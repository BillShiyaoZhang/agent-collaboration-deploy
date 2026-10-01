from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("render_ingress", ROOT / "tools/workspace/render_ingress.py")
assert SPEC and SPEC.loader
ingress = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ingress)


def settings() -> dict[str, str]:
    return {
        "WORKSPACE_GATEWAY_DOMAIN": "nodes.example-workspace.com",
        "WORKSPACE_GATEWAY_CONTROL_HOST": "connect.example-workspace.com",
        "WORKSPACE_GATEWAY_PUBLIC_URL": "https://connect.example-workspace.com",
        "NEXTAUTH_URL": "https://agent-communication.online",
        "WORKSPACE_GATEWAY_SECRET": "a" * 64,
        "NEXTAUTH_SECRET": "b" * 64,
        "WORKSPACE_CONTROL_CERT_DIR": "/unused/control",
        "WORKSPACE_NODE_CERT_DIR": "/unused/node",
    }


class IngressPolicyTests(unittest.TestCase):
    def test_valid_separate_site_and_default_fixed_proxy_address(self):
        result = ingress.validate_settings(settings())
        self.assertEqual("172.30.80.2", result["NGINX_IP"])
        self.assertEqual("2097152", result["HTTP_BODY_LIMIT"])

    def test_rejects_shared_portal_registrable_site(self):
        values = settings()
        values.update(
            WORKSPACE_GATEWAY_DOMAIN="nodes.agent-communication.online",
            WORKSPACE_GATEWAY_CONTROL_HOST="connect.agent-communication.online",
            WORKSPACE_GATEWAY_PUBLIC_URL="https://connect.agent-communication.online",
        )
        with self.assertRaisesRegex(ValueError, "separate"):
            ingress.validate_settings(values)

    def test_same_site_mode_requires_exact_enum_and_distinct_hosts(self):
        values = settings()
        values.update(
            WORKSPACE_GATEWAY_ORIGIN_MODE="same-site-subdomains",
            WORKSPACE_GATEWAY_DOMAIN="nodes.workspace.agent-communication.online",
            WORKSPACE_GATEWAY_CONTROL_HOST="connect.workspace.agent-communication.online",
            WORKSPACE_GATEWAY_PUBLIC_URL="https://connect.workspace.agent-communication.online",
        )
        result = ingress.validate_settings(values)
        self.assertEqual("same-site-subdomains", result["ORIGIN_MODE"])
        self.assertEqual("https://agent-communication.online", result["PORTAL_ORIGIN"])
        for changed in (
            {"WORKSPACE_GATEWAY_ORIGIN_MODE": "false"},
            {"WORKSPACE_GATEWAY_ORIGIN_MODE": ""},
            {"NEXTAUTH_URL": "https://connect.workspace.agent-communication.online"},
            {"NEXTAUTH_URL": "https://portal.nodes.workspace.agent-communication.online"},
            {"NEXTAUTH_URL": "https://portal.example.com"},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                ingress.validate_settings({**values, **changed})

    def test_render_guard_exists_only_in_same_site_mode_and_is_removed_on_switch(self):
        values = settings()
        values.update(
            WORKSPACE_GATEWAY_ORIGIN_MODE="same-site-subdomains",
            WORKSPACE_GATEWAY_DOMAIN="nodes.workspace.agent-communication.online",
            WORKSPACE_GATEWAY_CONTROL_HOST="connect.workspace.agent-communication.online",
            WORKSPACE_GATEWAY_PUBLIC_URL="https://connect.workspace.agent-communication.online",
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "config"
            with patch.object(ingress, "validate_certificate"):
                ingress.render(values, output, "openssl")
            metadata = (output / "portal-workspace-metadata.conf").read_text()
            guard = (output / "portal-workspace-guard.inc").read_text()
            self.assertIn(r"https://agent\-communication\.online", metadata)
            self.assertIn("$workspace_portal_guard_denied", guard)
            self.assertNotIn("@@", metadata + guard)
            # Policy changes must not leave a stale same-site guard enabled.
            with patch.object(ingress, "validate_certificate"):
                ingress.render(settings(), output, "openssl")
            self.assertFalse((output / "portal-workspace-metadata.conf").exists())
            self.assertFalse((output / "portal-workspace-guard.inc").exists())
            self.assertTrue((output / "workspace.conf").exists())

    def test_handles_co_uk_and_private_suffixes(self):
        values = settings()
        values.update(
            WORKSPACE_GATEWAY_DOMAIN="nodes.workspace.co.uk",
            WORKSPACE_GATEWAY_CONTROL_HOST="connect.workspace.co.uk",
            WORKSPACE_GATEWAY_PUBLIC_URL="https://connect.workspace.co.uk",
            NEXTAUTH_URL="https://portal.portal.co.uk",
        )
        ingress.validate_settings(values)
        values.update(
            WORKSPACE_GATEWAY_DOMAIN="nodes.workspace.github.io",
            WORKSPACE_GATEWAY_CONTROL_HOST="connect.workspace.github.io",
            WORKSPACE_GATEWAY_PUBLIC_URL="https://connect.workspace.github.io",
            NEXTAUTH_URL="https://portal.github.io",
        )
        ingress.validate_settings(values)
        values["NEXTAUTH_URL"] = "https://portal.workspace.github.io"
        with self.assertRaises(ValueError):
            ingress.validate_settings(values)

    def test_capabilities_are_exact_get_on_control_host_without_private_route_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "config"
            with patch.object(ingress, "validate_certificate"):
                ingress.render(settings(), output, "openssl")
            text = (output / "workspace.conf").read_text(encoding="utf-8")
            control = text.split("server_name connect.example-workspace.com;", 1)[1].split("\nserver {", 1)[0]
            capability = control.split("location = /v1/connector/capabilities {", 1)[1].split("\n    }", 1)[0]
            self.assertIn('if ($request_method != GET) { return 405; }', capability)
            self.assertIn("limit_req zone=workspace_control", capability)
            self.assertIn("proxy_pass http://workspace_gateway;", capability)
            self.assertIn("location / { return 404; }", control)
            for private in ("/health", "/v1/metrics", "/v1/accounts"):
                self.assertNotIn("location = " + private, control)
            self.assertEqual(1, text.count("location = /v1/connector/capabilities {"))

    def test_unknown_suffix_is_rejected(self):
        values = settings()
        values["WORKSPACE_GATEWAY_DOMAIN"] = "nodes.workspace.not-a-real-tld"
        with self.assertRaises(ValueError):
            ingress.validate_settings(values)

    def test_rejects_mismatched_control_origin_and_node_site(self):
        for key, value in (
            ("WORKSPACE_GATEWAY_PUBLIC_URL", "https://other.example-workspace.com"),
            ("WORKSPACE_GATEWAY_PUBLIC_URL", "http://connect.example-workspace.com"),
            ("WORKSPACE_GATEWAY_PUBLIC_URL", "https://connect.example-workspace.com/path"),
            ("WORKSPACE_GATEWAY_CONTROL_HOST", "a" * 24 + ".nodes.example-workspace.com"),
            ("WORKSPACE_GATEWAY_DOMAIN", "nodes.different-workspace.com"),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                values = settings()
                values[key] = value
                ingress.validate_settings(values)

    def test_rejects_shared_secret_or_unusable_network_addresses(self):
        for key, value in (
            ("WORKSPACE_GATEWAY_SECRET", "b" * 64),
            ("WORKSPACE_GATEWAY_SECRET", "short"),
            ("WORKSPACE_INGRESS_NGINX_IP", "172.30.80.3"),
            ("WORKSPACE_INGRESS_NGINX_IP", "172.30.80.0"),
            ("WORKSPACE_INGRESS_GATEWAY_IP", "172.30.81.3"),
            ("WORKSPACE_INGRESS_SUBNET", "172.30.0.0/16"),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                values = settings()
                values[key] = value
                ingress.validate_settings(values)

    def test_render_preserves_nginx_variables_and_checks_tls_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "config"
            with patch.object(ingress, "validate_certificate", side_effect=ValueError("bad TLS")):
                with self.assertRaises(ValueError):
                    ingress.render(settings(), output, "openssl")
            self.assertFalse(output.exists())
            with patch.object(ingress, "validate_certificate") as cert:
                ingress.render(settings(), output, "openssl")
            self.assertEqual(2, cert.call_count)
            text = (output / "workspace.conf").read_text(encoding="utf-8")
            proxy = (output / "workspace-proxy.inc").read_text(encoding="utf-8")
            self.assertIn("$request_method", text)
            self.assertIn("proxy_set_header Host $host", proxy)
            self.assertIn("proxy_bind 172.30.80.2", proxy)
            self.assertNotIn("@@", text + proxy)

    def test_environment_reader_handles_quotes_and_process_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / ".env"
            source.write_text("A='x#y'\nB=one # comment\nexport C=two\n", encoding="utf-8")
            with patch.dict(os.environ, {"C": "process"}, clear=True):
                self.assertEqual({"A": "x#y", "B": "one", "C": "process"}, ingress.load_environment(source))

    def test_certificate_missing_or_external_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(OSError):
                ingress.validate_certificate(Path(directory), "control.example.com", "openssl")

    def test_certificate_requires_san_and_matching_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for name in ("fullchain.pem", "privkey.pem"):
                (path / name).write_text("placeholder", encoding="utf-8")
            responses = [b"", b"DNS:*.nodes.example-workspace.com", b"public", b"same", b"same"]
            with patch.object(ingress, "openssl_run", side_effect=responses):
                ingress.validate_certificate(path, "nodes.example-workspace.com", "openssl", wildcard=True)
            with patch.object(ingress, "openssl_run", side_effect=[b"", b"DNS:*.example-workspace.com"]):
                with self.assertRaisesRegex(ValueError, "SAN"):
                    ingress.validate_certificate(path, "nodes.example-workspace.com", "openssl", wildcard=True)
            responses = [b"", b"DNS:connect.example-workspace.com", b"public", b"one", b"two"]
            with patch.object(ingress, "openssl_run", side_effect=responses):
                with self.assertRaisesRegex(ValueError, "match"):
                    ingress.validate_certificate(path, "connect.example-workspace.com", "openssl")

    def test_openssl_error_does_not_echo_command_output(self):
        result = subprocess.CompletedProcess([], 1, b"private data", b"sensitive data")
        with patch.object(ingress.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(ValueError, "OpenSSL") as raised:
                ingress.openssl_run("openssl", "x509")
        self.assertNotIn("sensitive", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
