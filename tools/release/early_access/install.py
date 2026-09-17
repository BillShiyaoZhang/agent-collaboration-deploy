"""Verify an extracted early-access bundle, then install into THIS Hermes Python.

No profile, key, mailbox or database is modified. --check-only is stdlib-only
and can be used by a release builder without Hermes installed.
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
import re
import shutil
import subprocess
import sys
import zipfile

EXPECTED_PACKAGES = ("agent-comm-runtime", "hermes-platform-agent-comm")


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


def verify_bundle(directory):
    root = Path(directory).expanduser().resolve()
    manifest_path = root / "SHA256SUMS.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("SHA256SUMS.json is missing or is a symbolic link")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, dict) or not files:
        raise ValueError("SHA256SUMS.json must contain a nonempty files mapping")
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
    required = {"install.py", "configure_hermes.py", "README.md"}
    required.update(path.relative_to(root).as_posix() for path in root.glob("*.py"))
    helper_assets = [path for path in root.iterdir() if path.is_file() and "helper" in path.name.lower()
                     and path.suffix.lower() in {"", ".exe"}]
    if len(helper_assets) != 1:
        raise ValueError("The bundle must contain exactly one platform helper executable at its root")
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
    args = cli.parse_args(argv)
    try:
        root, wheels = verify_bundle(args.bundle_dir)
        package_versions = {name: wheel_metadata(wheel)[1]["Version"] for name, wheel in wheels.items()}
        print(json.dumps({"status": "bundle_verified", "bundle": str(root), "packages": package_versions}, ensure_ascii=False))
        if args.check_only:
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
        print("Installed the verified wheels into this Hermes Python. Next run configure_hermes.py with this same executable.")
        return 0
    except (ValueError, RuntimeError, OSError, zipfile.BadZipFile, subprocess.CalledProcessError, ImportError) as exc:
        print(f"Installation stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
