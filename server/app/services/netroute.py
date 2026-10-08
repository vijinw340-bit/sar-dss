"""Outbound egress routing for VPN / multi-hop proxy anonymization (no Tor).

SAR-DSS talks to public services for live weather, static map images and map
tiles. Those requests normally leave from the server's public IP. This module
lets every outbound call instead exit through private VPN/proxy infrastructure,
offering several egress strategies:

* ``direct``   - no proxy (default - unchanged behaviour, best for already
                 tunneled hosts e.g. a WireGuard/OpenVPN box that VPNs at the OS
                 level - those are detected automatically and need no work).
* ``rotate``   - round-robin across the proxy pool; every request leaves from a
                 different exit node.
* ``random``   - a random pool member is chosen per request.
* ``failover`` - stick to the last proxy that worked; fall through the rest of
                 the pool on errors.
* ``chain``    - multi-hop SOCKS tunnelling through two or more nodes before
                 reaching the target - a miniature private relay network.
* ``guard``    - Tor-style guard node: pin one entry hop per session and never
                 change it until it fails, keeping the peer's exit stable.
* ``mixnet``   - like ``chain`` but the 2-hop circuit is assembled at random
                 from the proxy pool on every request (rotating circuits).
* ``relay``    - URL-forwarding relays (Cloudflare Worker / Jina / wsrv).

The ``socks5://``, ``socks4://``, ``http://`` and ``https://`` schemes are
supported in single-hop and chain modes. An ``ssh://user@host[:port]`` proxy
is a "poor man's VPN": a local ``ssh -N -D`` dynamic SOCKS ball is spawned
against the jump host and all traffic is routed through it.

Everything consults the standard ``HTTP(S)_PROXY`` / ``ALL_PROXY`` environment
variables transparently when running in ``failover`` / ``rotate`` / ``random``
modes through httpx transport wiring.
"""
import asyncio
import atexit
import ipaddress
import os
import random
import shutil
import socket
import ssl
import subprocess
import time
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import httpx
from socksio.exceptions import SOCKSError
from socksio.socks4 import (
    SOCKS4ARequest,
    SOCKS4Command,
    SOCKS4Reply,
    SOCKS4ReplyCode,
    SOCKS4Request,
)
from socksio.socks5 import (
    SOCKS5AuthMethod,
    SOCKS5AuthMethodsRequest,
    SOCKS5Command,
    SOCKS5CommandRequest,
    SOCKS5Connection,
    SOCKS5ReplyCode,
    SOCKS5UsernamePasswordRequest,
)

from app.core.config import settings

VALID_MODES = ("direct", "rotate", "random", "failover", "chain", "relay", "guard", "mixnet")


class ProxyError(ConnectionError):
    """Raised when a VPN/proxy hop refuses or misbehaves."""


# --------------------------------------------------------------------------- specs
@dataclass(frozen=True)
class ProxySpec:
    """A single proxy/VPN-exit endpoint parsed from a URL."""

    scheme: str
    host: str
    port: int
    username: str = ""
    password: str = ""

    @property
    def url(self) -> str:
        """Rebuild a URL acceptable to httpx transports."""
        userinfo = f"{self._q(self.username)}:{self._q(self.password)}@" if self.username else ""
        return f"{self.scheme}://{userinfo}{self.host}:{self.port}"

    @staticmethod
    def _q(value: str) -> str:
        from urllib.parse import quote

        return quote(value, safe="")


def parse_proxy_url(raw: str) -> ProxySpec:
    """Parse ``socks5://user:pass@host:port`` etc into a ProxySpec."""
    from urllib.parse import urlsplit

    parts = urlsplit(raw.strip())
    scheme = (parts.scheme or "socks5").lower()
    if scheme not in ("socks5", "socks4", "http", "https", "ssh"):
        raise ValueError(f"Unsupported proxy scheme: {scheme!r}")
    if not parts.hostname:
        raise ValueError(f"Proxy URL has no host: {raw!r}")
    return ProxySpec(
        scheme=scheme,
        host=parts.hostname,
        port=parts.port or (22 if scheme == "ssh" else 1080 if scheme.startswith("socks") else 8080),
        username=parts.username or "",
        password=parts.password or "",
    )


def parse_proxies(raw: str) -> list:
    """Split a comma separated proxy list into ProxySpec list."""
    out = []
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if chunk:
            out.append(parse_proxy_url(chunk))
    return out


