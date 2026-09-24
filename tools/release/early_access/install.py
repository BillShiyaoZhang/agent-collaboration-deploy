"""Verify an extracted early-access bundle, then install into THIS Hermes Python.

--check-only is stdlib-only and never modifies a profile, key or database.
--identity-dir additionally pins the release's verified policy root to an
existing helper identity before that helper is started. Release builders
verifying a bundle for another OS/CPU must pass --cross-platform-check.
"""
import argparse
from email.parser import Parser
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from urllib.parse import urlsplit

EXPECTED_PACKAGES = ("agent-comm-runtime", "hermes-platform-agent-comm")
SUPPORTED_PLATFORMS = {"windows-amd64", "linux-amd64", "macos-amd64", "macos-arm64"}
POLICY_TRUST_FIELDS = {"schema_version", "release", "platform_origin", "platform_peer_id",
                       "policy_root_public_key_hex", "verification_note"}


def host_platform():
    system = {"win32": "windows", "linux": "linux", "darwin": "macos"}.get(sys.platform)
    machine = platform.machine().lower()
    architecture = ("amd64" if machine in {"amd64", "x86_64"} else
                    "arm64" if machine in {"arm64", "aarch64"} else None)
    variant = f"{system}-{architecture}"
    if variant not in SUPPORTED_PLATFORMS:
        raise RuntimeError(f"No Agent Comm helper bundle is available for this host: {sys.platform}/{machine}")
    return variant


def utf8_output():
    for stream in (sys.stdout, sys.stderr):
        if callable(getattr(stream, "reconfigure", None)):
            stream.reconfigure(encoding="utf-8")


def _asset(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError("Manifest paths must be plain relative paths using forward slashes")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ValueError("Manifest path escapes the bundle")
    candidate = root.joinpath(*path.parts)
    if candidate.is_symlink() or any(parent.is_symlink() for parent in candidate.parents if parent != root and parent.is_relative_to(root)):
        raise ValueError("Bundle assets must not be symbolic links")
    if not candidate.resolve().is_relative_to(root):
        raise ValueError("Manifest path escapes the bundle")
    if not candidate.is_file():
        raise ValueError(f"Bundle asset is missing: {relative}")
    return candidate


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wheel_metadata(path):
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1 or archive.getinfo(names[0]).file_size > 200000:
            raise ValueError(f"Invalid wheel metadata: {path.name}")
        metadata = Parser().parsestr(archive.read(names[0]).decode("utf-8"))
    name = (metadata.get("Name") or "").lower().replace("_", "-")
    return name, metadata


def validate_policy_trust(value, *, release):
    """Accept only public, release-specific trust anchors supplied by the publisher."""
    if (not isinstance(value, dict) or set(value) != POLICY_TRUST_FIELDS
            or type(value.get("schema_version")) is not int or value["schema_version"] != 1):
        raise ValueError("policy-trust.json has an unsupported schema or extra fields")
    if not isinstance(release, str) or not release or value["release"] != release:
        raise ValueError("policy-trust.json does not match this release")
    root = value["policy_root_public_key_hex"]
    if not isinstance(root, str) or not re.fullmatch(r"[0-9a-f]{64}", root):
        raise ValueError("policy-trust.json needs a canonical Ed25519 root public key")
    peer = value["platform_peer_id"]
    if not isinstance(peer, str) or not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,80}", peer):
        raise ValueError("policy-trust.json needs a canonical Platform Peer ID")
    origin = value["platform_origin"]
    if not isinstance(origin, str):
        raise ValueError("policy-trust.json needs an HTTPS Platform origin")
    parsed = urlsplit(origin)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("policy-trust.json needs a valid HTTPS Platform port") from exc
    if (not origin.isascii() or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or port == 0
            or parsed.path or parsed.query or parsed.fragment or origin != f"https://{parsed.netloc}"):
        raise ValueError("policy-trust.json needs a plain HTTPS Platform origin")
    note = value["verification_note"]
    if (not isinstance(note, str) or not note.strip() or note != note.strip() or len(note) > 512
            or any(ord(char) < 32 or ord(char) == 127 for char in note)):
        raise ValueError("policy-trust.json needs a concise independent verification note")
    return value


