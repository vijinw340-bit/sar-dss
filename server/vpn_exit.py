"""Local SOCKS5 VPN-exit tunnel service for SAR-DSS.

A small, self-contained SOCKS5 proxy that acts as the app's VPN exit hop.
Clients (the SAR-DSS egress, or anything pointed at 127.0.0.1:1080) connect
here; every CONNECT is relayed to the target either directly or - when
OUTBOUND_PROXY_CHAIN is set - through the configured remote VPN nodes
(multi-hop relay). This is the on-host "VPN" that netroute.py routes through.

Run:  python server/vpn_exit.py            (listens on 127.0.0.1:1080)
Env:  SOCKS5_USER / SOCKS5_PASSWORD        optional client auth
      OUTBOUND_PROXY_CHAIN                 optional -> remote VPN hops
"""
import os
import select
import socket
import threading

HOST = os.getenv("SOCKS5_HOST", "127.0.0.1")
PORT = int(os.getenv("SOCKS5_PORT", "1080"))
USER = os.getenv("SOCKS5_USER", "")
PASSWORD = os.getenv("SOCKS5_PASSWORD", "")

# optional upstream hops: "socks5://nodeA:1080 -> socks5://nodeB:1080"
CHAIN = os.getenv("OUTBOUND_PROXY_CHAIN", "")

from app.services.netroute import ProxyError, _host_is_ip, _tunnel_step_sync, parse_chain  # noqa: E402


def build_upstream(host: str, port: int, timeout: float):
    """Return a socket connected to host:port through the VPN chain or directly."""
    hops = parse_chain(CHAIN)
    if hops:
        sock = socket.create_connection((hops[0].host, hops[0].port), timeout=timeout)
        try:
            for i, hop in enumerate(hops):
                target = (hops[i + 1].host, hops[i + 1].port) if i < len(hops) - 1 else (host, port)
                _tunnel_step_sync(sock, hop, target[0], target[1], timeout)
            return sock
        except Exception:
            sock.close()
            raise
    return socket.create_connection((host, port), timeout=timeout)


def recv_exact(conn, n: int):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("eof")
        buf += chunk
    return buf


def handle(conn):
    try:
        version = recv_exact(conn, 2)
        if version[0] != 0x05:
            return
        methods = recv_exact(conn, version[1])
        want_auth = bool(USER) and 0x02 in methods
        conn.sendall(b"\x05" + (b"\x02" if want_auth else b"\x00"))
        if want_auth:
            recv_exact(conn, 1)
            ulen = recv_exact(conn, 1)[0]
            uname = recv_exact(conn, ulen)
            plen = recv_exact(conn, 1)[0]
            passwd = recv_exact(conn, plen)
            if uname != USER.encode() or passwd != PASSWORD.encode():
                conn.sendall(b"\x01\x01")
                return
            conn.sendall(b"\x01\x00")
        hdr = recv_exact(conn, 4)
        atype = hdr[3]
        if atype == 0x01:
            host = socket.inet_ntoa(recv_exact(conn, 4))
        elif atype == 0x03:
            dlen = recv_exact(conn, 1)[0]
            host = recv_exact(conn, dlen).decode()
        else:
            host = socket.inet_ntop(socket.AF_INET6, recv_exact(conn, 16))
        port = int.from_bytes(recv_exact(conn, 2), "big")
        upstream = build_upstream(host, port, timeout=15)
        conn.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        pipe(conn, upstream)
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass


def pipe(a, b):
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


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(64)
    print(f"SAR-DSS VPN exit (SOCKS5) listening on {HOST}:{PORT}"
          f" | chain={CHAIN or 'direct'}")
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    main()