def parse_chain(raw: str) -> list:
    """Parse a chain like ``socks5://a:1080 -> socks5://b:1080`` into a hop list."""
    out = []
    for chunk in (raw or "").split("->"):
        chunk = chunk.strip()
        if chunk:
            out.append(parse_proxy_url(chunk))
    return out


@dataclass(frozen=True)
class _SshTunnel:
    """A live ``ssh -N -D`` dynamic SOCKS ball plus its child process."""

    port: int
    proc: subprocess.Popen


def _find_ssh() -> str:
    """Locate an OpenSSH client binary (Windows ships one via OpenSSH Client)."""
    found = shutil.which("ssh")
    if found:
        return found
    windows_ssh = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                               "System32", "OpenSSH", "ssh.exe")
    if os.path.isfile(windows_ssh):
        return windows_ssh
    return ""


# --------------------------------------------------------------------- egress
class Egress:
    """Stateful egress router. Builds httpx clients wired to the VPN/proxy farm."""

    def __init__(self, mode: str, proxies: list, chain: list, timeout: float = 15.0):
        self._mode = mode if mode in VALID_MODES else "direct"
        self._pool = proxies or []
        self._chain = chain or []
        self.timeout = timeout
        self.relay_url = settings.OUTBOUND_RELAY_URL.strip().rstrip("/")
        self.image_relay_url = settings.OUTBOUND_IMAGE_RELAY_URL.strip().rstrip("/")
        self._counter = 0
        self._last_good_index: Optional[int] = None
        self._guard_index: Optional[int] = None
        self._ssh_tunnels = {}

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def pool(self) -> list:
        return list(self._pool)

    @property
    def chain(self) -> list:
        return list(self._chain)

    # -- selection -----------------------------------------------------------
    def _pick_spec(self) -> Optional[ProxySpec]:
        if self._mode in ("direct", "chain", "mixnet") or not self._pool:
            return None
        if self._mode == "guard":
            # Tor-style guard node: pick an entry point once and pin to it so a
            # peer's behaviour stays stable; only re-randomize after a failure.
            if self._guard_index is None:
                self._guard_index = self._counter % len(self._pool)
                self._counter += 1
            return self._pool[self._guard_index]
        if self._mode == "failover":
            if self._last_good_index is not None:
                return self._pool[self._last_good_index]
            idx = self._counter % len(self._pool)
            self._counter += 1
            return self._pool[idx]
        if self._mode == "random":
            return random.choice(self._pool)
        idx = self._counter % len(self._pool)
        self._counter += 1
        return self._pool[idx]

    def _pick_chain(self) -> list:
        """Build a random 2-hop mixnet circuit from the pool (no self-loop)."""
        a = random.choice(self._pool)
        rest = [p for p in self._pool if p != a]
        b = random.choice(rest) if rest else a
        return [a, b]

    def mark_success(self, spec: Optional[ProxySpec]) -> None:
        if spec is None:
            return
        try:
            self._last_good_index = self._pool.index(spec)
        except ValueError:
            pass

    def mark_failure(self, spec: Optional[ProxySpec]) -> None:
        if spec is None:
            return
        if self._mode == "guard":
            self._guard_index = None
            return
        try:
            idx = self._pool.index(spec)
        except ValueError:
            return
        if self._last_good_index == idx:
            self._last_good_index = None

    # -- client factory ------------------------------------------------------
    def _build_client(self, spec: Optional[ProxySpec], sync: bool, image: bool = False):
        timeout = httpx.Timeout(self.timeout, connect=self.timeout)
        if image and self.image_relay_url:
            _fmt = settings.OUTBOUND_IMAGE_RELAY_FORMAT
            transport = (
                WebRelayTransport(self.image_relay_url, timeout=self.timeout, format=_fmt)
                if sync
                else AsyncWebRelayTransport(self.image_relay_url, timeout=self.timeout, format=_fmt)
            )
        elif self._mode == "relay" and self.relay_url:
            transport = (
                WebRelayTransport(self.relay_url, timeout=self.timeout)
                if sync
                else AsyncWebRelayTransport(self.relay_url, timeout=self.timeout)
            )
        elif self._mode == "chain" and len(self._chain) >= 2:
            transport = (
                ChainSyncTransport(self._chain, timeout=self.timeout)
                if sync
                else ChainAsyncTransport(self._chain, timeout=self.timeout)
            )
        elif self._mode == "mixnet" and len(self._pool) >= 2:
            hops = self._pick_chain()
            transport = (
                ChainSyncTransport(hops, timeout=self.timeout)
                if sync
                else ChainAsyncTransport(hops, timeout=self.timeout)
            )
        elif spec:
            if spec.scheme == "ssh":
                # ssh://user@host jump -> spawn a local dynamic SOCKS ball once.
                spec = self._ssh_tunnel_spec(spec)
            transport = (
                httpx.HTTPTransport(proxy=spec.url)
                if sync
                else httpx.AsyncHTTPTransport(proxy=spec.url)
            )
        else:
            transport = None

        if sync:
            if transport is not None:
                return httpx.Client(transport=transport, timeout=timeout, follow_redirects=True)
            return httpx.Client(timeout=timeout, follow_redirects=True)
        if transport is not None:
            return httpx.AsyncClient(transport=transport, timeout=timeout, follow_redirects=True)
        return httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    # -- session helpers -----------------------------------------------------
    def session(self) -> "_SyncSession":
        """Open a sync httpx.Client routed through the configured egress."""
        return _SyncSession(self)

    def async_session(self) -> "_AsyncSession":
        """Open an async httpx.AsyncClient routed through the configured egress."""
        return _AsyncSession(self)

    def image_session(self) -> "_SyncSession":
        """Sync client routed through the image relay (``query`` format, e.g. wsrv)."""
        session = _SyncSession(self)
        session._image_only = True
        return session

    def async_image_session(self) -> "_AsyncSession":
        """Async client routed through the image relay (``query`` format, e.g. wsrv)."""
        session = _AsyncSession(self)
        session._image_only = True
        return session

    # -- ssh dynamic-socks jump ----------------------------------------------
    @staticmethod
    def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _ssh_tunnel_spec(self, spec: ProxySpec) -> ProxySpec:
        """Lazily spawn ``ssh -N -D`` for an ``ssh://`` proxy and return the
        local SOCKS endpoint it listens on. Tunnels are cached and reused
        until the port dies (then they are rebuilt on the next request)."""
        key = spec.url
        cached = self._ssh_tunnels.get(key)
        if cached and self._port_open(cached.port):
            return cached
        if cached:
            try:
                cached.proc.terminate()
            except OSError:
                pass
        ssh_exe = _find_ssh()
        if not ssh_exe:
            raise ProxyError("SSH jump configured but no ssh client found on this host")
        port = self._free_port()
        target = f"{spec.username}@{spec.host}" if spec.username else spec.host
        cmd = [
            ssh_exe, "-N", "-D", f"127.0.0.1:{port}",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=30",
            "-o", "ConnectTimeout=10",
            "-p", str(spec.port),
            target,
        ]
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        proc = subprocess.Popen(cmd, **kwargs)
        deadline = time.time() + max(8.0, self.timeout)
        while time.time() < deadline:
            if self._port_open(port):
                spec_local = ProxySpec("socks5", "127.0.0.1", port)
                self._ssh_tunnels[key] = _SshTunnel(spec_local, proc)
                return spec_local
            if proc.poll() is not None:
                raise ProxyError("SSH tunnel died during handshake")
            time.sleep(0.25)
        try:
            proc.terminate()
        except OSError:
            pass
        raise ProxyError("SSH tunnel did not open its SOCKS port in time")

    def shutdown(self) -> None:
        """Kill every SSH jump tunnel spawned by this router."""
        for key, tunnel in list(self._ssh_tunnels.items()):
            try:
                tunnel.proc.terminate()
            except OSError:
                pass
            del self._ssh_tunnels[key]

    def __del__(self):
        try:
            self.shutdown()
        except Exception:
            pass


