"""Check real nginx ingress in isolated Docker containers with synthetic TLS.

No live containers, DNS records, production certificates, or persisted state are used.
Requires cached nginx/python images, Docker Linux engine, and a local OpenSSL binary.
"""
from __future__ import annotations

import argparse
import http.client
import json
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import uuid

from render_ingress import ROOT, render

NGINX_IMAGE = "nginx:alpine@sha256:c8497b180665e631ec92a5091125bec5b214f0e2b99409e30653a125b37557da"
CONTROL = "connect.example-workspace.com"
DOMAIN = "nodes.example-workspace.com"
NODE = "a" * 24 + "." + DOMAIN
MOCK = '''import base64, hashlib, http.server, json, threading
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self): self.respond()
    def do_POST(self): self.respond()
    def respond(self):
        if self.headers.get('Upgrade', '').lower() == 'websocket':
            key = self.headers['Sec-WebSocket-Key']
            accept = base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            self.send_response(101)
            self.send_header('Upgrade', 'websocket')
            self.send_header('Connection', 'upgrade')
            self.send_header('Sec-WebSocket-Accept', accept)
            self.send_header('X-Test-Upstream-Host', self.headers.get('Host', ''))
            self.end_headers()
            self.close_connection = True
            return
        size = int(self.headers.get('Content-Length', '0'))
        if size: self.rfile.read(size)
        data = json.dumps({'headers': dict(self.headers), 'peer': self.client_address[0]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError): pass
for port in (3000, 8080, 8090):
    server = http.server.ThreadingHTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
threading.Event().wait()
'''


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or f"Command failed: {args[0]}")
    return result.stdout.strip()


def mount(source: Path, target: str) -> str:
    return f"type=bind,source={source.resolve()},target={target},readonly"


def tls_connection(port: int, sni: str, host: str | None = None) -> http.client.HTTPConnection:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # These certificates are synthetic and self-signed.
    connection = http.client.HTTPConnection(host or sni, port, timeout=5)
    connection.sock = context.wrap_socket(socket.create_connection(("127.0.0.1", port), timeout=5), server_hostname=sni)
    return connection


