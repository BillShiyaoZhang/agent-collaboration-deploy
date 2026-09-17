"""Real Ed25519 verification of the exact grant requested by this installation.

These tests do not load a Hermes profile, start services, or contact a server.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SCRIPTS = Path(__file__).resolve().parents[1]
WORKSPACE = SCRIPTS.parents[2]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(WORKSPACE / "agent-comm-platform" / "agent-comm" / "python"))
import onboard_hermes


class TestOnboardingGrant(unittest.TestCase):
    NOW = 1893456000
    # RFC 8032 test-vector key, with its Agent Comm SHA-256/base58 fingerprint.
    SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    PUBLIC = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
    CONSOLE = "urn:hermes:agent:5CThzzdZPTPGPuLz6gwdFk"

    def setUp(self):
        self.key = Ed25519PrivateKey.from_private_bytes(self.SEED)
        self.state = {
            "request_id": "13eaa06f-c89a-4841-9e8e-7b4d40d92ee6",
            "agent_urn": "urn:agent-comm:agent:local-test-identity",
            "methods": ["capabilities", "conversation.send", "conversation.get"],
            "expires_at": datetime.fromtimestamp(self.NOW + 3600, timezone.utc).isoformat(),
        }
        self.grant = {"protocol": onboard_hermes.PROTOCOL, **deepcopy(self.state), "console_urn": self.CONSOLE}
        self.clock = patch.object(onboard_hermes.time, "time", return_value=self.NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def signed(self, grant=None, key=None):
        key = key or self.key
        raw = json.dumps(self.grant if grant is None else grant, ensure_ascii=False, separators=(",", ":"))
        public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return {"status": "approved", "grant": raw, "public_key": public.hex(), "signature": key.sign(raw.encode()).hex()}

    def test_exact_signed_grant_accepts_known_console_key_without_mutating_request(self):
        before = deepcopy(self.state)
        response = self.signed()
        self.assertEqual(response["public_key"], self.PUBLIC)
        self.assertEqual(onboard_hermes.verify_grant(response, self.state), self.grant)
        self.assertEqual(self.state, before)

    def test_even_a_valid_console_signature_cannot_change_requested_fields(self):
        changes = {
            "protocol": "agent-comm-onboarding/v2",
            "request_id": "4b820bdd-57a7-473a-9b20-98a692699fcf",
            "agent_urn": "urn:agent-comm:agent:another-agent",
            "methods": [*self.state["methods"], "collaboration.execute"],
            "expires_at": datetime.fromtimestamp(self.NOW + 7200, timezone.utc).isoformat(),
        }
        for field, value in changes.items():
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "changed the requested " + field):
                onboard_hermes.verify_grant(self.signed({**self.grant, field: value}), self.state)

    def test_missing_or_reordered_requested_methods_are_not_silently_substituted(self):
        for methods in ([], self.state["methods"][:1], list(reversed(self.state["methods"]))):
            with self.subTest(methods=methods), self.assertRaisesRegex(ValueError, "methods"):
                onboard_hermes.verify_grant(self.signed({**self.grant, "methods": methods}), self.state)
        for field in ("protocol", "request_id", "agent_urn", "methods", "expires_at"):
            grant = {key: value for key, value in self.grant.items() if key != field}
            with self.subTest(missing=field), self.assertRaises(ValueError):
                onboard_hermes.verify_grant(self.signed(grant), self.state)

    def test_valid_signature_does_not_authorize_a_different_console_urn(self):
        grant = {**self.grant, "console_urn": "urn:hermes:agent:some-other-console"}
        with self.assertRaisesRegex(ValueError, "Console identity"):
            onboard_hermes.verify_grant(self.signed(grant), self.state)
        for console in (None, "", "Hermes owner"):
            with self.subTest(console=console), self.assertRaises(ValueError):
                onboard_hermes.verify_grant(self.signed({**self.grant, "console_urn": console}), self.state)

    def test_replacing_the_signing_key_cannot_impersonate_the_claimed_console(self):
        other = Ed25519PrivateKey.generate()
        # A cryptographically valid signature from another key still has the
        # wrong identity, even if every requested field is unchanged.
        with self.assertRaisesRegex(ValueError, "Console identity"):
            onboard_hermes.verify_grant(self.signed(key=other), self.state)
        response = self.signed()
        response["public_key"] = other.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        with self.assertRaises(InvalidSignature):
            onboard_hermes.verify_grant(response, self.state)

    def test_tampering_with_exact_grant_bytes_or_signature_is_rejected(self):
        response = self.signed()
        response["grant"] += " "
        with self.assertRaises(InvalidSignature):
            onboard_hermes.verify_grant(response, self.state)
        response = self.signed()
        response["signature"] = ("00" if response["signature"][:2] != "00" else "01") + response["signature"][2:]
        with self.assertRaises(InvalidSignature):
            onboard_hermes.verify_grant(response, self.state)
        for field, value in (("public_key", "00" * 31), ("signature", "00" * 63), ("signature", "not-hex")):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                onboard_hermes.verify_grant({**self.signed(), field: value}, self.state)

    def test_expired_grant_is_rejected_even_when_it_exactly_matches_local_request(self):
        for expiry in (self.NOW - 1, self.NOW):
            state = {**self.state, "expires_at": datetime.fromtimestamp(expiry, timezone.utc).isoformat()}
            grant = {**self.grant, "expires_at": state["expires_at"]}
            with self.subTest(expiry=expiry), self.assertRaisesRegex(ValueError, "expired"):
                onboard_hermes.verify_grant(self.signed(grant), state)


if __name__ == "__main__":
    unittest.main()
