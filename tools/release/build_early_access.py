"""Build verified client bundles and a source snapshot from clean repositories."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from release_common import ROOT, SDK, project_metadata, release_name, repository_head, sha, source_files, source_timestamp

SOURCES = (SDK / "python", SDK / "connectors/hermes-platform")
VARIANTS = {
    "windows-amd64": ("agent-comm-helper.exe", "agent-comm-helper.exe"),
    "linux-amd64": ("agent-comm-helper-linux-amd64", "agent-comm-helper"),
    "macos-amd64": ("agent-comm-helper-darwin-amd64", "agent-comm-helper"),
    "macos-arm64": ("agent-comm-helper-darwin-arm64", "agent-comm-helper"),
}


def release_packages(sources=SOURCES):
    packages, wheels = {}, []
    for source in sources:
        name, version = project_metadata(source)
        packages[name] = version
        wheel = source / "dist" / f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
        wheels.append(wheel)
    return packages, wheels


def verify_wheels(wheels, sources=SOURCES):
    from early_access.install import wheel_metadata
    count = 0
    for wheel, source in zip(wheels, sources, strict=True):
        name, version = project_metadata(source)
        actual_name, metadata = wheel_metadata(wheel)
        if actual_name != name or metadata.get("Version") != version:
            raise ValueError(f"Wheel metadata differs from source: {wheel}")
        with zipfile.ZipFile(wheel) as archive:
            for entry in archive.namelist():
                if ".dist-info/" in entry or entry.endswith("/"):
                    continue
                path = source / entry
                if not path.resolve().is_relative_to(source.resolve()) or not path.is_file() or archive.read(entry) != path.read_bytes():
                    raise ValueError(f"Wheel/source mismatch: {entry}")
                count += 1
            package = name.replace("-", "_")
            for path in (source / package).rglob("*"):
                if path.is_file() and path.suffix in {".py", ".yaml", ".md", ".js", ".json"} and "__pycache__" not in path.parts:
                    if path.relative_to(source).as_posix() not in archive.namelist():
                        raise ValueError(f"Missing packaged source: {path}")
    return count


def write_zip(path, files, timestamp, executable=()):
    date = datetime.fromtimestamp(max(timestamp, 315532800), timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=date)
            info.compress_type, info.create_system = zipfile.ZIP_DEFLATED, 3
            info.external_attr = (0o100755 if name in executable else 0o100644) << 16
            archive.writestr(info, data)


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--release", help="Release identifier; defaults to today's UTC date")
    cli.add_argument("--helper-dir", type=Path, default=ROOT / "build/early-access",
                     help="Directory containing the four prebuilt helper executables")
    cli.add_argument("--output-dir", type=Path, default=ROOT / "downloads")
    cli.add_argument("--invitation", type=Path, help="Optional reviewed PDF to copy into this release")
    args = cli.parse_args(argv)
    release = release_name(args.release)
    repos = (ROOT, ROOT / "agent-collaboration-web", ROOT / "agent-comm-platform", SDK)
    heads = {repo.relative_to(ROOT).as_posix(): repository_head(repo) for repo in repos}
    packages, wheels = release_packages()
    verified = verify_wheels(wheels)
    assets = Path(__file__).resolve().parent / "early_access"
    common = {name: (assets / name).read_bytes() for name in ("README.md", "install.py", "configure_hermes.py")}
    common.update({"wheels/" + wheel.name: wheel.read_bytes() for wheel in wheels})
    helpers = {platform: (args.helper_dir / binary).read_bytes() for platform, (binary, _) in VARIANTS.items()}
    invitation = None
    if args.invitation:
        invitation = args.invitation.read_bytes()
        if args.invitation.suffix.lower() != ".pdf" or not invitation.startswith(b"%PDF-"):
            raise ValueError("--invitation must name a reviewed PDF file")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp, outputs = source_timestamp(ROOT), {}

    def record(path):
        outputs[path.name] = {"bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}

    for platform, (_, name) in VARIANTS.items():
        files = {**common, name: helpers[platform]}
        files["SHA256SUMS.json"] = json.dumps({
            "schema_version": 1, "release": release, "platform": platform, "packages": packages,
            "files": {name: sha(data) for name, data in sorted(files.items())}}, indent=2).encode()
        destination = args.output_dir / f"agent-comm-early-access-{platform}.zip"
        write_zip(destination, files, timestamp, (name,))
        with tempfile.TemporaryDirectory(prefix="verify-bundle-") as folder:
            with zipfile.ZipFile(destination) as archive:
                archive.extractall(folder)
            subprocess.run([sys.executable, str(Path(folder) / "install.py"), "--check-only"], check=True)
        record(destination)
    source = {}
    for repo in repos:
        prefix = repo.relative_to(ROOT).as_posix()
        prefix = "" if prefix == "." else prefix + "/"
        for name, data in source_files(repo):
            source["agent-collaboration-deploy/" + prefix + name] = data
    source["agent-collaboration-deploy/SOURCE_RELEASE.json"] = json.dumps(
        {"release": release, "source_heads": heads}, indent=2).encode()
    sourcezip = args.output_dir / "agent-comm-early-access-source.zip"
    write_zip(sourcezip, source, timestamp)
    record(sourcezip)
    if invitation is not None:
        destination = args.output_dir / "agent-comm-early-access-invitation.pdf"
        destination.write_bytes(invitation)
        record(destination)
    report = {"release": release, "packages": packages, "source_heads": heads,
              "verified_wheel_source_files": verified, "files": outputs}
    (args.output_dir / "release-manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
