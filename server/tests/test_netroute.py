"""Tests for the outbound egress router (VPN/proxy anonymization, no Tor)."""
import asyncio
import http.server
import io
import os
import select
import socket
import ssl
import tempfile
import threading
import time
from datetime import datetime, timedelta

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from PIL import Image

from app.services.netroute import (
    AsyncWebRelayTransport,
    ChainAsyncTransport,
    ChainSyncTransport,
    Egress,
    ProxyError,
    ProxySpec,
    WebRelayTransport,
    _build_raw_request,
    _find_ssh,
    _parse_response,
    parse_chain,
    parse_proxies,
    parse_proxy_url,
)


# --------------------------------------------------------------- mini servers
class MiniHttpServer:
    """Plain HTTP server that answers every path with a fixed body."""

    def __init__(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.paths.append(self.path)
                body = b"hello from target"
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.paths = []
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class MiniSocks5Proxy:
    """Tiny SOCKS5 proxy (NO_AUTH or USERNAME_PASSWORD) for tests."""

    def __init__(self, require_auth=False, user=b"user", password=b"pass"):
        self.require_auth = require_auth
        self.user = user
        self.password = password
        self.requests = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(32)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            nmethods = self._recv_exact(conn, 2)[1]
            methods = self._recv_exact(conn, nmethods)
            want_auth = self.require_auth and 0x02 in methods
            conn.sendall(b"\x05" + (b"\x02" if want_auth else b"\x00"))
            if want_auth:
                self._recv_exact(conn, 1)
                ulen = self._recv_exact(conn, 1)[0]
                uname = self._recv_exact(conn, ulen)
                plen = self._recv_exact(conn, 1)[0]
                passwd = self._recv_exact(conn, plen)
                if uname != self.user or passwd != self.password:
                    conn.sendall(b"\x01\x01")
                    return
                conn.sendall(b"\x01\x00")
            hdr = self._recv_exact(conn, 4)
            atype = hdr[3]
            if atype == 0x01:
                addr = socket.inet_ntoa(self._recv_exact(conn, 4))
            elif atype == 0x03:
                dlen = self._recv_exact(conn, 1)[0]
                addr = self._recv_exact(conn, dlen).decode()
            else:
                addr = socket.inet_ntop(socket.AF_INET6, self._recv_exact(conn, 16))
            port = int.from_bytes(self._recv_exact(conn, 2), "big")
            self.requests.append((addr, port))
            target = socket.create_connection((addr, port), timeout=5)
            conn.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            self._pipe(conn, target)
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _peek_atype(self, conn):
        data = self._recv_exact(conn, 1)
        return data[0]

    def _pipe(self, a, b):
        socks = [a, b]
        try:
            while True:
                r, _, _ = select.select(socks, [], [], 5)
                if not r:
                    continue
                for s in r:
                    data = s.recv(65536)
                    if not data:
                        return
                    (b if s is a else a).sendall(data)
        except OSError:
            pass
        finally:
            try:
                b.close()
            except OSError:
                pass

    def _recv_exact(self, conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise OSError("eof")
            buf += chunk
        return buf

    def close(self):
        self.sock.close()


class MiniHttpConnectProxy:
    """Tiny HTTP CONNECT proxy for tests."""

    def __init__(self):
        self.requests = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(32)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                data += chunk
            parts = data.split(b"\r\n", 1)[0].decode("latin1").split(" ")
            target = parts[1]
            host, port = target.rsplit(":", 1)
            port = int(port)
            self.requests.append((host, port))
            upstream = socket.create_connection((host, port), timeout=5)
            conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self._pipe(conn, upstream)
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _pipe(self, a, b):
        socks = [a, b]
        try:
            while True:
                r, _, _ = select.select(socks, [], [], 5)
                if not r:
                    continue
                for s in r:
                    data = s.recv(65536)
                    if not data:
                        return
                    (b if s is a else a).sendall(data)
        except OSError:
            pass
        finally:
            try:
                b.close()
            except OSError:
                pass

    def close(self):
        self.sock.close()


class MiniRelayServer:
    """Mimics a Cloudflare-Worker URL relay: fetches the encoded target itself."""

    def __init__(self):
        self.requests = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(32)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                data += chunk
            request_line = data.split(b"\r\n", 1)[0].decode("latin1")
            method, path, _ = request_line.split(" ")
            from urllib.parse import parse_qs, unquote, urlsplit

            if urlsplit(path).query:
                q = parse_qs(urlsplit(path).query)
                target = q.get("url", q.get("u", [""]))[0]
            else:
                target = unquote(path.lstrip("/"))
            self.requests.append(target)
            import http.client

            parts = target.split("/", 3)
            scheme, _, hostport = parts[0], parts[1], parts[2]
            host, _, port = hostport.rpartition(":")
            c = http.client.HTTPConnection(host, int(port), timeout=5)
            c.request("GET", "/" + (parts[3] if len(parts) > 3 else ""))
            r = c.getresponse()
            body = r.read()
            c.close()
            status = r.status
            ct = r.getheader("Content-Type", "application/octet-stream")
            conn.sendall(
                f"HTTP/1.1 {status} OK\r\nContent-Type: {ct}\r\n"
                f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("latin1")
                + body
            )
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def close(self):
        self.sock.close()


_SSL_PEM_DIR = None


def _self_signed_pem_files():
    """Generate a throwaway self-signed cert/key on disk (for the TLS proxy hop)."""
    global _SSL_PEM_DIR
    if _SSL_PEM_DIR is None:
        key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mini-tls-proxy")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow() - timedelta(days=1))
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=False)
            .sign(key, hashes.SHA256(), default_backend())
        )
        _SSL_PEM_DIR = tempfile.mkdtemp()
        cert_path = os.path.join(_SSL_PEM_DIR, "cert.pem")
        key_path = os.path.join(_SSL_PEM_DIR, "key.pem")
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        with open(key_path, "wb") as f:
            f.write(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                )
            )
    return os.path.join(_SSL_PEM_DIR, "cert.pem"), os.path.join(_SSL_PEM_DIR, "key.pem")