def parse_policy_trust_bytes(data, *, release):
    def unique_fields(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"Duplicate policy-trust.json field: {key}")
            value[key] = item
        return value

    return validate_policy_trust(json.loads(data.decode("utf-8"), object_pairs_hook=unique_fields), release=release)


def load_policy_trust(root, *, release):
    path = _asset(root, "policy-trust.json")
    if path.stat().st_size > 8192:
        raise ValueError("policy-trust.json is too large")
    return parse_policy_trust_bytes(path.read_bytes(), release=release)


def pin_policy_trust(root, identity_dir, *, release):
    """Pin to an existing identity; never create a replacement identity here."""
    root, _ = verify_bundle(root)
    trust = load_policy_trust(root, release=release)
    identity = Path(identity_dir).expanduser().resolve()
    if not identity.is_dir() or not (identity / "identity_sk.pem").is_file():
        raise ValueError("--identity-dir must name an existing helper identity; do not initialize another")
    helper = root / ("agent-comm-helper.exe" if os.name == "nt" else "agent-comm-helper")
    if os.name != "nt":
        helper.chmod(helper.stat().st_mode | 0o100)
    note = f"Agent Comm release {release}: {trust['verification_note']}"
    result = subprocess.run([str(helper), "v2-ensure-policy-root", str(identity),
                             trust["policy_root_public_key_hex"], trust["platform_peer_id"], note],
                            check=True, capture_output=True, text=True, timeout=45)
    output = json.loads(result.stdout)
    if (not isinstance(output, dict) or output.get("pinned") is not True
            or output.get("policy_root_public_key") != trust["policy_root_public_key_hex"]
            or output.get("platform_id") != trust["platform_peer_id"]):
        raise RuntimeError("The helper did not confirm the exact release policy root and Platform identity")
    return trust


def verify_bundle(directory, *, cross_platform=False):
    root = Path(directory).expanduser().resolve()
    manifest_path = root / "SHA256SUMS.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("SHA256SUMS.json is missing or is a symbolic link")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, dict) or not files:
        raise ValueError("SHA256SUMS.json must contain a nonempty files mapping")
    variant = manifest.get("platform")
    if not isinstance(variant, str) or variant not in SUPPORTED_PLATFORMS:
        raise ValueError("SHA256SUMS.json must declare a supported helper platform")
    if not cross_platform:
        actual = host_platform()
        if variant != actual:
            raise ValueError(f"The bundle targets {variant}; this host requires {actual}")
    expected_packages = manifest.get("packages")
    if (not isinstance(expected_packages, dict) or set(expected_packages) != set(EXPECTED_PACKAGES)
            or any(not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", version)
                   for version in expected_packages.values())):
        raise ValueError("SHA256SUMS.json must declare the runtime and connector package versions")
    for relative, expected in files.items():
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            raise ValueError(f"Invalid SHA256 for {relative}")
        path = _asset(root, relative)
        if _sha256(path) != expected.lower():
            raise ValueError(f"SHA256 mismatch: {relative}")
    required = {"install.py", "configure_hermes.py", "README.md", "policy-trust.json"}
    required.update(path.relative_to(root).as_posix() for path in root.glob("*.py"))
    helper_assets = [path for path in root.iterdir() if path.is_file() and "helper" in path.name.lower()
                     and path.suffix.lower() in {"", ".exe"}]
    if len(helper_assets) != 1:
        raise ValueError("The bundle must contain exactly one platform helper executable at its root")
    helper_name = "agent-comm-helper.exe" if variant.startswith("windows-") else "agent-comm-helper"
    if helper_assets[0].name != helper_name:
        raise ValueError(f"The {variant} bundle must contain {helper_name}")
    required.add(helper_assets[0].relative_to(root).as_posix())
    wheels = list((root / "wheels").glob("*.whl"))
    if len(wheels) != len(EXPECTED_PACKAGES):
        raise ValueError("The bundle must contain exactly the two supplied runtime and Hermes connector wheels")
    required.update(path.relative_to(root).as_posix() for path in wheels)
    if required - files.keys():
        raise ValueError("Required assets are not covered by SHA256SUMS.json: " + ", ".join(sorted(required - files.keys())))
    selected = {}
    for wheel in wheels:
        name, metadata = wheel_metadata(wheel)
        if name not in expected_packages or metadata.get("Version") != expected_packages[name] or name in selected:
            raise ValueError(f"Unexpected wheel name/version: {wheel.name}")
        selected[name] = wheel
    if set(selected) != set(EXPECTED_PACKAGES):
        raise ValueError("The expected wheel pair is incomplete")
    load_policy_trust(root, release=manifest.get("release"))
    return root, selected


