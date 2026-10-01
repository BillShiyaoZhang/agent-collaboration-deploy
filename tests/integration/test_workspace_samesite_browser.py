"""Run real HTTPS NextAuth + Gateway and an isolated Chromium sibling-origin probe.

Install/build Web and Gateway dependencies first. No production dotenv, account,
identity or browser profile is read. Playwright and browser binaries are supplied.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
from test_workspace_portal_gateway import (ROOT, WEB, GATEWAY, WINDOWS_FLAGS,
    clean_environment, free_ports, start_process, read_lines, stop_process_tree,
    wait_portal, link_dependencies, assert_ports_closed, http_status)


def run(args):
    if not (WEB / ".next/BUILD_ID").is_file():
        raise RuntimeError("Build Web before running the browser smoke")
    environment = clean_environment()
    output = (WEB / "build/workspace-portal-preview").resolve()
    output.mkdir(parents=True, exist_ok=True)
    gateway_port, portal_port, next_port, attack_port = free_ports(4)
    internal = f"http://127.0.0.1:{gateway_port}"
    control = f"gateway.workspace.example.com:{gateway_port}"
    portal = f"https://portal.example.com:{portal_port}"
    gateway_process = portal_process = browser_process = None
    dependencies = None
    with tempfile.TemporaryDirectory(prefix="samesite-browser-", dir=output) as temporary:
        directory = Path(temporary).resolve()
        if not directory.is_relative_to(output) or directory == output:
            raise RuntimeError("Unexpected fixture output directory")
        next_root = directory / "next-root"
        next_root.mkdir()
        shutil.copytree(WEB / ".next", next_root / ".next", ignore=shutil.ignore_patterns("cache", "standalone"))
        for name in ["package.json", "next.config.js"]:
            shutil.copy2(WEB / name, next_root / name)
        (next_root / "src/app").mkdir(parents=True)
        dependencies = next_root / "node_modules"
        link_dependencies(dependencies)
        certificate, key = directory / "fixture.crt", directory / "fixture.key"
        config = directory / "openssl.cnf"
        config.write_text("[req]\ndistinguished_name=dn\nx509_extensions=server\nprompt=no\n"
            "[dn]\nCN=portal.example.com\n[server]\n"
            "subjectAltName=DNS:localhost,DNS:portal.example.com,DNS:*.workspace.example.com,IP:127.0.0.1\n"
            "basicConstraints=critical,CA:TRUE\nkeyUsage=critical,digitalSignature,keyEncipherment,keyCertSign\n"
            "extendedKeyUsage=serverAuth\n", encoding="ascii")
        try:
            result = subprocess.run([args.openssl, "req", "-x509", "-newkey", "rsa:2048", "-days", "1", "-nodes",
                "-keyout", str(key), "-out", str(certificate), "-config", str(config)], cwd=directory,
                env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=WINDOWS_FLAGS)
            if result.returncode:
                raise RuntimeError("Cannot create synthetic fixture TLS certificate")
            secret = secrets.token_hex(32)
            gateway_environment = {**environment, "PYTHONPATH": str(GATEWAY),
                "WORKSPACE_GATEWAY_DATABASE": str(directory / "gateway.sqlite3"),
                "WORKSPACE_GATEWAY_SECRET": secret, "WORKSPACE_GATEWAY_SCHEME": "https",
                "WORKSPACE_GATEWAY_ORIGIN_MODE": "same-site-subdomains",
                "WORKSPACE_GATEWAY_DOMAIN": f"workspace.example.com:{attack_port}",
                "WORKSPACE_GATEWAY_CONTROL_HOST": control,
                "WORKSPACE_GATEWAY_SERVICE_HOST": f"127.0.0.1:{gateway_port}",
                "WORKSPACE_GATEWAY_PORTAL_ORIGIN": portal}
            gateway_process = start_process([args.gateway_python, "-m", "uvicorn", "workspace_gateway.app:create_app",
                "--factory", "--host", "127.0.0.1", "--port", str(gateway_port), "--no-access-log", "--log-level", "warning"],
                cwd=GATEWAY, environment=gateway_environment, capture=False)
            import time
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                if gateway_process.poll() is not None:
                    raise RuntimeError("Isolated Gateway exited")
                try:
                    if http_status(internal + "/health", {"Host": control}) == 200:
                        break
                except OSError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Isolated Gateway readiness timed out")
            fixture_environment = {**environment, "NODE_EXTRA_CA_CERTS": str(certificate),
                "WORKSPACE_GATEWAY_URL": internal, "WORKSPACE_GATEWAY_PUBLIC_URL": "https://" + control,
                "WORKSPACE_GATEWAY_DOMAIN": f"workspace.example.com:{attack_port}",
                "WORKSPACE_GATEWAY_SECRET": secret, "WORKSPACE_GATEWAY_ORIGIN_MODE": "same-site-subdomains",
                "WORKSPACE_PORTAL_FIXTURE_HOST": "portal.example.com",
                "WORKSPACE_PORTAL_FIXTURE_OUTPUT_DIR": str(directory),
                "WORKSPACE_PORTAL_FIXTURE_REQUEST_AUDIT_PATH": str(directory / "request-audit.jsonl"),
                "WORKSPACE_PORTAL_FIXTURE_PORT": str(portal_port), "WORKSPACE_PORTAL_FIXTURE_NEXT_PORT": str(next_port),
                "WORKSPACE_PORTAL_FIXTURE_TLS_CERT": str(certificate), "WORKSPACE_PORTAL_FIXTURE_TLS_KEY": str(key),
                "WORKSPACE_PORTAL_FIXTURE_NEXT_CWD": str(next_root), "WORKSPACE_PORTAL_FIXTURE_HIDE_PASSWORD": "1",
                "WORKSPACE_PORTAL_FIXTURE_DATABASE_PATH": str(directory / "portal.sqlite3")}
            portal_process = start_process([args.node, str(WEB / "tests/integration/workspace-portal-fixture.cjs")],
                cwd=WEB, environment=fixture_environment)
            ready = wait_portal(portal_process, read_lines(portal_process), args.timeout)
            database = Path(ready["database"]).resolve()
            if ready["url"] != portal or database.parent != directory:
                raise RuntimeError("Unexpected isolated Portal fixture metadata")
            import ssl, urllib.request
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=str(certificate))))
            with opener.open(urllib.request.Request(f"https://127.0.0.1:{portal_port}/login",
                    headers={"Host": f"portal.example.com:{portal_port}"}), timeout=10) as probe:
                if probe.status != 200: raise RuntimeError("Isolated TLS proxy did not serve login")
            browser_environment = {**fixture_environment, "WORKSPACE_PORTAL_FIXTURE_URL": portal,
                "WORKSPACE_PORTAL_FIXTURE_DATABASE": str(database),
                "WORKSPACE_BROWSER_ATTACK_PORT": str(attack_port),
                "WORKSPACE_BROWSER_PLAYWRIGHT_PACKAGE": str(args.playwright_package.resolve())}
            if args.browser_executable:
                browser_environment["WORKSPACE_BROWSER_EXECUTABLE"] = str(args.browser_executable.resolve())
            if args.browser_cache:
                browser_environment["PLAYWRIGHT_BROWSERS_PATH"] = str(args.browser_cache.resolve())
            browser_process = start_process([args.node, str(ROOT / "tests/integration/workspace_samesite_browser.cjs")],
                cwd=WEB, environment=browser_environment)
            try:
                browser_output, unused = browser_process.communicate(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                stop_process_tree(browser_process)
                raise RuntimeError("Real browser probe timed out; owned process tree stopped")
            if browser_process.returncode or "WORKSPACE_SAMESITE_BROWSER_PASS " not in browser_output:
                import re
                for line in browser_output.splitlines():
                    if line.startswith("Probe diagnostic "): print(line, file=sys.stderr)
                diagnostic = re.search(r"Pre-auth diagnostic: ([^\n]+)", browser_output)
                if diagnostic: print(diagnostic[0], file=sys.stderr)
                phase = re.search(r"WORKSPACE_SAMESITE_BROWSER_FAIL phase=([a-z-]+)", browser_output)
                raise RuntimeError("Real browser probe failed" + (" at " + phase[1] if phase else ""))
        finally:
            stop_process_tree(browser_process)
            stop_process_tree(portal_process)
            stop_process_tree(gateway_process)
            if dependencies is not None and dependencies.exists():
                dependencies.rmdir() if os.name == "nt" else dependencies.unlink()
            assert_ports_closed([gateway_port, portal_port, next_port, attack_port])
    print("WORKSPACE_SAMESITE_BROWSER_PASS real HTTPS NextAuth/BFF and Chromium sibling-origin protection; owned processes and temporary state cleaned")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-python", default=sys.executable)
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument("--openssl", default=shutil.which("openssl") or "openssl")
    parser.add_argument("--playwright-package", type=Path, required=True)
    parser.add_argument("--browser-cache", type=Path)
    parser.add_argument("--browser-executable", type=Path)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if not 5 <= args.timeout <= 300 or not args.playwright_package.is_file():
        parser.error("Supply an installed Playwright package.json and a timeout within 5..300 seconds")
    try:
        run(args)
    except Exception as error:
        print("WORKSPACE_SAMESITE_BROWSER_FAIL " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
