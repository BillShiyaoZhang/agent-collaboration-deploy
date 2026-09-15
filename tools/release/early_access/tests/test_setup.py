"""Setup scripts tested with a temporary fake Hermes host and HTTP helper.

No real profile or Python packages are modified. pip execution is recorded by a
mock; configuration and local pairing use real files under the temporary home.
"""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1]
WORKSPACE = SCRIPTS.parents[2]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(WORKSPACE / "agent-comm-platform" / "agent-comm" / "python"))
import install
import configure_hermes
from agent_comm_runtime.remote import RemoteBridge, hermes_principal

TEST_PACKAGES = {"agent-comm-runtime": "0.1.0", "hermes-platform-agent-comm": "1.3.0"}


class TestBundleInstaller(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bundle-setup-")
        self.root = Path(self.temp.name)
        (self.root / "wheels").mkdir()
        for name in ("install.py", "configure_hermes.py"):
            shutil.copy2(SCRIPTS / name, self.root / name)
        (self.root / "README.md").write_text("test distribution", encoding="utf-8")
        (self.root / "agent-comm-helper.exe").write_bytes(b"verified test helper; never executed")
        for name, version in TEST_PACKAGES.items():
            base = name.replace("-", "_")
            wheel = self.root / "wheels" / f"{base}-{version}-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(f"{base}-{version}.dist-info/METADATA", f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\nRequires-Python: >=3.11\n")
        self.manifest()

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self):
        files = {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in self.root.rglob("*") if path.is_file() and path.name != "SHA256SUMS.json"}
        (self.root / "SHA256SUMS.json").write_text(json.dumps({"packages": TEST_PACKAGES, "files": files}), encoding="utf-8")
        return files

    def test_check_only_verifies_without_hermes_or_pip(self):
        with patch.object(install, "ensure_hermes", side_effect=AssertionError("must not inspect Hermes")), \
             patch.object(install.subprocess, "run") as run, redirect_stdout(io.StringIO()):
            self.assertEqual(install.main(["--bundle-dir", str(self.root), "--check-only"]), 0)
        run.assert_not_called()

    def test_tampering_or_manifest_escape_never_reaches_installation(self):
        (self.root / "agent-comm-helper.exe").write_bytes(b"tampered")
        with patch.object(install.subprocess, "run") as run, redirect_stderr(io.StringIO()):
            self.assertEqual(install.main(["--bundle-dir", str(self.root)]), 2)
        run.assert_not_called()
        files = self.manifest()
        files["../outside.txt"] = "0" * 64
        (self.root / "SHA256SUMS.json").write_text(json.dumps({"packages": TEST_PACKAGES, "files": files}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "escapes"):
            install.verify_bundle(self.root)

    def test_unlisted_or_wrong_version_wheel_is_rejected(self):
        files = self.manifest()
        files.pop(next(key for key in files if key.endswith(".whl")))
        (self.root / "SHA256SUMS.json").write_text(json.dumps({"packages": TEST_PACKAGES, "files": files}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not covered"):
            install.verify_bundle(self.root)
        self.manifest()
        wheel = next((self.root / "wheels").glob("agent_comm_runtime*.whl"))
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("agent_comm_runtime-9.0.dist-info/METADATA", "Name: agent-comm-runtime\nVersion: 9.0\n")
        self.manifest()
        with self.assertRaisesRegex(ValueError, "Unexpected wheel"):
            install.verify_bundle(self.root)

    def test_wrong_python_fails_before_running_pip(self):
        with patch.object(install, "ensure_hermes", side_effect=RuntimeError("not Hermes")), \
             patch.object(install.subprocess, "run") as run, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(install.main(["--bundle-dir", str(self.root)]), 2)
        run.assert_not_called()

    def test_missing_or_incomplete_release_versions_are_rejected(self):
        files = self.manifest()
        for packages in (None, {"agent-comm-runtime": "0.1.0"}, {**TEST_PACKAGES, "unexpected-package": "1.0"}):
            with self.subTest(packages=packages):
                (self.root / "SHA256SUMS.json").write_text(json.dumps({"files": files, "packages": packages}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "package versions"):
                    install.verify_bundle(self.root)

    def test_installs_only_with_current_python_and_neutralizes_pip_target(self):
        fake_constants = type("Constants", (), {"__file__": str(self.root / "fake-hermes" / "hermes_constants.py")})
        with patch.object(install, "ensure_hermes", return_value=(fake_constants, None)), \
             patch.object(install.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, \
             patch.dict(os.environ, {"PIP_TARGET": str(self.root / "wrong-environment"), "PIP_USER": "1"}), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(install.main(["--bundle-dir", str(self.root)]), 0)
        invocation = run.call_args_list[0]
        command = invocation.args[0]
        self.assertEqual(command[:4], [sys.executable, "-m", "pip", "--isolated"])
        self.assertEqual(command[command.index("--prefix") + 1], str(Path(sys.prefix).resolve()))
        self.assertNotIn("PIP_TARGET", invocation.kwargs["env"])
        self.assertNotIn("PIP_USER", invocation.kwargs["env"])
        self.assertEqual(invocation.kwargs["env"]["PIP_CONFIG_FILE"], os.devnull)
        self.assertEqual(run.call_args_list[1].args[0][0], sys.executable)
        self.assertFalse((self.root / "wrong-environment").exists())


class TestConfigureHermes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fake-hermes-setup-")
        self.root = Path(self.temp.name)
        self.source = self.root / "fake-hermes"
        self.home = self.root / "profile"
        self.home.mkdir()
        for folder in ("hermes_cli", "gateway", "gateway/platforms"):
            directory = self.source / folder
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "__init__.py").write_text("", encoding="utf-8")
        (self.source / "gateway/platforms/base.py").write_text("# fake host contract", encoding="utf-8")
        (self.source / "hermes_constants.py").write_text(
            "import os\nfrom pathlib import Path\ndef get_hermes_home(): return Path(os.environ['HERMES_HOME'])\n", encoding="utf-8")
        (self.source / "hermes_cli/config.py").write_text('''
import os
from pathlib import Path
import yaml
from hermes_constants import get_hermes_home
def get_config_path(): return get_hermes_home() / "config.yaml"
def is_managed(): return False
def require_readable_config_before_write(path):
    if not path.exists(): return {}
    try: data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc: raise RuntimeError("Malformed config") from exc
    if data is None: return {}
    if not isinstance(data, dict): raise RuntimeError("Config root must be mapping")
    return data
def atomic_config_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".test-tmp")
    tmp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(tmp, path)
''', encoding="utf-8")
        self.saved_modules = {key: module for key, module in list(sys.modules.items())
                              if key == "hermes_constants" or key.startswith("hermes_cli") or key.startswith("gateway")}
        for key in self.saved_modules:
            sys.modules.pop(key)
        sys.path.insert(0, str(self.source))
        importlib.invalidate_caches()
        self.environment = patch.dict(os.environ, {"HERMES_HOME": str(self.home)})
        self.environment.start()
        self.requests = []
        requests = self.requests
        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler):
                requests.append(handler.path)
                body = json.dumps({"urn": "urn:hermes:agent:ExistingHelper123", "status": "running"}).encode()
                handler.send_response(200)
                handler.send_header("Content-Type", "application/json")
                handler.end_headers()
                handler.wfile.write(body)
            def log_message(self, *args): pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.original = {"model": "keep-current-model", "credentials": {"token": "never-print-this-secret"},
            "plugins": {"enabled": ["other_plugin"], "entries": {"other_plugin": {"settings": {"keep": True}}}},
            "platforms": {"telegram": {"enabled": True, "token": "${TELEGRAM_TOKEN}"},
                          "agent_comm": {"allow_from": ["urn:agent-comm:agent:OldPeer"],
                              "extra": {"state_path": "keep-receipts.sqlite3", "custom_setting": 42}}}}
        self.config_path = self.home / "config.yaml"
        self.config_path.write_text(json.dumps(self.original, ensure_ascii=False), encoding="utf-8")
        self.original_bytes = self.config_path.read_bytes()
        (self.home / "keys").mkdir()
        (self.home / "keys/private.key").write_bytes(b"preserve-key")
        (self.home / "mailbox.sqlite3").write_bytes(b"preserve-mailbox")
        (self.home / "collaboration.sqlite3").write_bytes(b"preserve-collaboration-db")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.environment.stop()
        sys.path.remove(str(self.source))
        for key in list(sys.modules):
            if key == "hermes_constants" or key.startswith("hermes_cli") or key.startswith("gateway"):
                sys.modules.pop(key)
        sys.modules.update(self.saved_modules)
        importlib.invalidate_caches()
        self.temp.cleanup()

    def run_configure(self, *args):
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as error:
            code = configure_hermes.main(["--helper-url", self.url, *args])
        self.assertNotIn("never-print-this-secret", output.getvalue() + error.getvalue())
        return code, output.getvalue(), error.getvalue()

    def read_config(self):
        return importlib.import_module("hermes_cli.config").require_readable_config_before_write(self.config_path)

    def test_real_get_home_contract_merge_backup_and_data_preservation(self):
        code, _, error = self.run_configure("--allow-peer", "urn:hermes:agent:ExistingWebPeer456")
        self.assertEqual(code, 0, error)
        config = self.read_config()
        self.assertEqual(config["model"], self.original["model"])
        self.assertEqual(config["credentials"], self.original["credentials"])
        self.assertEqual(config["platforms"]["telegram"], self.original["platforms"]["telegram"])
        self.assertEqual(config["plugins"]["entries"], self.original["plugins"]["entries"])
        self.assertEqual(config["plugins"]["enabled"], ["other_plugin", "agent_comm"])
        platform = config["platforms"]["agent_comm"]
        self.assertNotIn("allow_from", platform)
        self.assertEqual(platform["extra"]["allow_from"], ["urn:agent-comm:agent:OldPeer", "urn:hermes:agent:ExistingWebPeer456"])
        self.assertEqual(platform["extra"]["state_path"], "keep-receipts.sqlite3")
        self.assertEqual(platform["extra"]["urn"], "urn:hermes:agent:ExistingHelper123")
        self.assertTrue(platform["extra"]["collaboration_enabled"])
        self.assertEqual(list(self.home.glob("config.yaml.agent-comm-backup-*"))[0].read_bytes(), self.original_bytes)
        self.assertEqual((self.home / "keys/private.key").read_bytes(), b"preserve-key")
        self.assertEqual((self.home / "mailbox.sqlite3").read_bytes(), b"preserve-mailbox")
        self.assertEqual((self.home / "collaboration.sqlite3").read_bytes(), b"preserve-collaboration-db")
        self.assertEqual(self.requests, ["/info"])

    def test_check_only_pair_plan_has_no_configuration_or_pairing_side_effect(self):
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        code, output, error = self.run_configure("--remote", "--pair-console", "urn:hermes:agent:WebConsole123",
                                               "--expires", expires, "--check-only")
        self.assertEqual(code, 0, error)
        self.assertIn("conversation.send", output)
        self.assertEqual(self.config_path.read_bytes(), self.original_bytes)
        self.assertEqual(list(self.home.glob("config.yaml.agent-comm-backup-*")), [])
        self.assertFalse((self.home / "agent-comm").exists())

    def test_remote_alone_does_not_pair_but_explicit_console_does(self):
        self.assertEqual(self.run_configure("--remote")[0], 0)
        path = self.home / "agent-comm/remote.sqlite3"
        self.assertFalse(path.exists())
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        console = "urn:hermes:agent:WebConsole123"
        code, _, error = self.run_configure("--remote", "--pair-console", console, "--expires", expires)
        self.assertEqual(code, 0, error)
        bridge = RemoteBridge(path, None, "urn:hermes:agent:ExistingHelper123")
        try:
            pairing = bridge.pairings()[0]
            self.assertEqual(pairing["owner_principal"], hermes_principal(self.home))
            self.assertEqual(set(pairing["methods"]), set(configure_hermes.PAIR_METHODS))
            self.assertEqual(pairing["expires_at"], expires)
        finally:
            bridge.close()
        self.assertIn(console, self.read_config()["platforms"]["agent_comm"]["extra"]["allow_from"])

    def test_wildcards_invalid_pair_args_and_malformed_config_fail_closed(self):
        for args in [("--allow-peer", "*"), ("--pair-console", "urn:hermes:agent:WebConsole123"),
                     ("--remote", "--pair-console", "urn:hermes:agent:WebConsole123", "--expires", "2000-01-01T00:00:00Z")]:
            with self.subTest(args=args):
                self.assertEqual(self.run_configure(*args)[0], 2)
                self.assertEqual(self.config_path.read_bytes(), self.original_bytes)
        self.assertEqual(self.requests, [])
        self.config_path.write_text("plugins: [unterminated", encoding="utf-8")
        self.assertEqual(self.run_configure()[0], 2)
        self.assertEqual(self.config_path.read_text(encoding="utf-8"), "plugins: [unterminated")
        self.assertEqual(list(self.home.glob("config.yaml.agent-comm-backup-*")), [])

    def test_no_peer_does_not_create_wildcard_permission(self):
        self.config_path.write_text("{}", encoding="utf-8")
        code, output, error = self.run_configure()
        self.assertEqual(code, 0, error)
        self.assertIn("does not permit messages to arbitrary", output)
        self.assertEqual(self.read_config()["platforms"]["agent_comm"]["extra"]["allow_from"], [])

    def test_non_loopback_helper_is_rejected_before_network(self):
        for url in ["https://example.com", "http://127.0.0.1@evil.example", "http://127.0.0.1/?token=secret"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                configure_hermes.helper_info(url)
        self.assertEqual(self.requests, [])

    def test_source_install_is_found_only_next_to_current_hermes_interpreter(self):
        sys.path.remove(str(self.source))
        importlib.invalidate_caches()
        with patch.object(sys, "prefix", str(self.source / "venv")), \
             patch.object(sys, "executable", str(self.source / "venv/Scripts/python.exe")):
            constants, _ = install.ensure_hermes()
        self.assertEqual(Path(constants.__file__).resolve(), (self.source / "hermes_constants.py").resolve())
        self.assertEqual(constants.get_hermes_home(), self.home)


if __name__ == "__main__":
    unittest.main()