def ensure_hermes():
    if sys.version_info < (3, 11):
        raise RuntimeError("Use the Python 3.11+ interpreter that runs Hermes")
    # Hermes source installations run venv/bin/python (or venv/Scripts/python)
    # without an editable package. Only inspect that interpreter's adjacent
    # source tree; never select another Python or scan somebody else's profile.
    if importlib.util.find_spec("hermes_constants") is None:
        candidates = [Path(sys.prefix).resolve().parent, Path(sys.executable).resolve().parents[2]]
        for candidate in candidates:
            if ((candidate / "hermes_constants.py").is_file()
                    and (candidate / "hermes_cli" / "config.py").is_file()
                    and (candidate / "gateway" / "platforms" / "base.py").is_file()):
                sys.path.insert(0, str(candidate))
                importlib.invalidate_caches()
                break
    try:
        constants = importlib.import_module("hermes_constants")
        config = importlib.import_module("hermes_cli.config")
        if (not callable(getattr(constants, "get_hermes_home", None))
                or not callable(getattr(config, "require_readable_config_before_write", None))
                or not callable(getattr(config, "atomic_config_write", None))
                or importlib.util.find_spec("gateway.platforms.base") is None):
            raise ImportError("Required Hermes host interfaces are unavailable")
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError("This Python cannot load the supported Hermes host. Run this script with the same Python executable used by Hermes; nothing was installed.") from exc
    return constants, config


def check_dependencies(wheels):
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version
    python_version = Version(".".join(map(str, sys.version_info[:3])))
    package_versions = {name: wheel_metadata(wheel)[1]["Version"] for name, wheel in wheels.items()}
    for wheel in wheels.values():
        _, metadata = wheel_metadata(wheel)
        if metadata.get("Requires-Python") and python_version not in SpecifierSet(metadata["Requires-Python"]):
            raise RuntimeError(f"This Python does not satisfy {wheel.name}'s Requires-Python")
        for text in metadata.get_all("Requires-Dist", []):
            requirement = Requirement(text)
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            name = requirement.name.lower().replace("_", "-")
            if name in package_versions:
                version = package_versions[name]
            else:
                try:
                    version = importlib.metadata.version(requirement.name)
                except importlib.metadata.PackageNotFoundError as exc:
                    raise RuntimeError(f"Hermes's current Python is missing {requirement}; install its supported dependencies before continuing") from exc
            if requirement.specifier and Version(version) not in requirement.specifier:
                raise RuntimeError(f"Hermes's current Python has {requirement.name} {version}, but the connector needs {requirement}; no packages were changed")


