"""Create a private, consistent SQLite backup of Workspace Gateway state."""

from __future__ import annotations

import argparse
from contextlib import closing
import math
import os
import sqlite3
import tempfile
import time
from pathlib import Path


def backup(database: Path, output: Path, *, timeout: float = 30) -> Path:
    database, output = database.resolve(strict=True), output.resolve()
    if not database.is_file() or output == database or output.exists():
        raise ValueError("Use an existing Gateway database and a new backup destination")
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 300:
        raise ValueError("Backup timeout must be between 0 and 300 seconds")
    output.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=timeout)
    temporary: Path | None = None
    try:
        tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"nodes", "sessions", "launches", "audit", "deleted_accounts"}.issubset(tables):
            raise ValueError("Source is not a Workspace Gateway state database")
        descriptor, filename = tempfile.mkstemp(prefix=".workspace-backup-", suffix=".sqlite3", dir=output.parent)
        os.close(descriptor)
        temporary = Path(filename)
        started = time.monotonic()

        def progress(status, remaining, total):
            if time.monotonic() - started > timeout:
                raise TimeoutError("Gateway backup exceeded its deadline")

        with closing(sqlite3.connect(temporary)) as destination:
            source.backup(destination, pages=128, progress=progress, sleep=0.01)
            if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity check failed")
        os.chmod(temporary, 0o600)
        # A hard link publishes without replacing a destination created concurrently.
        os.link(temporary, output)
        return output
    finally:
        source.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    try:
        backup(args.database, args.output, timeout=args.timeout)
    except (OSError, sqlite3.Error, ValueError, TimeoutError) as error:
        parser.exit(1, f"Gateway backup failed: {error}\n")
    print("Gateway backup complete; integrity check passed. Protect this file as private state.")


if __name__ == "__main__":
    main()
