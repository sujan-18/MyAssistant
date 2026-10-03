"""Persist and search the locally discovered application catalog."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from launcher.discovery import DiscoveryReport


_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class AppResult:
    name: str
    launch_target: str
    score: int


@dataclass(frozen=True, slots=True)
class SearchResults:
    query: str
    matches: tuple[AppResult, ...]
    ambiguous: bool


class ApplicationCatalog:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def refresh(self, report: DiscoveryReport) -> int:
        """Upsert findings and prune stale Start Menu rows only after a full scan."""
        now = datetime.now(UTC).isoformat()
        with self.connection:
            for shortcut in report.shortcuts:
                self.connection.execute(
                    """INSERT INTO applications(name, launch_target, source, discovered_at_utc)
                       VALUES (?, ?, 'start-menu', ?)
                       ON CONFLICT(launch_target) DO UPDATE SET
                         name = excluded.name,
                         source = excluded.source,
                         discovered_at_utc = excluded.discovered_at_utc""",
                    (shortcut.name, str(shortcut.shortcut_path), now),
                )
            if report.complete:
                paths = [str(shortcut.shortcut_path) for shortcut in report.shortcuts]
                if paths:
                    placeholders = ",".join("?" for _ in paths)
                    self.connection.execute(
                        f"DELETE FROM applications WHERE source = 'start-menu' AND launch_target NOT IN ({placeholders})",
                        paths,
                    )
                else:
                    self.connection.execute("DELETE FROM applications WHERE source = 'start-menu'")
        return len(report.shortcuts)

    def search(self, query: str, limit: int = 8) -> SearchResults:
        normalized = " ".join(_TOKEN_RE.findall(query.casefold()))
        if not normalized or limit < 1:
            return SearchResults(query, (), False)

        query_tokens = normalized.split()
        rows = self.connection.execute(
            "SELECT name, launch_target FROM applications ORDER BY name COLLATE NOCASE"
        ).fetchall()
        ranked: list[AppResult] = []
        for row in rows:
            name = row["name"]
            candidate = " ".join(_TOKEN_RE.findall(name.casefold()))
            candidate_tokens = candidate.split()
            if candidate == normalized:
                score = 100
            elif candidate.startswith(normalized):
                score = 90
            elif all(token in candidate_tokens for token in query_tokens):
                score = 80
            elif normalized in candidate:
                score = 60
            else:
                continue
            ranked.append(AppResult(name, row["launch_target"], score))

        ranked.sort(key=lambda result: (-result.score, result.name.casefold(), result.launch_target.casefold()))
        best = ranked[0].score if ranked else 0
        ambiguous = sum(result.score == best for result in ranked) > 1
        return SearchResults(query, tuple(ranked[:limit]), ambiguous)
