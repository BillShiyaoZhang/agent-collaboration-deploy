"""Docker-backed ingress checks; uses isolated containers and no production data.

Run: python tests/integration/test_deployment_security.py
Requires Docker and the nginx:alpine image (Docker may pull it).
"""
import os
import json
from http.client import HTTPException
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]


def docker(*args, **kwargs):
    return subprocess.run(["docker", *args], text=True, capture_output=True, **kwargs)


class DeploymentSecurity(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("WEB_TEST_IMAGE"), "Set WEB_TEST_IMAGE to a locally built Web image")
    def test_web_drops_privileges_and_preserves_existing_volume(self):
        image = os.environ["WEB_TEST_IMAGE"]
        volume = "agent-security-" + uuid.uuid4().hex
        self.assertEqual(docker("volume", "create", volume).returncode, 0)
        container = None
        try:
            mount = f"type=volume,source={volume},target=/app/data"
            result = docker("run", "--rm", "--pull=never", "--mount", mount, "--entrypoint", "sh", image,
                            "-c", "printf retained > /app/data/ownership-marker; chmod 600 /app/data/ownership-marker")
            self.assertEqual(result.returncode, 0, result.stderr)
            result = docker("run", "--rm", "-d", "--pull=never", "--mount", mount, "-p", "127.0.0.1::3000",
                            "-e", "DATABASE_URL=file:/app/data/security.db",
                            "-e", "NEXTAUTH_SECRET=" + uuid.uuid4().hex + uuid.uuid4().hex,
                            "-e", "NEXTAUTH_URL=http://localhost:3000", "-e", "WORKSPACE_SYNC_DISABLED=1", image)
            self.assertEqual(result.returncode, 0, result.stderr)
            container = result.stdout.strip()
            port = docker("port", container, "3000").stdout.strip().split(":")[-1]
            opener = build_opener(ProxyHandler({}))
            for _ in range(60):
                try:
                    with opener.open("http://127.0.0.1:" + port + "/api/auth/session", timeout=2) as response:
                        self.assertEqual(json.loads(response.read()), {})
                    break
                except (OSError, HTTPException):
                    time.sleep(0.25)
            else:
                self.fail(docker("logs", container).stdout + docker("logs", container).stderr)
            process = docker("exec", container, "cat", "/proc/1/status")
            self.assertRegex(process.stdout, r"Uid:\s+1001\s+1001\s+1001\s+1001")
            self.assertRegex(process.stdout, r"Gid:\s+1001\s+1001\s+1001\s+1001")
            retained = docker("exec", "--user", "1001:1001", container, "cat", "/app/data/ownership-marker")
            self.assertEqual(retained.returncode, 0, retained.stderr)
            self.assertEqual(retained.stdout, "retained")
            database_owner = docker("exec", container, "stat", "-c", "%u:%g", "/app/data/security.db")
            self.assertEqual(database_owner.stdout.strip(), "1001:1001")
        finally:
            if container:
                docker("rm", "-f", container)
            docker("volume", "rm", volume)

    def test_compose_requires_each_deployment_secret_and_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = Path(folder) / "empty.env"
            empty.write_text("")
            env = dict(os.environ, NEXTAUTH_SECRET="test-secret-not-used-for-serving",
                       PLATFORM_ADMIN_TOKEN="test-admin-not-used-for-serving",
                       NEXTAUTH_URL="https://test.example.invalid")
            args = ("compose", "--env-file", str(empty), "-f", str(ROOT / "docker-compose.yml"), "config", "--quiet")
            result = docker(*args, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            for key in ("NEXTAUTH_SECRET", "PLATFORM_ADMIN_TOKEN", "NEXTAUTH_URL"):
                for value in (None, ""):
                    invalid = dict(env)
                    if value is None:
                        invalid.pop(key)
                    else:
                        invalid[key] = value
                    result = docker(*args, env=invalid)
                    self.assertNotEqual(result.returncode, 0, key)
                    self.assertIn(key, result.stderr)

    def test_nginx_enforces_limits_and_overwrites_forwarded_addresses(self):
        with tempfile.TemporaryDirectory() as folder:
            config = (ROOT / "deploy/nginx/nginx.conf").read_text(encoding="utf-8")
            # Keep the actual ingress locations/rules. Replace only TLS/listeners
            # and upstreams so the test needs no certificate or external service.
            config = config.replace("listen 80;", "listen 8081;")
            config = config.replace("listen 443 ssl http2;", "listen 8080;")
            config = re.sub(r"^\s*ssl_certificate(?:_key)?\s+[^;]+;", "", config, flags=re.M)
            config = config.replace("server web:3000;", "server 127.0.0.1:8088;")
            config = config.replace("server platform:8080;", "server 127.0.0.1:8088;")
            at = config.rfind("}")
            config = config[:at] + '''
    server {
        listen 8088;
        location / { return 200 "$http_x_real_ip|$http_x_forwarded_for"; }
    }
''' + config[at:]
            config_path = Path(folder) / "nginx.conf"
            config_path.write_text(config, encoding="utf-8")
            result = docker("run", "--rm", "-d", "-p", "127.0.0.1::8080", "-p", "127.0.0.1::8081",
                            "--mount", f"type=bind,source={config_path},target=/etc/nginx/nginx.conf,readonly",
                            os.environ.get("NGINX_TEST_IMAGE", "nginx:alpine"))
            self.assertEqual(result.returncode, 0, result.stderr)
            container = result.stdout.strip()
            try:
                result = docker("exec", container, "nginx", "-t")
                self.assertEqual(result.returncode, 0, result.stderr)
                port = docker("port", container, "8080").stdout.strip().split(":")[-1]
                base = "http://127.0.0.1:" + port
                opener = build_opener(ProxyHandler({}))

                def request(path, data=None, spoof="203.0.113.99"):
                    req = Request(base + path, data=data, headers={"X-Real-IP": spoof,
                                  "X-Forwarded-For": spoof, "Host": "agent-communication.online"})
                    try:
                        with opener.open(req, timeout=5) as response:
                            return response.status, response.read().decode()
                    except HTTPError as exc:
                        return exc.code, exc.read().decode()

                for _ in range(30):
                    try:
                        status, forwarded = request("/api/v1/registry/fixture")
                        break
                    except URLError:
                        time.sleep(0.1)
                else:
                    self.fail("nginx did not become ready")
                self.assertEqual(status, 200)
                self.assertNotIn("203.0.113.99", forwarded)
                self.assertEqual(*forwarded.split("|"))
                self.assertEqual(request("/api/auth/register", b"x" * 16385)[0], 413)
                self.assertEqual(request("/api/agents", b"x" * (1024 * 1024 + 1))[0], 413)
                statuses = [request("/api/auth/" + ("register/" if index % 2 else "callback/credentials"),
                                    b"{}", f"203.0.113.{index}")[0] for index in range(10)]
                self.assertIn(200, statuses)
                self.assertEqual(statuses[-1], 429, statuses)
                self.assertEqual(request("/api/auth/callback/credentials/extra", b"{}")[0], 429)
                self.assertEqual(request("/api/auth/csrf")[0], 200)
            finally:
                docker("rm", "-f", container)


if __name__ == "__main__":
    unittest.main()