class _SyncSession(AbstractContextManager):
    """Context manager that marks egress success/failure for failover mode."""

    def __init__(self, egress: Egress):
        self._egress = egress
        self._spec: Optional[ProxySpec] = None
        self._image_only = False
        self.client: Optional[httpx.Client] = None

    def __enter__(self) -> httpx.Client:
        self._spec = self._egress._pick_spec()
        self.client = self._egress._build_client(self._spec, sync=True, image=self._image_only)
        return self.client

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self.client is not None:
            self.client.close()
        if exc is None:
            self._egress.mark_success(self._spec)
        else:
            self._egress.mark_failure(self._spec)
        return False


class _AsyncSession(AbstractAsyncContextManager):
    """Async variant of _SyncSession."""

    def __init__(self, egress: Egress):
        self._egress = egress
        self._spec: Optional[ProxySpec] = None
        self._image_only = False
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> httpx.AsyncClient:
        self._spec = self._egress._pick_spec()
        self.client = self._egress._build_client(self._spec, sync=False, image=self._image_only)
        return self.client

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if self.client is not None:
            await self.client.aclose()
        if exc is None:
            self._egress.mark_success(self._spec)
        else:
            self._egress.mark_failure(self._spec)
        return False


# ------------------------------------------------------------------ raw http
def _build_raw_request(request: httpx.Request) -> bytes:
    """Serialize an httpx request as a self-contained HTTP/1.1 request."""
    path = request.url.raw_path.decode("latin1") or "/"
    lines = [f"{request.method} {path} HTTP/1.1".encode("latin1")]
    seen_host = False
    for name, value in request.headers.raw:
        lines.append(name + b": " + value)
        if name.lower() == b"host":
            seen_host = True
    if not seen_host:
        lines.append(b"Host: " + request.url.netloc.decode("latin1"))
    body = request.content or b""
    if body:
        lines.append(f"Content-Length: {len(body)}".encode("latin1"))
    lines.append(b"Connection: close")
    return b"\r\n".join(lines) + b"\r\n\r\n" + body


