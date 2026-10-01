"""Run real NextAuth/BFF + Gateway HTTPS smoke using fresh loopback state only.

Build agent-collaboration-web first. The Gateway Python must already have its
requirements installed; this launcher never installs packages or loads dotenv.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "agent-collaboration-web"
GATEWAY = ROOT / "workspace-gateway"
WINDOWS_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def clean_environment() -> dict[str, str]:
    # Keep OS/runtime paths, never inherited service URLs, identities or credentials.
    allowed = {"PATH", "PATHEXT", "SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
               "TMPDIR", "COMSPEC", "LANG", "LC_ALL"}
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment.update({"PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1",
                        "NEXT_TELEMETRY_DISABLED": "1", "NODE_ENV": "production"})
    return environment


def free_ports(count: int) -> list[int]:
    sockets = []
    try:
        for _ in range(count):
            handle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            handle.bind(("127.0.0.1", 0))
            sockets.append(handle)
        return [handle.getsockname()[1] for handle in sockets]
    finally:
        for handle in sockets:
            handle.close()


def start_process(command: list[str], *, cwd: Path, environment: dict[str, str], capture: bool = True) -> subprocess.Popen:
    return subprocess.Popen(command, cwd=cwd, env=environment,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", creationflags=WINDOWS_FLAGS,
                            start_new_session=os.name != "nt")


def read_lines(process: subprocess.Popen) -> queue.Queue:
    lines: queue.Queue = queue.Queue(maxsize=128)
    def offer(line: str | None) -> None:
        try:
            lines.put_nowait(line)
        except queue.Full:
            try:
                lines.get_nowait()
            except queue.Empty:
                pass
            try:
                lines.put_nowait(line)
            except queue.Full:
                pass
    def consume() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            # Logs remain bounded in memory and are never replayed, including READY.
            offer(line[:65536].rstrip())
        offer(None)
    threading.Thread(target=consume, daemon=True).start()
    return lines


def stop_process_tree(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        # The PID is from this launcher's Popen; /T includes its own Next child.
        subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=WINDOWS_FLAGS, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def http_status(url: str, headers: dict[str, str] | None = None) -> int:
    request = urllib.request.Request(url, headers=headers or {})
    # Avoid inherited HTTP proxy configuration; every URL is loopback.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=1) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def wait_gateway(process: subprocess.Popen, public_url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("isolated Gateway exited before readiness")
        try:
            if http_status(public_url + "/health") == 200:
                return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.1)
    raise RuntimeError("isolated Gateway readiness timed out")


def wait_portal(process: subprocess.Popen, lines: queue.Queue, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            line = lines.get(timeout=0.2)
        except queue.Empty:
            if process.poll() is not None:
                raise RuntimeError("isolated Portal exited before readiness")
            continue
        if line is None:
            raise RuntimeError("isolated Portal closed its output before readiness")
        if line.startswith("WORKSPACE_PORTAL_READY "):
            value = json.loads(line.split(" ", 1)[1])
            # The fixture suppresses the generated password in launcher mode.
            if "password" in value:
                raise RuntimeError("fixture failed to suppress its synthetic password")
            return value
        if line.startswith("Workspace portal fixture failed:"):
            raise RuntimeError("isolated Portal fixture startup failed")
    raise RuntimeError("isolated Portal readiness timed out")


def link_dependencies(destination: Path) -> None:
    source = (WEB / "node_modules").resolve()
    if os.name == "nt":
        # Junction creation uses constant argv and does not require symlink privileges.
        result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J",
                                 str(destination), str(source)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=WINDOWS_FLAGS, check=False)
        if result.returncode:
            raise RuntimeError("cannot create isolated Node dependency junction")
    else:
        destination.symlink_to(source, target_is_directory=True)


def assert_ports_closed(ports: list[int]) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        opened = []
        for port in ports:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
                connection.settimeout(0.2)
                if connection.connect_ex(("127.0.0.1", port)) == 0:
                    opened.append(port)
        if not opened:
            return
        time.sleep(0.1)
    raise RuntimeError("a self-created fixture listener did not stop")


def run(args: argparse.Namespace) -> None:
    for path in [WEB / ".next" / "BUILD_ID", WEB / "node_modules" / "next" / "dist" / "bin" / "next"]:
        if not path.is_file():
            raise RuntimeError("build Web and install its dependencies before running this smoke")
    environment = clean_environment()
    output = (WEB / "build" / "workspace-portal-preview").resolve()
    output.mkdir(parents=True, exist_ok=True)
    gateway_port, portal_port, next_port = free_ports(3)
    internal = f"http://127.0.0.1:{gateway_port}"
    public = f"http://localhost:{gateway_port}"
    portal = f"https://localhost:{portal_port}"
    gateway_process = portal_process = None
    dependencies = None
    with tempfile.TemporaryDirectory(prefix="https-gateway-smoke-", dir=output) as temporary:
        directory = Path(temporary).resolve()
        if not directory.is_relative_to(output) or directory == output:
            raise RuntimeError("fixture output escaped its intended temporary root")
        next_root = directory / "next-root"
        next_root.mkdir()
        # Copy only compiled output and public project metadata, never dotenv or state.
        shutil.copytree(WEB / ".next", next_root / ".next",
                        ignore=shutil.ignore_patterns("cache", "standalone"))
        for name in ["package.json", "next.config.js"]:
            shutil.copy2(WEB / name, next_root / name)
        # Next requires an app directory to recognize this compiled App Router project.
        (next_root / "src" / "app").mkdir(parents=True)
        dependencies = next_root / "node_modules"
        link_dependencies(dependencies)
        certificate, key = directory / "localhost.crt", directory / "localhost.key"
        openssl_config = directory / "openssl.cnf"
        openssl_config.write_text(
            "[req]\ndistinguished_name=dn\nx509_extensions=server\nprompt=no\n"
            "[dn]\nCN=localhost\n[server]\n"
            "subjectAltName=DNS:localhost,IP:127.0.0.1\n"
            "basicConstraints=critical,CA:TRUE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign\n"
            "extendedKeyUsage=serverAuth\n", encoding="ascii")
        try:
            openssl = subprocess.run([
                args.openssl, "req", "-x509", "-newkey", "rsa:2048", "-days", "1", "-nodes",
                "-keyout", str(key), "-out", str(certificate), "-config", str(openssl_config),
            ], env=environment, cwd=directory, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=WINDOWS_FLAGS, check=False)
            if openssl.returncode:
                raise RuntimeError("cannot generate isolated localhost TLS certificate")
            secret = secrets.token_hex(32)
            gateway_environment = {
                **environment, "PYTHONPATH": str(GATEWAY),
                "WORKSPACE_GATEWAY_DATABASE": str(directory / "gateway.sqlite3"),
                "WORKSPACE_GATEWAY_SECRET": secret,
                "WORKSPACE_GATEWAY_SCHEME": "http",
                "WORKSPACE_GATEWAY_DOMAIN": f"localhost:{gateway_port}",
                "WORKSPACE_GATEWAY_PUBLIC_URL": public,
                "WORKSPACE_GATEWAY_CONTROL_HOST": f"localhost:{gateway_port}",
                "WORKSPACE_GATEWAY_SERVICE_HOST": f"127.0.0.1:{gateway_port}",
                "WORKSPACE_GATEWAY_PORTAL_ORIGIN": portal,
            }
            gateway_process = start_process([
                args.gateway_python, "-m", "uvicorn", "workspace_gateway.app:create_app",
                "--factory", "--host", "127.0.0.1", "--port", str(gateway_port),
                "--no-access-log", "--log-level", "warning",
            ], cwd=GATEWAY, environment=gateway_environment, capture=False)
            wait_gateway(gateway_process, public, args.timeout)
            if http_status(internal + "/health") != 404:
                raise RuntimeError("internal service Host unexpectedly reached public control health")
            if http_status(internal + "/v1/metrics", {"Authorization": "Bearer " + secret}) != 200:
                raise RuntimeError("internal service Host could not reach authenticated metrics")
            fixture_environment = {
                **environment, "NODE_EXTRA_CA_CERTS": str(certificate),
                "WORKSPACE_GATEWAY_URL": internal,
                "WORKSPACE_GATEWAY_PUBLIC_URL": public,
                "WORKSPACE_GATEWAY_DOMAIN": f"localhost:{gateway_port}",
                "WORKSPACE_GATEWAY_SECRET": secret,
                "WORKSPACE_PORTAL_FIXTURE_PORT": str(portal_port),
                "WORKSPACE_PORTAL_FIXTURE_NEXT_PORT": str(next_port),
                "WORKSPACE_PORTAL_FIXTURE_TLS_CERT": str(certificate),
                "WORKSPACE_PORTAL_FIXTURE_TLS_KEY": str(key),
                "WORKSPACE_PORTAL_FIXTURE_NEXT_CWD": str(next_root),
                "WORKSPACE_PORTAL_FIXTURE_HIDE_PASSWORD": "1",
                "WORKSPACE_PORTAL_FIXTURE_DATABASE_PATH": str(directory / "portal.sqlite3"),
            }
            portal_process = start_process([args.node, str(WEB / "tests" / "integration" / "workspace-portal-fixture.cjs")],
                                           cwd=WEB, environment=fixture_environment)
            ready = wait_portal(portal_process, read_lines(portal_process), args.timeout)
            database = Path(ready["database"]).resolve()
            if not database.is_file() or not database.is_relative_to(output) or ready["url"] != portal:
                raise RuntimeError("Portal returned an unexpected fixture location")
            smoke = subprocess.run([
                args.node, str(WEB / "tests" / "integration" / "workspace-portal-smoke.cjs"),
            ], cwd=WEB, env={**fixture_environment, "WORKSPACE_PORTAL_FIXTURE_URL": portal,
                            "WORKSPACE_PORTAL_FIXTURE_DATABASE": str(database)},
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace", timeout=args.timeout,
                creationflags=WINDOWS_FLAGS, check=False)
            if smoke.returncode or "WORKSPACE_PORTAL_SMOKE_PASS " not in smoke.stdout:
                # Do not replay stdout; a future fixture may accidentally include credentials.
                raise RuntimeError(f"real Portal/Gateway smoke failed with exit code {smoke.returncode}")
        finally:
            stop_process_tree(portal_process)
            stop_process_tree(gateway_process)
            if dependencies is not None and dependencies.exists():
                # Unlink the newly-created junction itself, never traverse its source.
                if os.name == "nt":
                    dependencies.rmdir()
                else:
                    dependencies.unlink()
            assert_ports_closed([gateway_port, portal_port, next_port])
    print("WORKSPACE_PORTAL_GATEWAY_PASS real HTTPS NextAuth, internal BFF/public Connector Host separation, enrollment/replay, pending pagination, claim/local approval, account revocation/stale cookie; owned processes cleaned")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-python", default=sys.executable)
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument("--openssl", default=shutil.which("openssl") or "openssl")
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    if not 5 <= args.timeout <= 300:
        parser.error("--timeout must be within 5..300 seconds")
    try:
        run(args)
    except Exception as error:
        # Error descriptions only; no captured service output, token or password.
        print("WORKSPACE_PORTAL_GATEWAY_FAIL " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