class MiniTlsConnectProxy:
    """Tiny HTTP CONNECT proxy that requires TLS from the client first."""

    def __init__(self):
        self.requests = []
        cert_path, key_path = _self_signed_pem_files()
        self._ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(32)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            conn = self._ctx.wrap_socket(conn, server_side=True)
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                data += chunk
            parts = data.split(b"\r\n", 1)[0].decode("latin1").split(" ")
            target = parts[1]
            host, port = target.rsplit(":", 1)
            port = int(port)
            self.requests.append((host, port))
            upstream = socket.create_connection((host, port), timeout=5)
            conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self._pipe(conn, upstream)
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _pipe(self, a, b):
        socks = [a, b]
        try:
            while True:
                r, _, _ = select.select(socks, [], [], 5)
                if not r:
                    continue
                for s in r:
                    data = s.recv(65536)
                    if not data:
                        return
                    (b if s is a else a).sendall(data)
        except OSError:
            pass
        finally:
            try:
                b.close()
            except OSError:
                pass

    def close(self):
        self.sock.close()
def test_parse_proxy_url_basic():
    spec = parse_proxy_url("socks5://user:pass@127.0.0.1:1080")
    assert spec.scheme == "socks5"
    assert spec.host == "127.0.0.1"
    assert spec.port == 1080
    assert spec.username == "user"
    assert spec.password == "pass"
    assert spec.url == "socks5://user%3Apass@127.0.0.1:1080" or spec.url.startswith("socks5://")


def test_parse_proxy_url_default_ports():
    assert parse_proxy_url("socks5://h").port == 1080
    assert parse_proxy_url("socks4://h:9050").port == 9050
    assert parse_proxy_url("http://h").port == 8080


def test_parse_proxy_url_rejects_unknown_scheme():
    with pytest.raises(ValueError):
        parse_proxy_url("ftp://h:21")


def test_parse_proxies_and_chain():
    specs = parse_proxies(" socks5://a:1080 , http://b:8118, socks4://c:9050 ")
    assert [s.host for s in specs] == ["a", "b", "c"]
    hops = parse_chain("socks5://x:1080 -> socks5://y:1080 -> http://z:3128")
    assert [h.host for h in hops] == ["x", "y", "z"]


# --------------------------------------------------------------- selection
def _pool():
    return [
        ProxySpec("socks5", "h1", 1),
        ProxySpec("socks5", "h2", 2),
        ProxySpec("socks5", "h3", 3),
    ]


def test_direct_and_chain_pick_none():
    assert Egress("direct", _pool(), [], 1)._pick_spec() is None
    eg = Egress("chain", [], parse_chain("socks5://a:1 -> socks5://b:2"), 1)
    assert eg._pick_spec() is None


def test_rotate_order():
    eg = Egress("rotate", _pool(), [], 1)
    assert [eg._pick_spec().host for _ in range(5)] == ["h1", "h2", "h3", "h1", "h2"]


