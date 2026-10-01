"""Isolated WAL backup and no-overwrite regression checks."""
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backup_workspace_gateway import backup


class BackupTests(unittest.TestCase):
    def test_live_wal_preserves_grants_and_deleted_accounts(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "state.sqlite3", Path(directory) / "backup.sqlite3"
            connection = sqlite3.connect(source)
            connection.execute("PRAGMA journal_mode=WAL")
            for table in ("nodes", "sessions", "launches", "audit", "deleted_accounts"):
                connection.execute(f"CREATE TABLE {table}(id TEXT)")
            connection.execute("INSERT INTO nodes VALUES ('original-grant')")
            connection.execute("INSERT INTO deleted_accounts VALUES ('deleted-account')")
            connection.commit()
            backup(source, output)
            connection.execute("INSERT INTO nodes VALUES ('later-write')")
            connection.commit()
            with closing(sqlite3.connect(output)) as snapshot:
                self.assertEqual(snapshot.execute("SELECT id FROM nodes").fetchall(), [("original-grant",)])
                self.assertEqual(snapshot.execute("SELECT id FROM deleted_accounts").fetchall(), [("deleted-account",)])
                self.assertEqual(snapshot.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0], 2)
            connection.close()
            if os.name != "nt":
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "state.sqlite3", Path(directory) / "existing"
            source.touch()
            output.write_bytes(b"keep")
            with self.assertRaises(ValueError):
                backup(source, output)
            self.assertEqual(output.read_bytes(), b"keep")

    def test_wrong_database_leaves_no_partial_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "wrong.sqlite3", Path(directory) / "backup.sqlite3"
            with closing(sqlite3.connect(source)) as connection:
                connection.execute("CREATE TABLE unrelated(id)")
            with self.assertRaises(ValueError):
                backup(source, output)
            self.assertFalse(output.exists())
            self.assertEqual(sorted(path.name for path in Path(directory).iterdir()), ["wrong.sqlite3"])

    def test_nonfinite_timeout_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "state.sqlite3"
            source.touch()
            for value in (float("nan"), float("inf")):
                with self.assertRaises(ValueError):
                    backup(source, Path(directory) / "backup.sqlite3", timeout=value)


if __name__ == "__main__":
    unittest.main()
