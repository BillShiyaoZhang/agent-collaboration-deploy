"""Package a clean, tracked Web source snapshot and reviewed deployment config."""
import argparse
import gzip
import io
import json
from pathlib import Path
import tarfile

from release_common import ROOT, release_name, repository_head, sha, source_files, source_timestamp

DEPLOY_FILES = ("docker-compose.yml", "deploy/nginx/nginx.conf", "deploy/platform/config.yaml")


def build_archive(root, output, release):
    web = root / "agent-collaboration-web"
    heads = {"deploy": repository_head(root), "web": repository_head(web)}
    files = {"web/" + name: data for name, data in source_files(web)}
    if not files:
        raise ValueError("The Web repository contains no releasable source")
    deploy_source = dict(source_files(root))
    for name in DEPLOY_FILES:
        if name not in deploy_source:
            raise ValueError(f"Deployment config must exist and be tracked: {name}")
        files[name] = deploy_source[name]
    manifest = {
        "schema_version": 1, "release": release, "mode": "full_snapshot", "source_heads": heads,
        "web_source_prefix": "web/",
        "deployment": "Stage Web source in a fresh directory and review the supplied configuration before deployment. "
                      "This archive is not an overlay patch; keep persistent data outside the staged source directory.",
        "files": {name: sha(data) for name, data in sorted(files.items())},
    }
    files["manifest.json"] = json.dumps(manifest, indent=2).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = source_timestamp(root)
    with output.open("wb") as target, gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=timestamp) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(name)
                info.size, info.mtime = len(data), timestamp
                info.mode = 0o755 if name.endswith(".sh") else 0o644
                archive.addfile(info, io.BytesIO(data))
    return {"archive": str(output), "files": len(files), "bytes": output.stat().st_size,
            "sha256": sha(output.read_bytes()), "mode": manifest["mode"], "source_heads": heads}


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--release", help="Release identifier; defaults to today's UTC date")
    cli.add_argument("--output", type=Path, default=ROOT / "build/releases/web-release.tar.gz")
    args = cli.parse_args(argv)
    print(json.dumps(build_archive(ROOT, args.output.resolve(), release_name(args.release)), indent=2))


if __name__ == "__main__":
    main()
