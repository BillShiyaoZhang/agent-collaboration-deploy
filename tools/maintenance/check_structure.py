"""Check repository boundaries and Markdown links without network access.

Run from any directory: python tools/maintenance/check_structure.py
Includes tracked and untracked, non-ignored source files, so it also works before
committing a reorganization. Deleted files are excluded. GitHub links pointing
into one of the four local repositories are resolved against this checkout.
"""
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
REPOSITORIES = {
    "agent-collaboration-deploy": ROOT,
    "agent-collaboration-web": ROOT / "agent-collaboration-web",
    "agent-comm-platform": ROOT / "agent-comm-platform",
    "agent-comm": ROOT / "agent-comm-platform" / "agent-comm",
}


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), *args],
        encoding="utf-8",
    )


def sources(repo):
    top = Path(git(repo, "rev-parse", "--show-toplevel").strip()).resolve()
    if top != repo.resolve():
        raise RuntimeError(f"Uninitialized submodule: {repo.relative_to(ROOT)}")
    names = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    return sorted({repo / name for name in names.split("\0") if name and (repo / name).is_file()})


def target(document, url):
    url = unquote(url.strip("<>"))
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        if parsed.netloc != "github.com":
            return None
        parts = parsed.path.strip("/").split("/")
        if len(parts) < 5 or parts[0] != "BillShiyaoZhang" or parts[1] not in REPOSITORIES:
            return None
        # Commit-specific historical links are intentionally left unchanged.
        if parts[2] not in {"blob", "tree"} or parts[3] not in {"main", "master"}:
            return None
        return REPOSITORIES[parts[1]].joinpath(*parts[4:])
    if not parsed.path or parsed.path.startswith("/"):
        return None
    return document.parent / parsed.path


def main():
    errors, documents = [], 0
    for name, repo in REPOSITORIES.items():
        try:
            files = sources(repo)
        except (RuntimeError, subprocess.CalledProcessError) as error:
            errors.append(f"{name}: {error}")
            continue
        for file in files:
            if file.suffix != ".md":
                continue
            documents += 1
            text = file.read_text(encoding="utf-8-sig")
            # Links shown as examples in fenced code are not navigation.
            text = re.sub(r"(?ms)^```.*?^```[^\n]*", "", text)
            links = re.findall(r"\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", text)
            for url in links:
                path = target(file, url)
                if path is not None and not path.exists():
                    errors.append(f"{file.relative_to(ROOT).as_posix()}: {url}")
        print(f"{name}: {len(files)} source files")
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)
    print(f"Checked {documents} Markdown files; {len(errors)} errors")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
