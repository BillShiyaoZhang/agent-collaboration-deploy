"""Release contracts exercised with isolated Git repositories and wheel files."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import build_early_access
import package_web_release
import release_common


class TestReleases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="release-tests-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def repository(self, path, files):
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "--quiet", str(path)], check=True, capture_output=True)
        release_common.git(path, "config", "core.autocrlf", "false")
        for name, data in files.items():
            target = path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data if isinstance(data, bytes) else data.encode())
        release_common.git(path, "add", ".")
        release_common.git(path, "-c", "user.name=Release Test", "-c", "user.email=release@example.invalid",
                           "-c", "commit.gpgsign=false", "-c", "core.hooksPath=disabled-hooks",
                           "commit", "--quiet", "-m", "fixture")
        return path

    def web_repositories(self):
        root = self.repository(self.root / "deploy", {
            ".gitignore": "agent-collaboration-web/\nagent-comm-platform/\nbuild/\n",
            "docker-compose.yml": "services: {}\n",
            "deploy/nginx/nginx.conf": "events {}\n",
            "deploy/nginx/docs-source.conf": "default_type text/plain;\n",
            "deploy/platform/config.yaml": "platform: {}\n",
            "docs/README.md": "# Deploy docs\n",
            "docs/releases/old.md": "Historical release record\n",
        })
        self.repository(root / "agent-collaboration-web", {
            "src/page.ts": "export const title = 'current';\n", ".env": "PRIVATE=excluded",
            ".env.example": "TOKEN=replace-me\n", ".env.local": "PRIVATE=excluded-too",
            "data/private.sqlite3": b"database", "keys/private.key": b"secret",
            "helper": b"\x7fELFbinary", "README.md": "web source\n",
            "docs/README.md": "# Web docs\n",
        })
        platform = self.repository(root / "agent-comm-platform", {
            ".gitignore": "agent-comm/\n", "docs/README.md": "# Platform docs\n",
        })
        self.repository(platform / "agent-comm", {"docs/README.md": "# SDK docs\n"})
        return root

    def test_snapshot_is_complete_private_assets_excluded_and_reproducible(self):
        root = self.web_repositories()
        output = root / "build/web.tar.gz"
        result = package_web_release.build_archive(root, output, "test-release")
        first = output.read_bytes()
        with tarfile.open(output) as archive:
            names = set(archive.getnames())
            self.assertEqual(names, {"web/src/page.ts", "web/README.md", "web/docs/README.md",
                                     "web/.env.example", "manifest.json", "docs/README.md",
                                     "docs/releases/old.md", "agent-comm-platform/docs/README.md",
                                     "agent-comm-platform/agent-comm/docs/README.md",
                                     *package_web_release.DEPLOY_FILES})
            self.assertEqual(archive.extractfile("web/.env.example").read(), b"TOKEN=replace-me\n")
            manifest = json.load(archive.extractfile("manifest.json"))
            self.assertEqual(manifest["mode"], "full_snapshot")
            self.assertNotIn("remove_web", manifest)
            for name, expected in manifest["files"].items():
                self.assertEqual(release_common.sha(archive.extractfile(name).read()), expected)
        self.assertEqual(result["source_heads"]["deploy"], release_common.repository_head(root))
        self.assertEqual(result["source_heads"]["platform"],
                         release_common.repository_head(root / "agent-comm-platform"))
        self.assertEqual(result["source_heads"]["sdk"],
                         release_common.repository_head(root / "agent-comm-platform/agent-comm"))
        package_web_release.build_archive(root, output, "test-release")
        self.assertEqual(first, output.read_bytes())

    def test_dirty_repository_and_uninitialized_submodule_are_rejected(self):
        root = self.repository(self.root / "repo", {"README.md": "source"})
        nested = root / "uninitialized"
        nested.mkdir()
        with self.assertRaisesRegex(ValueError, "exact repository"):
            release_common.repository_head(nested)
        (root / "untracked.txt").write_text("private draft")
        with self.assertRaisesRegex(ValueError, "committed and clean"):
            release_common.repository_head(root)
        (root / "untracked.txt").unlink()
        (root / "README.md").write_text("uncommitted edit")
        with self.assertRaisesRegex(ValueError, "committed and clean"):
            release_common.repository_head(root)

    def test_tracked_only_selection_does_not_publish_untracked_files(self):
        root = self.repository(self.root / "repo", {"README.md": "tracked"})
        (root / "draft.md").write_text("untracked")
        (root / "README.md").write_text("uncommitted tracked edit")
        self.assertEqual(dict(release_common.source_files(root)), {"README.md": b"tracked"})

    def packages(self, sdk):
        sources = (sdk / "python", sdk / "connectors/hermes-platform")
        versions = {"agent-comm-runtime": "2.0.4", "hermes-platform-agent-comm": "3.1.5"}
        for source, (name, version) in zip(sources, versions.items()):
            source.mkdir(parents=True)
            if source.name == "python":
                (source / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n')
            else:
                (source / "setup.py").write_text(f'raise RuntimeError("must not execute metadata")\nsetup(name="{name}", version="{version}")\n')
            package = name.replace("-", "_")
            (source / package).mkdir()
            (source / package / "__init__.py").write_bytes(b"# release fixture\n")
            (source / "dist").mkdir()
            with zipfile.ZipFile(source / "dist" / f"{package}-{version}-py3-none-any.whl", "w") as archive:
                archive.writestr(f"{package}/__init__.py", "# release fixture\n")
                archive.writestr(f"{package}-{version}.dist-info/METADATA", f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n")
        return sources, versions

    def test_project_metadata_drives_versions_and_wheel_source_is_verified(self):
        sources, versions = self.packages(self.root / "sdk")
        actual, wheels = build_early_access.release_packages(sources)
        self.assertEqual(actual, versions)
        self.assertEqual(build_early_access.verify_wheels(wheels, sources), 2)
        (sources[0] / "agent_comm_runtime/__init__.py").write_text("# changed after wheel build\n")
        with self.assertRaisesRegex(ValueError, "Wheel/source mismatch"):
            build_early_access.verify_wheels(wheels, sources)

    def test_bundle_build_without_pdf_uses_metadata_and_checks_all_platforms(self):
        root = self.repository(self.root / "deploy", {
            ".gitignore": "agent-collaboration-web/\nagent-comm-platform/\nbuild/\ndownloads/\n",
            "README.md": "deploy fixture",
        })
        self.repository(root / "agent-collaboration-web", {"README.md": "web fixture"})
        platform = self.repository(root / "agent-comm-platform", {".gitignore": "agent-comm/\n", "README.md": "platform"})
        sdk = platform / "agent-comm"
        sources, versions = self.packages(sdk)
        self.repository(sdk, {".gitignore": "dist/\n"})
        helpers = root / "build/helpers"
        helpers.mkdir(parents=True)
        trust_path = root / "build/policy-trust.json"
        trust_path.write_text(json.dumps({"schema_version": 1, "release": "fixture",
                                          "platform_origin": "https://agents.example.org",
                                          "platform_peer_id": "12D3KooW" + "A" * 45,
                                          "policy_root_public_key_hex": "a" * 64,
                                          "verification_note": "Independent fixture key review"}), encoding="utf-8")
        for binary, _ in build_early_access.VARIANTS.values():
            (helpers / binary).write_bytes(f"fixture {binary}; never executed".encode())
        packages = build_early_access.release_packages
        verify = build_early_access.verify_wheels
        with patch.object(build_early_access, "ROOT", root), patch.object(build_early_access, "SDK", sdk), \
             patch.object(build_early_access, "release_packages", side_effect=lambda: packages(sources)), \
             patch.object(build_early_access, "verify_wheels", side_effect=lambda wheels: verify(wheels, sources)), \
             contextlib.redirect_stdout(io.StringIO()):
            build_early_access.main(["--release", "fixture", "--helper-dir", str(helpers),
                                     "--policy-trust", str(trust_path)])
        report = json.loads((root / "downloads/release-manifest.json").read_text())
        self.assertEqual(report["packages"], versions)
        self.assertEqual(len(report["files"]), len(build_early_access.VARIANTS) + 1)
        self.assertFalse(any(name.endswith(".pdf") for name in report["files"]))
        for platform_name, (binary, packaged_name) in build_early_access.VARIANTS.items():
            with self.subTest(platform=platform_name), zipfile.ZipFile(
                    root / f"downloads/agent-comm-early-access-{platform_name}.zip") as archive:
                manifest = json.loads(archive.read("SHA256SUMS.json"))
                self.assertEqual(manifest["packages"], versions)
                self.assertEqual(manifest["platform"], platform_name)
                self.assertIn("onboard_hermes.py", manifest["files"])
                self.assertIn("policy-trust.json", manifest["files"])
                self.assertEqual(archive.read("policy-trust.json"), trust_path.read_bytes())
                self.assertEqual(json.loads(archive.read("policy-trust.json"))["policy_root_public_key_hex"], "a" * 64)
                self.assertIn(b"def verify_grant", archive.read("onboard_hermes.py"))
                self.assertEqual(archive.read(packaged_name), (helpers / binary).read_bytes())
                self.assertEqual((archive.getinfo(packaged_name).external_attr >> 16) & 0o777, 0o755)
        trust_path.write_text(json.dumps({"schema_version": 1, "release": "fixture",
                                          "platform_origin": "https://agents.example.org",
                                          "platform_peer_id": "12D3KooW" + "A" * 45,
                                          "policy_root_public_key_hex": "a" * 64,
                                          "policy_root_private_key_hex": "b" * 64,
                                          "verification_note": "Independent fixture key review"}), encoding="utf-8")
        rejected = root / "build/rejected-release"
        with patch.object(build_early_access, "ROOT", root), patch.object(build_early_access, "SDK", sdk), \
             patch.object(build_early_access, "release_packages", side_effect=lambda: packages(sources)), \
             patch.object(build_early_access, "verify_wheels", side_effect=lambda wheels: verify(wheels, sources)):
            with self.assertRaisesRegex(ValueError, "extra fields"):
                build_early_access.main(["--release", "fixture", "--helper-dir", str(helpers),
                                         "--policy-trust", str(trust_path), "--output-dir", str(rejected)])
        self.assertFalse(rejected.exists())


if __name__ == "__main__":
    unittest.main()