def install_wheels(wheels):
    """Keep the exact interpreter target, including uv environments without pip."""
    assets = [str(wheels[name]) for name in EXPECTED_PACKAGES]
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith(("PIP_", "UV_")) and key not in {"VIRTUAL_ENV", "CONDA_PREFIX"}}
    environment["PIP_CONFIG_FILE"] = os.devnull
    if importlib.util.find_spec("pip") is not None:
        command = [sys.executable, "-m", "pip", "--isolated", "install", "--disable-pip-version-check", "--no-input",
                   "--no-index", "--no-deps", "--prefix", str(Path(sys.prefix).resolve()), "--force-reinstall", *assets]
    else:
        uv = shutil.which("uv")
        if not uv:
            raise RuntimeError("This Hermes Python has no pip and uv was not found. Install uv or enable pip in this same interpreter, then retry")
        command = [uv, "--no-config", "pip", "install", "--python", sys.executable,
                   "--no-index", "--no-deps", "--reinstall", *assets]
    subprocess.run(command, check=True, env=environment)


def main(argv=None):
    utf8_output()
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--bundle-dir", type=Path, default=Path(__file__).resolve().parent)
    cli.add_argument("--check-only", action="store_true", help="Verify checksums and wheel metadata; do not require Hermes or install anything")
    cli.add_argument("--cross-platform-check", action="store_true",
                     help="With --check-only, verify a release for another OS/CPU without installing it")
    cli.add_argument("--identity-dir", type=Path,
                     help="After installation, pin verified release trust to this existing helper identity")
    cli.add_argument("--pin-only", action="store_true",
                     help="Pin verified release trust to --identity-dir without reinstalling Python wheels")
    args = cli.parse_args(argv)
    try:
        if args.cross_platform_check and not args.check_only:
            raise ValueError("--cross-platform-check requires --check-only")
        if args.identity_dir and args.check_only:
            raise ValueError("--identity-dir cannot be used with --check-only")
        if args.pin_only and (args.check_only or not args.identity_dir):
            raise ValueError("--pin-only requires --identity-dir and cannot be used with --check-only")
        root, wheels = verify_bundle(args.bundle_dir, cross_platform=args.cross_platform_check)
        release = json.loads((root / "SHA256SUMS.json").read_text(encoding="utf-8"))["release"]
        package_versions = {name: wheel_metadata(wheel)[1]["Version"] for name, wheel in wheels.items()}
        print(json.dumps({"status": "bundle_verified", "bundle": str(root), "packages": package_versions}, ensure_ascii=False))
        if args.check_only:
            return 0
        if args.pin_only:
            pin_policy_trust(root, args.identity_dir, release=release)
            print("The existing helper identity now has this release's verified policy root and Platform ID. Restart its daemon before continuing.")
            return 0
        constants, _ = ensure_hermes()
        check_dependencies(wheels)
        print(json.dumps({"python": sys.executable, "hermes_source": str(Path(constants.__file__).resolve())}, ensure_ascii=False))
        install_wheels(wheels)
        # A fresh interpreter avoids reporting modules cached before installation.
        probe = ("import importlib.metadata as m; "
                 f"expected = {package_versions!r}; "
                 "assert all(m.version(name) == version for name, version in expected.items()); "
                 "import agent_comm_runtime.remote, hermes_platform_agent_comm")
        subprocess.run([sys.executable, "-c", probe], check=True, cwd=root)
        if args.identity_dir:
            pin_policy_trust(root, args.identity_dir, release=release)
        print("Installed the verified wheels into this Hermes Python. This installs Python components only; it does not connect Hermes to Web.")
        print("For a new Web connection, run onboard_hermes.py from this bundle with this same Hermes Python. It starts the helper, returns the Web claim_url, and completes pairing and Gateway startup automatically after Web confirmation.")
        print("Current guide: https://agent-communication.online/agent-install.md . Existing manually managed identities must retain their helper data, URN and Hermes profile; follow the existing-client steps instead of replacing that identity.")
        return 0
    except (ValueError, RuntimeError, OSError, zipfile.BadZipFile, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, ImportError, json.JSONDecodeError) as exc:
        print(f"Installation stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