def test_random_picks_from_pool():
    eg = Egress("random", _pool(), [], 1)
    picked = {eg._pick_spec().host for _ in range(50)}
    assert picked <= {"h1", "h2", "h3"}


def test_failover_sticky_then_fallback():
    eg = Egress("failover", _pool(), [], 1)
    assert eg._pick_spec().host == "h1"
    eg.mark_success(_pool()[0])
    assert eg._pick_spec().host == "h1"
    eg.mark_failure(_pool()[0])
    assert eg._pick_spec().host == "h2"
    eg.mark_success(_pool()[1])
    assert eg._pick_spec().host == "h2"


def test_guard_pins_entry_hop_until_failure():
    eg = Egress("guard", _pool(), [], 1)
    picked = {eg._pick_spec().host for _ in range(6)}
    assert picked == {"h1"}
    eg.mark_failure(_pool()[0])
    assert eg._pick_spec().host == "h2"
    assert eg._pick_spec().host == "h2"


def test_mixnet_builds_two_hop_random_circuits():
    eg = Egress("mixnet", _pool(), [], 1)
    assert eg._pick_spec() is None
    for _ in range(30):
        hop_a, hop_b = eg._pick_chain()
        assert hop_a in _pool() and hop_b in _pool()
        assert len({hop_a.host, hop_b.host}) == 2 or len(_pool()) == 1


def test_mixnet_egress_routes_through_two_hops():
    hop1 = MiniSocks5Proxy()
    hop2 = MiniSocks5Proxy()
    target = MiniHttpServer()
    eg = Egress("mixnet", [
        parse_proxy_url(f"socks5://127.0.0.1:{hop1.port}"),
        parse_proxy_url(f"socks5://127.0.0.1:{hop2.port}"),
    ], [], timeout=5)
    try:
        with eg.session() as client:
            resp = client.get(f"http://127.0.0.1:{target.port}/mix.png")
        assert resp.status_code == 200
        assert resp.content == b"hello from target"
    finally:
        hop1.close()
        hop2.close()
        target.close()
    # both hops must have seen the circuit (order may be [a,b] or [b,a]).
    assert (("127.0.0.1", hop1.port) in hop2.requests) or (("127.0.0.1", hop2.port) in hop1.requests)
    assert target.server.paths == ["/mix.png"]


def test_parse_proxy_url_accepts_ssh_scheme():
    spec = parse_proxy_url("ssh://svc@jump.example:2222")
    assert spec.scheme == "ssh"
    assert spec.host == "jump.example"
    assert spec.port == 2222
    assert spec.username == "svc"
    assert parse_proxy_url("ssh://h").port == 22


def test_ssh_jump_without_client_fails_cleanly(monkeypatch):
    monkeypatch.setattr("app.services.netroute._find_ssh", lambda: "")
    spec = parse_proxy_url("ssh://me@jump.example:22")
    eg = Egress("rotate", [spec], [], timeout=1)
    with pytest.raises(ProxyError):
        with eg.session() as client:
            client.get("http://example.com/")
    # failure must not permanently lock a guard in the pool
    assert eg._last_good_index is None or eg._last_good_index != 0


# --------------------------------------------------------------- raw helpers
def test_build_raw_request():
    req = httpx.Request("GET", "http://example.com/path?q=1")
    raw = _build_raw_request(req)
    assert b"GET /path?q=1 HTTP/1.1" in raw
    assert b"Host: example.com" in raw
    assert b"Connection: close" in raw


def test_parse_response():
    raw = b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nCache-Control: max-age=10\r\n\r\n\x89PNG"
    resp = _parse_response(raw, httpx.Request("GET", "http://x/"))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == b"\x89PNG"


# --------------------------------------------------------------- chain transport
def test_chain_transport_two_socks_hops():
    hop1 = MiniSocks5Proxy()
    hop2 = MiniSocks5Proxy()
    target = MiniHttpServer()
    chain = [
        parse_proxy_url(f"socks5://127.0.0.1:{hop1.port}"),
        parse_proxy_url(f"socks5://127.0.0.1:{hop2.port}"),
    ]
    transport = ChainSyncTransport(chain, timeout=5)
    client = httpx.Client(transport=transport, timeout=5)
    try:
        resp = client.get(f"http://127.0.0.1:{target.port}/tile.png")
        assert resp.status_code == 200
        assert resp.content == b"hello from target"
    finally:
        client.close()
        hop1.close()
        hop2.close()
        target.close()
    assert hop1.requests == [("127.0.0.1", hop2.port)]
    assert hop2.requests == [("127.0.0.1", target.port)]
    assert target.server.paths == ["/tile.png"]