def request(port: int, host: str, path: str, method: str = "GET", headers=None, body=None):
    connection = tls_connection(port, host)
    try:
        connection.request(method, path, body=body, headers={"Host": host, **(headers or {})})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def check(binary: str, nginx_image: str, python_image: str) -> list[str]:
    checks: list[str] = []
    suffix = uuid.uuid4().hex[:10]
    network, backend, nginx = (f"workspace-check-{suffix}-{name}" for name in ("net", "backend", "nginx"))
    public_network = f"workspace-check-{suffix}-public"
    scratch = ROOT / "tmp"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="workspace-ingress-", dir=scratch) as temporary:
        directory = Path(temporary).resolve()
        if not directory.is_relative_to(scratch.resolve()):
            raise RuntimeError("Refused temporary directory outside the workspace")
        cert = directory / "cert"
        cert.mkdir()
        request_config = cert / "openssl.cnf"
        request_config.write_text("[req]\ndistinguished_name=dn\n[dn]\n", encoding="utf-8")
        run(binary, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
            "-config", str(request_config),
            "-subj", "/CN=" + CONTROL,
            "-addext", f"subjectAltName=DNS:{CONTROL},DNS:*.{DOMAIN},DNS:agent-communication.online",
            "-keyout", str(cert / "privkey.pem"), "-out", str(cert / "fullchain.pem"))
        values = {
            "WORKSPACE_GATEWAY_DOMAIN": DOMAIN, "WORKSPACE_GATEWAY_CONTROL_HOST": CONTROL,
            "WORKSPACE_GATEWAY_PUBLIC_URL": "https://" + CONTROL,
            "NEXTAUTH_URL": "https://agent-communication.online", "WORKSPACE_GATEWAY_SECRET": "a" * 64,
            "WORKSPACE_CONTROL_CERT_DIR": str(cert), "WORKSPACE_NODE_CERT_DIR": str(cert),
            "WORKSPACE_INGRESS_SUBNET": "172.30.81.0/29", "WORKSPACE_INGRESS_NGINX_IP": "172.30.81.2",
            "WORKSPACE_INGRESS_GATEWAY_IP": "172.30.81.3",
        }
        config = render(values, directory / "config", binary)
        (directory / "mock.py").write_text(MOCK, encoding="utf-8", newline="\n")
        try:
            run("docker", "network", "create", "--internal", "--subnet", "172.30.81.0/29", network)
            run("docker", "network", "create", public_network)
            run("docker", "run", "--pull", "never", "-d", "--name", backend, "--network", network,
                "--ip", "172.30.81.3", "--network-alias", "workspace-ingress-upstream",
                "--network-alias", "web", "--network-alias", "platform",
                "--mount", mount(directory / "mock.py", "/test/mock.py"),
                python_image, "python", "/test/mock.py")
            run("docker", "create", "--pull", "never", "--name", nginx, "--network", public_network,
                "-p", "127.0.0.1::443", "-p", "127.0.0.1::80",
                "--mount", mount(ROOT / "deploy/nginx/nginx.conf", "/etc/nginx/nginx.conf"),
                "--mount", mount(ROOT / "deploy/nginx/docs-source.conf", "/etc/nginx/docs-source.conf"),
                "--mount", mount(config, "/etc/nginx/workspace-enabled"),
                "--mount", mount(cert, "/etc/nginx/workspace-tls/control"),
                "--mount", mount(cert, "/etc/nginx/workspace-tls/node"),
                "--mount", mount(cert, "/etc/letsencrypt/live/agent-communication.online"), nginx_image)
            run("docker", "network", "connect", "--ip", "172.30.81.2", network, nginx)
            run("docker", "start", nginx)
            run("docker", "exec", nginx, "nginx", "-t")
            checks.append("production base nginx + optional workspace include parse")
            port = int(run("docker", "port", nginx, "443/tcp").rsplit(":", 1)[1])
            http_port = int(run("docker", "port", nginx, "80/tcp").rsplit(":", 1)[1])
            for attempt in range(30):
                try:
                    status, _, _ = request(port, CONTROL, "/v1/connector/state")
                    if status == 200:
                        break
                except (OSError, http.client.HTTPException):
                    pass
                time.sleep(0.2)
            else:
                raise AssertionError("Isolated nginx upstream did not become ready")
            assert request(port, "agent-communication.online", "/healthz")[0] == 200
            checks.append("existing portal HTTPS route remains available")
            assert request(port, CONTROL, "/v1/accounts/test/nodes", headers={"Authorization": "Bearer synthetic-secret"})[0] == 404
            assert request(port, CONTROL, "/health")[0] == 404
            assert request(port, CONTROL, "/v1/connector/state/extra")[0] == 404
            assert request(port, CONTROL, "/v1/connector/pairings")[0] == 405
            assert request(port, NODE, "/v1/accounts/test/nodes")[0] == 404
            checks.append("account BFF and non-allowlisted public control routes denied")
            status, headers, data = request(port, CONTROL, "/v1/connector/state", headers={
                "X-Real-IP": "198.51.100.1", "X-Forwarded-For": "198.51.100.2",
                "Forwarded": "for=198.51.100.3", "X-Forwarded-Host": "evil.example.com",
            })
            echo = json.loads(data)
            received = {name.lower(): value for name, value in echo["headers"].items()}
            assert status == 200 and received["host"] == CONTROL and echo["peer"] == "172.30.81.2"
            assert received["x-real-ip"] != "198.51.100.1"
            assert not any(name in received for name in ("forwarded", "x-forwarded-for", "x-forwarded-host"))
            checks.append("Host preserved; forged proxy headers stripped; exact ingress peer IP")
            status, headers, _ = request(port, CONTROL, "/v1/connector/tunnel", headers={
                "Upgrade": "websocket", "Connection": "upgrade", "Sec-WebSocket-Version": "13",
                "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
            })
            assert status == 101 and headers["X-Test-Upstream-Host"] == CONTROL
            checks.append("connector WebSocket upgrade forwarded")
            status, _, _ = request(port, NODE, "/ws/test", headers={
                "Upgrade": "websocket", "Connection": "upgrade", "Sec-WebSocket-Version": "13",
                "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
            })
            assert status == 101
            checks.append("node WebSocket upgrade forwarded")
            assert request(port, NODE, "/api/test", method="POST", body=b"x" * (2097152 + 1))[0] == 413
            checks.append("node body limit enforced by nginx")
            marker = "synthetic-launch-query-must-never-be-logged"
            status, headers, _ = request(port, NODE, "/_ambient/launch?ticket=" + marker)
            assert status == 200 and headers["Referrer-Policy"] == "no-referrer" and headers["Cache-Control"] == "no-store"
            logs = subprocess.run(["docker", "logs", nginx], capture_output=True, text=True, timeout=15)
            assert marker not in logs.stdout + logs.stderr
            checks.append("launch no-store/no-referrer and query absent from nginx logs")
            try:
                connection = tls_connection(port, "unknown.example-workspace.com")
            except ssl.SSLError:
                pass
            else:
                connection.close()
                raise AssertionError("Unknown SNI was accepted")
            connection = tls_connection(port, CONTROL)
            try:
                connection.request("GET", "/v1/connector/state", headers={"Host": "unknown.example-workspace.com"})
                connection.getresponse()
                raise AssertionError("Unknown HTTP Host was accepted on a valid TLS connection")
            except http.client.RemoteDisconnected:
                pass
            finally:
                connection.close()
            for host in (CONTROL, "unknown.example-workspace.com"):
                connection = http.client.HTTPConnection("127.0.0.1", http_port, timeout=5)
                try:
                    connection.request("GET", "/_ambient/launch?ticket=" + marker, headers={"Host": host})
                    connection.getresponse()
                    raise AssertionError("Workspace or unknown HTTP host was accepted")
                except http.client.RemoteDisconnected:
                    pass
                finally:
                    connection.close()
            checks.append("unknown TLS hosts and ordinary workspace HTTP rejected")
            responses = [request(port, CONTROL, "/v1/connector/pairings", method="POST", body=b"{}") for _ in range(10)]
            statuses = [response[0] for response in responses]
            assert 200 in statuses and 429 in statuses
            assert all(headers.get("Retry-After") == "60" for status, headers, _ in responses if status == 429)
            checks.append("anonymous pairing rate limit and 429 Retry-After enforced")
            return checks
        finally:
            for name in (nginx, backend):
                run("docker", "rm", "-f", name, check=False)
            run("docker", "network", "rm", network, check=False)
            run("docker", "network", "rm", public_network, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openssl", default=shutil.which("openssl"))
    parser.add_argument("--nginx-image", default=NGINX_IMAGE)
    parser.add_argument("--python-image", default="python:3.12-slim")
    args = parser.parse_args()
    if not args.openssl:
        parser.error("OpenSSL is required; specify --openssl PATH")
    for name in check(args.openssl, args.nginx_image, args.python_image):
        print("PASS " + name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
