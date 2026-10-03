"""Local metadata indexing and FTS5 search for configured filesystem roots."""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_BATCH_SIZE = 250
_FILE_ATTRIBUTE_HIDDEN = 0x2
_FILE_ATTRIBUTE_SYSTEM = 0x4


@dataclass(frozen=True, slots=True)
class FileResult:
    name: str
    path: str
    is_directory: bool
    score: int


@dataclass(frozen=True, slots=True)
class FileSearchResults:
    query: str
    matches: tuple[FileResult, ...]
    ambiguous: bool


@dataclass(frozen=True, slots=True)
class IndexReport:
    roots_completed: int
    entries_indexed: int
    errors: int
    cancelled: bool

    @property
    def complete(self) -> bool:
        return not self.cancelled and self.errors == 0


def _path_key(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _is_within(path: str, parent: str) -> bool:
    try:
        return os.path.commonpath((path, parent)) == parent
    except ValueError:
        return False


def _is_hidden_or_system(entry: os.DirEntry[str], stat_result: os.stat_result) -> bool:
    if entry.name.startswith("."):
        return True
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return bool(attributes & (_FILE_ATTRIBUTE_HIDDEN | _FILE_ATTRIBUTE_SYSTEM))


def index_roots(
    connection: sqlite3.Connection,
    roots: tuple[Path, ...],
    exclusions: tuple[Path, ...] = (),
    cancel_event: threading.Event | None = None,
    progress: Callable[[int], None] | None = None,
) -> IndexReport:
    """Index roots, pruning stale entries only after a root was fully traversed.

    Symlinks and hidden/system entries are skipped. A permission or I/O error
    makes that root incomplete, preserving its previously indexed rows.
    """
    exclusion_keys = tuple(_path_key(path) for path in exclusions)
    entries_indexed = 0
    errors = 0
    roots_completed = 0

    connection.execute("CREATE TEMP TABLE IF NOT EXISTS scan_seen(path TEXT PRIMARY KEY)")
    for configured_root in roots:
        if cancel_event is not None and cancel_event.is_set():
            return IndexReport(roots_completed, entries_indexed, errors, True)
        root = Path(configured_root).expanduser()
        root_key = _path_key(root)
        if any(_is_within(root_key, excluded) for excluded in exclusion_keys):
            continue
        if root.is_symlink() or not root.is_dir():
            errors += 1
            continue

        root_errors = 0
        root_entries = 0
        stack = [root]
        batch: list[tuple[str, str, str, str, int, float | None, int | None, str]] = []
        with connection:
            connection.execute("DELETE FROM scan_seen")

        def flush() -> None:
            nonlocal root_entries
            if not batch:
                return
            with connection:
                connection.executemany(
                    """INSERT INTO indexed_entries(
                           path, name, parent_path, extension, is_directory,
                           modified_at, size_bytes, scanned_at_utc
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(path) DO UPDATE SET
                           name = excluded.name,
                           parent_path = excluded.parent_path,
                           extension = excluded.extension,
                           is_directory = excluded.is_directory,
                           modified_at = excluded.modified_at,
                           size_bytes = excluded.size_bytes,
                           scanned_at_utc = excluded.scanned_at_utc""",
                    batch,
                )
                connection.executemany(
                    "INSERT OR IGNORE INTO scan_seen(path) VALUES (?)",
                    ((_path_key(row[0]),) for row in batch),
                )
            root_entries += len(batch)
            if progress is not None:
                progress(entries_indexed + root_entries)
            batch.clear()

        while stack:
            if cancel_event is not None and cancel_event.is_set():
                return IndexReport(roots_completed, entries_indexed + root_entries, errors + root_errors, True)
            directory = stack.pop()
            try:
                with os.scandir(directory) as children:
                    for entry in children:
                        if cancel_event is not None and cancel_event.is_set():
                            return IndexReport(
                                roots_completed,
                                entries_indexed + root_entries,
                                errors + root_errors,
                                True,
                            )
                        try:
                            if entry.is_symlink():
                                continue
                            stat_result = entry.stat(follow_symlinks=False)
                            if _is_hidden_or_system(entry, stat_result):
                                continue
                            child_path = Path(entry.path)
                            child_key = _path_key(child_path)
                            if any(_is_within(child_key, excluded) for excluded in exclusion_keys):
                                continue
                            is_directory = entry.is_dir(follow_symlinks=False)
                            batch.append(
                                (
                                    os.path.abspath(entry.path),
                                    entry.name,
                                    os.path.abspath(directory),
                                    "" if is_directory else child_path.suffix.casefold(),
                                    int(is_directory),
                                    stat_result.st_mtime,
                                    None if is_directory else stat_result.st_size,
                                    datetime.now(UTC).isoformat(),
                                )
                            )
                            if is_directory:
                                stack.append(child_path)
                            if len(batch) >= _BATCH_SIZE:
                                flush()
                        except OSError:
                            root_errors += 1
            except OSError:
                root_errors += 1

        flush()
        if root_errors == 0:
            # Also index the configured root itself, allowing a root name to
            # appear in results and making empty roots visible.
            try:
                root_stat = root.stat()
                with connection:
                    connection.execute(
                        """INSERT INTO indexed_entries(
                               path, name, parent_path, extension, is_directory,
                               modified_at, size_bytes, scanned_at_utc
                           ) VALUES (?, ?, ?, '', 1, ?, NULL, ?)
                           ON CONFLICT(path) DO UPDATE SET
                               name = excluded.name,
                               parent_path = excluded.parent_path,
                               is_directory = 1,
                               modified_at = excluded.modified_at,
                               size_bytes = NULL,
                               scanned_at_utc = excluded.scanned_at_utc""",
                        (
                            os.path.abspath(root),
                            root.name or str(root),
                            os.path.abspath(root.parent),
                            root_stat.st_mtime,
                            datetime.now(UTC).isoformat(),
                        ),
                    )
                    connection.execute("INSERT OR IGNORE INTO scan_seen(path) VALUES (?)", (root_key,))
                root_entries += 1
                if progress is not None:
                    progress(entries_indexed + root_entries)
            except OSError:
                root_errors += 1

        if root_errors == 0:
            # Only remove old rows below this root once traversal completed.
            seen_paths = {
                row["path"] for row in connection.execute("SELECT path FROM scan_seen").fetchall()
            }
            existing = connection.execute("SELECT path FROM indexed_entries").fetchall()
            stale = [
                (row["path"],)
                for row in existing
                if _is_within(_path_key(row["path"]), root_key)
                and _path_key(row["path"]) not in seen_paths
            ]
            for offset in range(0, len(stale), _BATCH_SIZE):
                with connection:
                    connection.executemany(
                        "DELETE FROM indexed_entries WHERE path = ?",
                        stale[offset : offset + _BATCH_SIZE],
                    )
            roots_completed += 1
        errors += root_errors
        entries_indexed += root_entries

    return IndexReport(roots_completed, entries_indexed, errors, False)


def search_files(
    connection: sqlite3.Connection,
    query: str,
    limit: int = 8,
    roots: tuple[Path, ...] | None = None,
    exclusions: tuple[Path, ...] = (),
) -> FileSearchResults:
    """Search indexed names and paths with FTS5 and deterministic tie handling."""
    if limit < 1:
        return FileSearchResults(query, (), False)
    tokens = _TOKEN_RE.findall(query.casefold())
    if not tokens or roots == ():
        return FileSearchResults(query, (), False)
    expression = " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"*' for token in tokens)
    scope_sql = ""
    parameters: list[object] = [" ".join(tokens), " ".join(tokens), expression]
    if roots is not None:
        scopes = []
        for root in roots:
            root_path = os.path.abspath(os.fspath(root))
            escaped = root_path.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            prefix = escaped.rstrip("\\/") + os.sep + "%"
            scopes.append("(e.path = ? COLLATE NOCASE OR e.path LIKE ? ESCAPE '!')")
            parameters.extend((root_path, prefix))
        scope_sql = " AND (" + " OR ".join(scopes) + ")" if scopes else " AND 0"
    if exclusions:
        excluded_sql = []
        for excluded in exclusions:
            excluded_path = os.path.abspath(os.fspath(excluded))
            escaped = excluded_path.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            prefix = escaped.rstrip("\\/") + os.sep + "%"
            excluded_sql.append("(e.path = ? COLLATE NOCASE OR e.path LIKE ? ESCAPE '!')")
            parameters.extend((excluded_path, prefix))
        scope_sql += " AND NOT (" + " OR ".join(excluded_sql) + ")"
    rows = connection.execute(
        """SELECT e.name, e.path, e.is_directory,
                  CASE
                    WHEN lower(e.name) = lower(?) THEN 100
                    WHEN lower(e.name) LIKE lower(?) || '%' THEN 90
                    ELSE 70
                  END AS score,
                  bm25(indexed_entries_fts, 4.0, 1.0) AS rank
           FROM indexed_entries_fts
           JOIN indexed_entries AS e ON e.id = indexed_entries_fts.rowid
           WHERE indexed_entries_fts MATCH ?""" + scope_sql + """
           ORDER BY score DESC, rank ASC, e.name COLLATE NOCASE, e.path COLLATE NOCASE
           LIMIT ?""",
        (*parameters, min(limit, 100)),
    ).fetchall()
    matches = tuple(
        FileResult(row["name"], row["path"], bool(row["is_directory"]), int(row["score"]))
        for row in rows
    )
    ambiguous = bool(matches) and sum(match.score == matches[0].score for match in matches) > 1
    return FileSearchResults(query, matches, ambiguous)