def test_chain_transport_mixed_socks_and_http():
    socks = MiniSocks5Proxy()
    http_proxy = MiniHttpConnectProxy()
    target = MiniHttpServer()
    chain = [
        parse_proxy_url(f"socks5://127.0.0.1:{socks.port}"),
        parse_proxy_url(f"http://127.0.0.1:{http_proxy.port}"),
    ]
    transport = ChainSyncTransport(chain, timeout=5)
    client = httpx.Client(transport=transport, timeout=5)
    try:
        resp = client.get(f"http://127.0.0.1:{target.port}/x")
        assert resp.status_code == 200
    finally:
        client.close()
        socks.close()
        http_proxy.close()
        target.close()
    assert socks.requests == [("127.0.0.1", http_proxy.port)]
    assert http_proxy.requests == [("127.0.0.1", target.port)]


def test_chain_transport_https_proxy_tls_to_proxy_single_hop():
    tls_proxy = MiniTlsConnectProxy()
    target = MiniHttpServer()
    chain = [parse_proxy_url(f"https://127.0.0.1:{tls_proxy.port}")]
    transport = ChainSyncTransport(chain, timeout=5)
    client = httpx.Client(transport=transport, timeout=5)
    try:
        resp = client.get(f"http://127.0.0.1:{target.port}/via-tls")
        assert resp.status_code == 200
        assert resp.content == b"hello from target"
    finally:
        client.close()
        tls_proxy.close()
        target.close()
    assert tls_proxy.requests == [("127.0.0.1", target.port)]


def test_chain_transport_socks_then_https_proxy():
    socks = MiniSocks5Proxy()
    tls_proxy = MiniTlsConnectProxy()
    target = MiniHttpServer()
    chain = [
        parse_proxy_url(f"socks5://127.0.0.1:{socks.port}"),
        parse_proxy_url(f"https://127.0.0.1:{tls_proxy.port}"),
    ]
    transport = ChainSyncTransport(chain, timeout=5)
    client = httpx.Client(transport=transport, timeout=5)
    try:
        resp = client.get(f"http://127.0.0.1:{target.port}/mixed-tls")
        assert resp.status_code == 200
    finally:
        client.close()
        socks.close()
        tls_proxy.close()
        target.close()
    assert socks.requests == [("127.0.0.1", tls_proxy.port)]
    assert tls_proxy.requests == [("127.0.0.1", target.port)]


def test_chain_transport_socks5_auth_single_hop():
    proxy = MiniSocks5Proxy(require_auth=True)
    target = MiniHttpServer()
    chain = [
        parse_proxy_url(f"socks5://user:pass@127.0.0.1:{proxy.port}"),
    ]
    transport = ChainSyncTransport(chain, timeout=5)
    client = httpx.Client(transport=transport, timeout=5)
    try:
        resp = client.get(f"http://127.0.0.1:{target.port}/auth")
        assert resp.status_code == 200
    finally:
        client.close()
        proxy.close()
        target.close()
    assert proxy.requests == [("127.0.0.1", target.port)]


def test_chain_transport_refuses_bad_auth():
    proxy = MiniSocks5Proxy(require_auth=True)
    target = MiniHttpServer()
    chain = [parse_proxy_url(f"socks5://nope:wrong@127.0.0.1:{proxy.port}")]
    transport = ChainSyncTransport(chain, timeout=5)
    client = httpx.Client(transport=transport, timeout=5)
    try:
        with pytest.raises(httpx.TransportError):
            client.get(f"http://127.0.0.1:{target.port}/auth")
    finally:
        client.close()
        proxy.close()
        target.close()


def test_async_chain_transport_two_socks_hops():
    hop1 = MiniSocks5Proxy()
    hop2 = MiniSocks5Proxy()
    target = MiniHttpServer()

    async def main():
        chain = [
            parse_proxy_url(f"socks5://127.0.0.1:{hop1.port}"),
            parse_proxy_url(f"socks5://127.0.0.1:{hop2.port}"),
        ]
        transport = ChainAsyncTransport(chain, timeout=5)
        async with httpx.AsyncClient(transport=transport, timeout=5) as client:
            resp = await client.get(f"http://127.0.0.1:{target.port}/tile.png")
            assert resp.status_code == 200
            assert resp.content == b"hello from target"

    try:
        asyncio.run(main())
    finally:
        hop1.close()
        hop2.close()
        target.close()
    assert hop1.requests == [("127.0.0.1", hop2.port)]
    assert hop2.requests == [("127.0.0.1", target.port)]


