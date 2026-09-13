"""Exercise retired entry points without installing packages or invoking a helper."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
PROBE = r'''
import os
import runpy
import sys

def forbid_side_effects(event, args):
    if event.startswith(("socket.", "subprocess.")) or event in (
        "os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.system",
        "os.chmod", "os.link", "os.symlink", "shutil.copyfile",
    ):
        raise RuntimeError("forbidden legacy side effect: " + event)
    if event == "open":
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        ):
            raise RuntimeError("forbidden legacy file write")

sys.addaudithook(forbid_side_effects)
action, package = sys.argv[1:]
if action == "install":
    script = os.path.join(package, "setup.py")
    sys.argv = [script, "install", "--user"]
    runpy.run_path(script, run_name="__main__")
elif action == "import":
    sys.path.insert(0, package)
    import hermes_platform_agent_comm
elif action == "direct":
    runpy.run_path(os.path.join(package, "hermes_platform_agent_comm", "platform.py"))
'''


def snapshot(directory):
    return {
        str(path.relative_to(directory)): None if path.is_dir() else path.read_bytes()
        for path in directory.rglob("*")
    }


class RetiredConnectorTest(unittest.TestCase):
    def test_old_install_and_imports_cannot_touch_profile_or_identity(self):
        for action in ("install", "import", "direct"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                (directory / "config.yaml").write_text("preserve: profile-configuration\n")
                (directory / "keys").mkdir()
                (directory / "keys" / "identity.fixture").write_text("existing-identity-fixture")
                (directory / "keys" / "mailbox.fixture").write_text("existing-message-state")
                before = snapshot(directory)
                environment = dict(os.environ, HOME=temporary, USERPROFILE=temporary, HERMES_HOME=temporary)
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", PROBE, action, str(PACKAGE)],
                    cwd=directory, env=environment, text=True, capture_output=True, timeout=10,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("RETIRED", result.stderr)
                self.assertIn("connectors/hermes-platform", result.stderr)
                self.assertIn("http://127.0.0.1:45042", result.stderr)
                self.assertNotIn("forbidden legacy", result.stderr)
                self.assertEqual(snapshot(directory), before)


if __name__ == "__main__":
    unittest.main()