def _parse_response(raw: bytes, request: httpx.Request) -> httpx.Response:
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    status_line = lines[0].decode("latin1", "replace")
    try:
        status_code = int(status_line.split(" ")[1])
    except (IndexError, ValueError):
        status_code = 599
    reason = " ".join(status_line.split(" ")[2:])
    headers = []
    for line in lines[1:]:
        name, _, value = line.partition(b":")
        if name:
            headers.append((name, value.strip()))
    return httpx.Response(
        status_code=status_code,
        headers=headers,
        content=body,
        request=request,
        extensions={"http_version": b"HTTP/1.1", "reason_phrase": reason.encode("latin1")},
    )


# ------------------------------------------------------------ tunnel helpers
def _host_is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _socks5_step_sync(sock, proxy: ProxySpec, host: str, port: int, timeout: float) -> None:
    conn = SOCKS5Connection()
    conn.send(SOCKS5AuthMethodsRequest(
        [SOCKS5AuthMethod.NO_AUTH_REQUIRED, SOCKS5AuthMethod.USERNAME_PASSWORD]
    ))
    sock.sendall(conn.data_to_send())
    reply = conn.receive_data(_recv_exact_sync(sock, 2, timeout))
    if reply.method == SOCKS5AuthMethod.USERNAME_PASSWORD:
        if not proxy.username:
            raise ProxyError("SOCKS5 proxy requires credentials")
        conn.send(SOCKS5UsernamePasswordRequest(
            proxy.username.encode(), (proxy.password or "").encode()
        ))
        sock.sendall(conn.data_to_send())
        auth = conn.receive_data(_recv_exact_sync(sock, 2, timeout))
        if not auth.success:
            raise ProxyError("SOCKS5 username/password rejected")
    elif reply.method != SOCKS5AuthMethod.NO_AUTH_REQUIRED:
        raise ProxyError(f"SOCKS5 proxy picked unsupported method: {reply.method!r}")

    conn.send(SOCKS5CommandRequest.from_address(SOCKS5Command.CONNECT, (host, port)))
    sock.sendall(conn.data_to_send())
    prefix = _recv_exact_sync(sock, 4, timeout)
    atype = prefix[3]
    if atype == 0x01:
        addrn = 4
    elif atype == 0x03:
        addrn = 1 + _recv_exact_sync(sock, 1, timeout)[0]
    else:
        addrn = 16
    reply = conn.receive_data(prefix + _recv_exact_sync(sock, addrn + 2, timeout))
    if reply.reply_code != SOCKS5ReplyCode.SUCCEEDED:
        raise ProxyError(f"SOCKS5 CONNECT failed: {reply.reply_code!r}")