# --------------------------------------------------------------- egress sessions
def test_tiles_endpoint_relays_through_chain(monkeypatch):
    """The /api/v1/tiles endpoint must relay tile fetches via the VPN egress."""
    from fastapi.testclient import TestClient

    from app.api.routers import tiles as tiles_router
    from app.main import app

    hop1 = MiniSocks5Proxy()
    hop2 = MiniSocks5Proxy()
    target = MiniHttpServer()
    chain_egress = Egress(
        "chain",
        [],
        [
            parse_proxy_url(f"socks5://127.0.0.1:{hop1.port}"),
            parse_proxy_url(f"socks5://127.0.0.1:{hop2.port}"),
        ],
        timeout=5,
    )
    monkeypatch.setattr(tiles_router, "egress", chain_egress)
    # point the "streets" provider at the local upstream server
    monkeypatch.setitem(
        tiles_router.TILE_PROVIDERS,
        "streets",
        f"http://127.0.0.1:{target.port}/" + "{z}/{x}/{y}.png",
    )

    client = TestClient(app)
    try:
        resp = client.get("/api/v1/tiles/streets/3/5/10.png?s=a")
        assert resp.status_code == 200
        assert resp.content == b"hello from target"
        assert "max-age=86400" in resp.headers.get("cache-control", "")
    finally:
        client.close()
        hop1.close()
        hop2.close()
        target.close()
    assert hop1.requests == [("127.0.0.1", hop2.port)]
    assert hop2.requests == [("127.0.0.1", target.port)]
    assert target.server.paths == ["/3/5/10.png"]


def test_egress_failover_session_falls_back_to_working_proxy():
    dead = parse_proxy_url("socks5://127.0.0.1:1")  # nothing listening
    proxy = MiniSocks5Proxy()
    target = MiniHttpServer()
    egress = Egress("failover", [dead, parse_proxy_url(f"socks5://127.0.0.1:{proxy.port}")], [], timeout=2)
    try:
        with pytest.raises(httpx.TransportError):
            with egress.session() as client:
                client.get(f"http://127.0.0.1:{target.port}/")
        with egress.session() as client:
            resp = client.get(f"http://127.0.0.1:{target.port}/ok")
        assert resp.status_code == 200
        # sticky: second call must reuse the working proxy without probing the dead one
        with egress.session() as client:
            resp2 = client.get(f"http://127.0.0.1:{target.port}/again")
        assert resp2.status_code == 200
    finally:
        proxy.close()
        target.close()
    assert len(proxy.requests) == 2


def test_egress_async_session_through_socks():
    proxy = MiniSocks5Proxy()
    target = MiniHttpServer()
    egress = Egress("rotate", [parse_proxy_url(f"socks5://127.0.0.1:{proxy.port}")], [], timeout=5)

    async def main():
        async with egress.async_session() as client:
            resp = await client.get(f"http://127.0.0.1:{target.port}/a")
            return resp.status_code

    try:
        code = asyncio.run(main())
    finally:
        proxy.close()
        target.close()
    assert code == 200
    assert proxy.requests == [("127.0.0.1", target.port)]


# --------------------------------------------------------------- web-relay mode
def test_web_relay_transport_sync():
    relay = MiniRelayServer()
    target = MiniHttpServer()
    transport = WebRelayTransport(f"http://127.0.0.1:{relay.port}", timeout=5)
    client = httpx.Client(transport=transport, timeout=5)
    try:
        resp = client.get(f"http://127.0.0.1:{target.port}/tile.png")
        assert resp.status_code == 200
        assert resp.content == b"hello from target"
    finally:
        client.close()
        transport.close()
        relay.close()
        target.close()
    assert relay.requests == [f"http://127.0.0.1:{target.port}/tile.png"]


def test_web_relay_transport_async():
    relay = MiniRelayServer()
    target = MiniHttpServer()

    async def main():
        transport = AsyncWebRelayTransport(f"http://127.0.0.1:{relay.port}", timeout=5)
        async with httpx.AsyncClient(transport=transport, timeout=5) as client:
            resp = await client.get(f"http://127.0.0.1:{target.port}/json")
            return resp.status_code, resp.content

    try:
        code, body = asyncio.run(main())
    finally:
        relay.close()
        target.close()
    assert code == 200
    assert body == b"hello from target"


