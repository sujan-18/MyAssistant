"""SQLite connection and forward-only schema migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_VERSION = 2

_MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: (
        """CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL CHECK(length(trim(title)) > 0),
            description TEXT NOT NULL DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
            due_at_utc TEXT,
            timezone_id TEXT,
            project_path TEXT,
            completed_at_utc TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        )""",
        "CREATE INDEX tasks_due_idx ON tasks(due_at_utc) WHERE completed_at_utc IS NULL",
        """CREATE TABLE task_tags (
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            tag TEXT NOT NULL CHECK(length(trim(tag)) > 0),
            PRIMARY KEY(task_id, tag)
        )""",
        """CREATE TABLE indexed_entries (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            parent_path TEXT NOT NULL,
            extension TEXT NOT NULL DEFAULT '',
            is_directory INTEGER NOT NULL CHECK(is_directory IN (0, 1)),
            modified_at REAL,
            size_bytes INTEGER,
            scanned_at_utc TEXT NOT NULL
        )""",
        "CREATE INDEX indexed_entries_parent_idx ON indexed_entries(parent_path)",
        """CREATE TABLE applications (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            launch_target TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            discovered_at_utc TEXT NOT NULL
        )""",
        "CREATE INDEX applications_name_idx ON applications(name COLLATE NOCASE)",
        """CREATE TABLE reminder_deliveries (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            reminder_key TEXT NOT NULL,
            delivered_at_utc TEXT NOT NULL,
            UNIQUE(task_id, reminder_key)
        )""",
    ),
    2: (
        """CREATE VIRTUAL TABLE indexed_entries_fts USING fts5(
            name, path, content='indexed_entries', content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )""",
        """CREATE TRIGGER indexed_entries_ai AFTER INSERT ON indexed_entries BEGIN
            INSERT INTO indexed_entries_fts(rowid, name, path)
            VALUES (new.id, new.name, new.path);
        END""",
        """CREATE TRIGGER indexed_entries_ad AFTER DELETE ON indexed_entries BEGIN
            INSERT INTO indexed_entries_fts(indexed_entries_fts, rowid, name, path)
            VALUES ('delete', old.id, old.name, old.path);
        END""",
        """CREATE TRIGGER indexed_entries_au AFTER UPDATE ON indexed_entries BEGIN
            INSERT INTO indexed_entries_fts(indexed_entries_fts, rowid, name, path)
            VALUES ('delete', old.id, old.name, old.path);
            INSERT INTO indexed_entries_fts(rowid, name, path)
            VALUES (new.id, new.name, new.path);
        END""",
        "INSERT INTO indexed_entries_fts(indexed_entries_fts) VALUES ('rebuild')",
    ),
}


class Database:
    """Owns a configured SQLite connection and applies schema upgrades."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: sqlite3.Connection | None = None

    def open(self) -> sqlite3.Connection:
        if self.connection is not None:
            return self.connection
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            self._migrate(connection)
        except BaseException:
            # Release the partially initialized handle for every failure type,
            # then re-raise without changing the startup error.
            connection.close()
            raise
        self.connection = connection
        return connection

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema {version} is newer than supported schema {SCHEMA_VERSION}"
            )
        while version < SCHEMA_VERSION:
            next_version = version + 1
            try:
                with connection:
                    for statement in _MIGRATIONS[next_version]:
                        connection.execute(statement)
                    connection.execute(f"PRAGMA user_version = {next_version}")
            except KeyError as exc:
                raise RuntimeError(f"Missing database migration {next_version}") from exc
            version = next_version

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def __enter__(self) -> Database:
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
