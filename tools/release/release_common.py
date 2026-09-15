"""Source and metadata helpers shared by the release builders (Python 3.11+)."""
import ast
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT / "agent-comm-platform" / "agent-comm"
EXCLUDED_DIRS = {"build", "dist", "node_modules", ".next", ".git", ".agents", ".codex",
                 "__pycache__", "downloads", "output", "tmp", "data", "acme-challenge"}
PRIVATE_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".exe", ".pyc"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args, input=None):
    return subprocess.check_output(
        ["git", "-c", "safe.directory=" + Path(repo).resolve().as_posix(), *args], cwd=repo, input=input)


def repository_head(repo):
    """Reject empty submodules and unpublished local changes before packaging."""
    repo = Path(repo).resolve()
    actual = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if actual != repo:
        raise ValueError(f"Initialize the exact repository before releasing: {repo}")
    if git(repo, "status", "--porcelain", "--untracked-files=all").strip():
        raise ValueError(f"Release source must be committed and clean (including submodules): {repo}")
    return git(repo, "rev-parse", "HEAD").decode().strip()


def source_files(repo):
    """Yield committed blobs, preserving Git line endings across operating systems."""
    repo = Path(repo).resolve()
    selected = []
    for entry in git(repo, "ls-tree", "-rz", "--full-tree", "HEAD").split(b"\0"):
        if not entry:
            continue
        header, raw_name = entry.split(b"\t", 1)
        mode, kind, object_id = header.decode().split()
        if mode not in {"100644", "100755"} or kind != "blob":
            continue
        name = raw_name.decode()
        path = Path(name)
        if any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in Path(name).parts):
            continue
        if (path.name.startswith(".env") and path.name != ".env.example") or path.suffix.lower() in PRIVATE_SUFFIXES:
            continue
        selected.append((name, object_id))
    if not selected:
        return
    blobs = git(repo, "cat-file", "--batch", input="".join(object_id + "\n" for _, object_id in selected).encode())
    cursor = 0
    for name, object_id in selected:
        end = blobs.index(b"\n", cursor)
        actual_id, kind, size = blobs[cursor:end].decode().split()
        if actual_id != object_id or kind != "blob":
            raise ValueError(f"Unexpected Git object while packaging {name}")
        cursor = end + 1
        data = blobs[cursor:cursor + int(size)]
        cursor += int(size) + 1
        if data[:4] in {b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe"} or data[:2] == b"MZ":
            continue
        yield name.replace("\\", "/"), data


def project_metadata(source):
    """Read literal package metadata without importing or executing setup.py."""
    pyproject = source / "pyproject.toml"
    if pyproject.is_file():
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    else:
        tree = ast.parse((source / "setup.py").read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "setup"]
        if len(calls) != 1:
            raise ValueError(f"Expected one static setup() declaration: {source}")
        project = {item.arg: ast.literal_eval(item.value) for item in calls[0].keywords
                   if item.arg in {"name", "version"}}
    if any(not isinstance(project.get(key), str) or not project[key] for key in ("name", "version")):
        raise ValueError(f"Release requires static package name/version metadata: {source}")
    return project["name"], project["version"]


def release_name(value):
    value = value or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in value):
        raise ValueError("--release must use only letters, numbers, dots, underscores and hyphens")
    return value


def source_timestamp(repo):
    return int(git(repo, "show", "-s", "--format=%ct", "HEAD").decode().strip())
