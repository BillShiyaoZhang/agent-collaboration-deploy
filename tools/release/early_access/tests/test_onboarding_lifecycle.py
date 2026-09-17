"""Isolated onboarding process/retry checks; no real Hermes/profile is changed."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import onboard_hermes as onboarding


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="onboarding-lifecycle-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def test_launcher_is_read_without_evaluating_shell(self):
        python = self.home / "venv/bin/python"
        python.parent.mkdir(parents=True)
        python.touch()
        launcher = self.home / "hermes"
        launcher.write_text(f'#!/usr/bin/env bash\nunset PYTHONPATH\nexec "{python}" "/host/hermes" "$@"\n')
        self.assertEqual(onboarding.launcher_interpreters(launcher)[0], str(python))

    def test_background_process_outlives_installer_terminal_and_has_profile(self):
        with patch.object(onboarding.subprocess, "Popen") as popen, \
             patch.dict(os.environ, {"PYTHONHOME": "/wrong", "PYTHONPATH": "/wrong", "HERMES_HOME": "/wrong"}):
            onboarding.detached(["python", "worker"], self.home / "logs/worker.log", home=self.home)
        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertTrue(kwargs["close_fds"])
        self.assertEqual(kwargs["env"]["HERMES_HOME"], str(self.home))
        self.assertNotIn("PYTHONHOME", kwargs["env"])
        self.assertNotIn("PYTHONPATH", kwargs["env"])
        if os.name != "nt":
            self.assertTrue(kwargs["start_new_session"])

    def test_native_start_exit_zero_without_gateway_uses_detached_runtime(self):
        source = self.home / "source"
        source.mkdir()
        (source / "hermes").touch()
        status = types.ModuleType("gateway.status")
        status.get_running_pid = lambda *args, **kwargs: None
        with patch.object(onboarding, "live_gateway_pid", return_value=None), \
             patch.object(onboarding.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, \
             patch.object(onboarding, "detached") as detached, \
             patch.object(onboarding, "gateway_connected", return_value=True), \
             patch.object(onboarding.time, "sleep"):
            onboarding.ensure_gateway(self.home, source)
        self.assertEqual(run.call_args.args[0], [sys.executable, str(source / "hermes"), "gateway", "start"])
        self.assertEqual(detached.call_args.args[0], [sys.executable, str(source / "hermes"), "gateway", "run"])

    def state(self):
        return {"status": "pending", "home": str(self.home), "source": str(self.home),
                "platform": "https://agents.example.org", "agent_urn": "urn:agent-comm:agent:test",
                "request_id": "11111111-2222-3333-4444-555555555555", "poll_secret": "private-poll-secret",
                "ticket_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()}

    def test_approved_grant_survives_gateway_failure_and_ack_response_loss(self):
        path = self.home / "onboarding.json"
        state = self.state()
        onboarding.private_json(path, state)
        response = {"status": "approved", "grant": "signed-grant"}
        grant = {"console_urn": "urn:hermes:agent:owner"}
        saved_before_retry = []

        def complete(current, approved, checkpoint):
            saved_before_retry.append(json.loads(path.read_text()))
            if len(saved_before_retry) == 1:
                raise RuntimeError("temporary gateway startup failure")

        with patch.object(onboarding, "ensure_hermes"), \
             patch.object(onboarding, "verify_grant", return_value=grant), \
             patch.object(onboarding, "complete_pairing", side_effect=complete), \
             patch.object(onboarding, "request_json", side_effect=[response, URLError("response lost"), {"status": "completed"}]) as request, \
             patch.object(onboarding.time, "sleep"), redirect_stdout(io.StringIO()) as output:
            onboarding.poll_pairing(path)
        result = json.loads(path.read_text())
        self.assertEqual(result["status"], "connected")
        self.assertFalse(result["web_ack_pending"])
        self.assertEqual(len(saved_before_retry), 2)
        self.assertEqual(saved_before_retry[0]["status"], "approved")
        self.assertEqual(saved_before_retry[0]["approval"], response)
        self.assertEqual(request.call_count, 3)
        self.assertNotIn("private-poll-secret", output.getvalue())
        if os.name != "nt":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_resume_connected_state_retries_unacknowledged_completion(self):
        path = self.home / "onboarding.json"
        state = {**self.state(), "status": "connected", "web_ack_pending": True}
        onboarding.private_json(path, state)
        with patch.object(onboarding, "ensure_hermes"), \
             patch.object(onboarding, "request_json", return_value={"status": "completed"}) as request, \
             patch.object(onboarding, "complete_pairing") as complete:
            onboarding.poll_pairing(path)
        self.assertFalse(json.loads(path.read_text())["web_ack_pending"])
        self.assertEqual(request.call_args.kwargs["body"], {"status": "completed"})
        complete.assert_not_called()

    def test_changed_helper_port_is_rejected_without_starting_another_helper(self):
        (self.home / "agent-comm-helper").touch()
        previous = {"agent_urn": "urn:agent-comm:agent:test", "port": 45042}
        with patch.object(onboarding, "run_json", return_value={"urn": previous["agent_urn"]}), \
             patch.object(onboarding, "start_helper_supervisor") as start:
            with self.assertRaisesRegex(ValueError, "already owns a helper port"):
                onboarding.ensure_helper(self.home, self.home, "https://agents.example.org", previous, 45043)
        start.assert_not_called()

    def test_gateway_retry_cannot_restore_a_revoked_pairing(self):
        import configure_hermes
        state = {**self.state(), "helper_url": "http://127.0.0.1:45042", "allow_web_actions": False,
                 "local_pair_installed": True}
        grant = {"console_urn": "urn:hermes:agent:owner", "expires_at": "2099-01-01T00:00:00Z"}
        with patch.object(onboarding, "pairing_matches", return_value=False), \
             patch.object(configure_hermes, "main") as configure, \
             patch.object(onboarding, "ensure_gateway") as gateway:
            with self.assertRaisesRegex(ValueError, "revoked or changed"):
                onboarding.complete_pairing(state, grant)
        configure.assert_not_called()
        gateway.assert_not_called()


if __name__ == "__main__":
    unittest.main()