def _socks4_step_sync(sock, proxy: ProxySpec, host: str, port: int, timeout: float) -> None:
    user_id = (proxy.username or "sardss").encode()
    if _host_is_ip(host):
        req = SOCKS4Request.from_address(SOCKS4Command.CONNECT, (host, port), user_id)
    else:
        req = SOCKS4ARequest.from_address(SOCKS4Command.CONNECT, (host, port), user_id)
    sock.sendall(req.dumps())
    reply = SOCKS4Reply.loads(_recv_exact_sync(sock, 8, timeout))
    if reply.reply_code != SOCKS4ReplyCode.REQUEST_GRANTED:
        raise ProxyError(f"SOCKS4 CONNECT failed: {reply.reply_code!r}")


def _http_connect_step_sync(sock, host: str, port: int, timeout: float) -> None:
    req = (
        f"CONNECT {host}:{port} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\nProxy-Connection: keep-alive\r\n\r\n"
    ).encode("latin1")
    sock.sendall(req)
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ProxyError("HTTP CONNECT proxy closed early")
        buf += chunk
    status_line = buf.split(b"\r\n", 1)[0]
    parts = status_line.split(b" ", 2)
    if len(parts) < 2 or parts[1] != b"200":
        raise ProxyError(f"HTTP CONNECT refused: {status_line.decode('latin1', 'replace')}")


_PROXY_TLS_CTX = ssl._create_unverified_context()


def _tunnel_step_sync(sock, proxy: ProxySpec, host: str, port: int, timeout: float):
    if proxy.scheme == "https":
        sock = _PROXY_TLS_CTX.wrap_socket(sock, server_hostname=proxy.host)
    if proxy.scheme in ("socks5",):
        _socks5_step_sync(sock, proxy, host, port, timeout)
    elif proxy.scheme in ("socks4",):
        _socks4_step_sync(sock, proxy, host, port, timeout)
    else:
        _http_connect_step_sync(sock, host, port, timeout)
    return sock


def _recv_exact_sync(sock, n: int, timeout: float) -> bytes:
    sock.settimeout(timeout)
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ProxyError("Remote closed during tunnel setup")
        buf += chunk
    return buf


# ------------------------------------------------------------ sync transport
class ChainSyncTransport(httpx.BaseTransport):
    """Sync httpx transport that tunnels each request through 2+ proxies."""

    def __init__(self, hops: list, timeout: float = 15.0):
        self.hops = hops
        self.timeout = timeout

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        sock = None
        try:
            sock = socket.create_connection(
                (self.hops[0].host, self.hops[0].port), timeout=self.timeout
            )
            for i, hop in enumerate(self.hops):
                target = (self.hops[i + 1].host, self.hops[i + 1].port) \
                    if i < len(self.hops) - 1 else (host, port)
                sock = _tunnel_step_sync(sock, hop, target[0], target[1], self.timeout)
            if request.url.scheme == "https":
                ctx = ssl.create_default_context()
                sock = ctx.wrap_socket(sock, server_hostname=host)
            sock.sendall(_build_raw_request(request))
            raw = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                raw += chunk
            return _parse_response(raw, request)
        except (socket.error, OSError, SOCKSError, ProxyError, ssl.SSLError) as exc:
            raise httpx.TransportError(f"Proxy chain failed: {exc}") from exc
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    def close(self) -> None:
        pass


# ------------------------------------------------------------ async transport
class ChainAsyncTransport(httpx.AsyncBaseTransport):
    """Async httpx transport that tunnels each request through 2+ proxies.

    Tunnel setup runs in a worker thread (it reuses the battle-tested sync
    socket/SOCKS/TLS logic) so it also works on Windows where the Proactor
    event loop cannot upgrade transports with ``start_tls``.
    """

    def __init__(self, hops: list, timeout: float = 15.0):
        self.hops = hops
        self.timeout = timeout

    def _connect(self, request: httpx.Request) -> socket.socket:
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        sock = socket.create_connection(
            (self.hops[0].host, self.hops[0].port), timeout=self.timeout
        )
        try:
            for i, hop in enumerate(self.hops):
                target = (self.hops[i + 1].host, self.hops[i + 1].port) \
                    if i < len(self.hops) - 1 else (host, port)
                sock = _tunnel_step_sync(sock, hop, target[0], target[1], self.timeout)
            if request.url.scheme == "https":
                ctx = ssl.create_default_context()
                sock = ctx.wrap_socket(sock, server_hostname=host)
            sock.setblocking(False)
            return sock
        except Exception:
            try:
                sock.close()
            except OSError:
                pass
            raise

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        loop = asyncio.get_running_loop()
        sock = None
        try:
            sock = await asyncio.to_thread(self._connect, request)
            await asyncio.wait_for(
                loop.sock_sendall(sock, _build_raw_request(request)), self.timeout
            )
            raw = b""
            while True:
                chunk = await asyncio.wait_for(loop.sock_recv(sock, 65536), self.timeout)
                if not chunk:
                    break
                raw += chunk
            return _parse_response(raw, request)
        except (socket.error, OSError, SOCKSError, ProxyError, ssl.SSLError, asyncio.TimeoutError) as exc:
            raise httpx.TransportError(f"Proxy chain failed: {exc}") from exc
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    async def aclose(self) -> None:
        pass


