import sqlite3
from pathlib import Path

import pytest

from core.database import SCHEMA_VERSION, Database, _MIGRATIONS


def test_database_initializes_schema_and_reuses_connection(tmp_path: Path) -> None:
    database = Database(tmp_path / "nested" / "assistant.sqlite3")
    connection = database.open()

    assert database.open() is connection
    assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    names = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"tasks", "task_tags", "indexed_entries", "applications", "reminder_deliveries"} <= names
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    database.close()
    assert database.connection is None


def test_database_migration_enforces_task_and_tag_constraints(tmp_path: Path) -> None:
    database = Database(tmp_path / "assistant.sqlite3")
    connection = database.open()
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """INSERT INTO tasks(title, created_at_utc, updated_at_utc)
               VALUES ('', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"""
        )
    database.close()


def test_database_rejects_newer_schema_and_closes_failed_connection(tmp_path: Path) -> None:
    path = tmp_path / "assistant.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")

    database = Database(path)
    with pytest.raises(RuntimeError, match="newer than supported"):
        database.open()
    assert database.connection is None

    # Successful reopening proves the failed initialization released its handle.
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION + 1


def test_database_upgrades_v1_indexed_entries_to_fts5(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as connection:
        for statement in _MIGRATIONS[1]:
            connection.execute(statement)
        connection.execute(
            """INSERT INTO indexed_entries(
                   path, name, parent_path, is_directory, scanned_at_utc
               ) VALUES ('C:/Docs/Old Notes.txt', 'Old Notes.txt', 'C:/Docs', 0, 'now')"""
        )
        connection.execute("PRAGMA user_version = 1")

    database = Database(path)
    connection = database.open()
    assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert connection.execute(
        "SELECT rowid FROM indexed_entries_fts WHERE indexed_entries_fts MATCH 'old'"
    ).fetchone() is not None
    database.close()