def test_egress_relay_mode_session():
    relay = MiniRelayServer()
    target = MiniHttpServer()
    egress = Egress("relay", [], [], timeout=5)
    egress.relay_url = f"http://127.0.0.1:{relay.port}"
    try:
        with egress.session() as client:
            resp = client.get(f"http://127.0.0.1:{target.port}/x")
        assert resp.status_code == 200
        assert resp.content == b"hello from target"
    finally:
        relay.close()
        target.close()
    assert relay.requests == [f"http://127.0.0.1:{target.port}/x"]


def test_web_relay_transport_query_format():
    relay = MiniRelayServer()
    target = MiniHttpServer()
    transport = WebRelayTransport(f"http://127.0.0.1:{relay.port}", timeout=5, format="query")
    client = httpx.Client(transport=transport, timeout=5)
    try:
        resp = client.get(f"http://127.0.0.1:{target.port}/img.png")
        assert resp.status_code == 200
        assert resp.content == b"hello from target"
    finally:
        client.close()
        transport.close()
        relay.close()
        target.close()
    # query-style relay must have received the target via ?url=...
    assert relay.requests == [f"http://127.0.0.1:{target.port}/img.png"]


def test_web_relay_transport_duckduckgo_format():
    relay = MiniRelayServer()
    target = MiniHttpServer()
    transport = WebRelayTransport(f"http://127.0.0.1:{relay.port}", timeout=5, format="duckduckgo")
    client = httpx.Client(transport=transport, timeout=5)
    try:
        resp = client.get(f"http://127.0.0.1:{target.port}/us.png")
        assert resp.status_code == 200
    finally:
        client.close()
        transport.close()
        relay.close()
        target.close()
    # DDG-style relay receives the target via /iu/?u=... -> query-string url param
    assert relay.requests == [f"http://127.0.0.1:{target.port}/us.png"]


def test_web_relay_query_ignores_dark_filter_params():
    relay = MiniRelayServer()
    target = MiniHttpServer()
    # dark tiles append &filt=greyscale&bri=-40 after ?url=... - must still resolve
    wrapped = f"http://127.0.0.1:{relay.port}/?url=http%3A%2F%2F127.0.0.1%3A{target.port}%2Fd.png&filt=greyscale&bri=-40"
    with httpx.Client(timeout=5) as client:
        resp = client.get(wrapped)
    assert resp.status_code == 200
    assert relay.requests == [f"http://127.0.0.1:{target.port}/d.png"]


def test_egress_image_session_uses_query_relay():
    relay = MiniRelayServer()
    target = MiniHttpServer()
    egress = Egress("direct", [], [], timeout=5)
    egress.image_relay_url = f"http://127.0.0.1:{relay.port}"
    try:
        with egress.image_session() as client:
            resp = client.get(f"http://127.0.0.1:{target.port}/map.png")
        assert resp.status_code == 200
        assert resp.content == b"hello from target"
    finally:
        relay.close()
        target.close()
    assert relay.requests == [f"http://127.0.0.1:{target.port}/map.png"]


class MiniTileServer(MiniHttpServer):
    """HTTP server that returns a small solid-color PNG tile."""

    def __init__(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.paths.append(self.path)
                buf = io.BytesIO()
                Image.new("RGB", (256, 256), (64, 128, 192)).save(buf, format="PNG")
                body = buf.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.paths = []
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()


def test_build_static_map_stitches_relay_tiles(monkeypatch):
    import app.services.static_map as sm
    from app.services import static_map as static_map_mod

    relay = MiniRelayServer()
    tiles = MiniTileServer()
    egress = Egress("direct", [], [], timeout=5)
    egress.image_relay_url = f"http://127.0.0.1:{relay.port}"
    monkeypatch.setattr(static_map_mod, "egress", egress)
    monkeypatch.setattr(
        static_map_mod,
        "ESRI_STREETS",
        f"http://127.0.0.1:{tiles.port}/{{z}}/{{x}}/{{y}}",
    )
    try:
        png = sm.build_static_map(28.61, 77.2, radius_nm=5.0, width=512, height=384)
        with Image.open(io.BytesIO(png)) as img:
            assert img.size == (512, 384)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
    finally:
        relay.close()
        tiles.close()
    assert len(tiles.server.paths) > 1
    assert len(relay.requests) == len(tiles.server.paths)