# ------------------------------------------------------------ web-relay mode
def _wrap_relay_url(base: str, target: str, format: str = "path") -> str:
    """Build a relay URL for a URL-forwarding service.

    ``path``      -> ``<base>/<percent-encoded full target URL>``   (Workers, Jina, Wayback)
    ``query``     -> ``<base>/?url=<percent-encoded full target URL>``  (wsrv / image CDN relays)
    ``duckduckgo``-> ``<base>/iu/?u=<percent-encoded full target URL>`` (DDG image proxy, US)
    """
    enc = quote(target, safe="")
    if format == "query":
        return f"{base.rstrip('/')}/?url={enc}"
    if format == "duckduckgo":
        return f"{base.rstrip('/')}/iu/?u={enc}"
    return f"{base.rstrip('/')}/{enc}"


def _relay_request_headers(request: httpx.Request) -> dict:
    """Headers to forward to the relay (drops hop-by-hop / body framing)."""
    out = {}
    for name, value in request.headers.items():
        if name.lower() in ("host", "content-length", "content-type", "transfer-encoding", "connection"):
            continue
        out[name] = value
    if "user-agent" not in out:
        out["User-Agent"] = "Mozilla/5.0"
    return out


class WebRelayTransport(httpx.BaseTransport):
    """Routes every request through an HTTPS URL-forwarding relay (e.g. a
    Cloudflare Worker, Jina Reader or wsrv image CDN) that fetches the encoded
    target from its own egress. Preserves upstream status, headers and bytes.
    """

    def __init__(self, base_url: str, timeout: float = 15.0, format: str = "path"):
        self.base = base_url
        self.timeout = timeout
        self.format = format
        self._client = httpx.Client(verify=False, timeout=timeout, follow_redirects=True)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        wrapped = _wrap_relay_url(self.base, str(request.url), self.format)
        try:
            resp = self._client.get(wrapped, headers=_relay_request_headers(request))
        except httpx.HTTPError as exc:
            raise httpx.TransportError(f"Web relay failed: {exc}") from exc
        return httpx.Response(
            status_code=resp.status_code,
            headers=httpx.Headers(resp.headers),
            content=resp.content,
            request=request,
        )

    def close(self) -> None:
        self._client.close()


class AsyncWebRelayTransport(httpx.AsyncBaseTransport):
    """Async twin of WebRelayTransport."""

    def __init__(self, base_url: str, timeout: float = 15.0, format: str = "path"):
        self.base = base_url
        self.timeout = timeout
        self.format = format
        self._client = httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=True)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        wrapped = _wrap_relay_url(self.base, str(request.url), self.format)
        try:
            resp = await self._client.get(wrapped, headers=_relay_request_headers(request))
        except httpx.HTTPError as exc:
            raise httpx.TransportError(f"Web relay failed: {exc}") from exc
        return httpx.Response(
            status_code=resp.status_code,
            headers=httpx.Headers(resp.headers),
            content=resp.content,
            request=request,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


# ------------------------------------------------------------------- singleton
def build_egress(source=settings) -> Egress:
    return Egress(
        mode=source.OUTBOUND_MODE,
        proxies=parse_proxies(source.OUTBOUND_PROXIES),
        chain=parse_chain(source.OUTBOUND_PROXY_CHAIN),
        timeout=float(source.OUTBOUND_CONNECT_TIMEOUT),
    )


egress = build_egress()
atexit.register(egress.shutdown)