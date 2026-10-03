"""Composition and lifecycle for the headless application foundation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import Event

from config import Settings
from core.database import Database
from core.logging_setup import configure_logging, shutdown_logging
from launcher.catalog import ApplicationCatalog, SearchResults
from launcher.discovery import discover_shortcuts
from launcher.opening import ApplicationOpener
from search.filesystem import IndexReport, index_roots, search_files
from todo.service import TaskService


@dataclass(frozen=True, slots=True)
class LauncherItem:
    name: str
    target: str
    kind: str
    score: int


@dataclass(frozen=True, slots=True)
class LauncherSearchResults:
    query: str
    matches: tuple[LauncherItem, ...]
    ambiguous: bool


class Application:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()
        self.logger: logging.Logger | None = None
        self.database: Database | None = None
        self.catalog: ApplicationCatalog | None = None
        self.opener: ApplicationOpener | None = None
        self.task_service: TaskService | None = None

    def start(self) -> None:
        if self.database is not None:
            raise RuntimeError("Application is already started")
        self.settings.paths.ensure_directories()
        self.logger = configure_logging(self.settings.paths.log_dir, self.settings.log_level)
        database = Database(self.settings.paths.database)
        try:
            connection = database.open()
            self.catalog = ApplicationCatalog(connection)
            self.opener = ApplicationOpener(connection)
            self.task_service = TaskService(connection)
            report = discover_shortcuts()
            indexed = self.catalog.refresh(report)
            self.logger.info(
                "Application catalog refreshed: %d shortcut(s), complete=%s, errors=%d",
                indexed,
                report.complete,
                report.errors,
            )
        except BaseException:
            # Release any partially initialized DB resources, then preserve the
            # original startup error for the caller.
            database.close()
            self.catalog = None
            self.opener = None
            self.task_service = None
            self.logger.exception("Application database initialization failed")
            raise
        self.database = database
        self.logger.info("Application foundation initialized")

    def search_applications(self, query: str, limit: int = 8) -> SearchResults:
        if self.catalog is None:
            raise RuntimeError("Application must be started before searching")
        return self.catalog.search(query, limit)

    def open_application(self, launch_target: str) -> None:
        if self.opener is None:
            raise RuntimeError("Application must be started before launching")
        self.opener.open_selected(launch_target)

    def index_filesystem(self, cancel_event: Event | None = None) -> IndexReport:
        if self.database is None or self.database.connection is None:
            raise RuntimeError("Application must be started before indexing")
        return index_roots(
            self.database.connection,
            self.settings.index_roots,
            self.settings.index_exclusions,
            cancel_event,
        )

    def search_launcher(
        self, query: str, limit: int = 8, scope: str = "all"
    ) -> LauncherSearchResults:
        if self.catalog is None or self.database is None or self.database.connection is None:
            raise RuntimeError("Application must be started before searching")
        if scope not in {"all", "applications", "files"}:
            raise ValueError(f"Unsupported launcher search scope: {scope!r}")
        apps = self.catalog.search(query, limit) if scope in {"all", "applications"} else None
        files = (
            search_files(
                self.database.connection,
                query,
                limit,
                self.settings.index_roots,
                self.settings.index_exclusions,
            )
            if scope in {"all", "files"}
            else None
        )
        items = [
            LauncherItem(result.name, result.launch_target, "APPLICATION", result.score)
            for result in (apps.matches if apps is not None else ())
        ]
        items.extend(
            LauncherItem(
                result.name,
                result.path,
                "FOLDER" if result.is_directory else "FILE",
                result.score,
            )
            for result in (files.matches if files is not None else ())
        )
        items.sort(key=lambda item: (-item.score, item.name.casefold(), item.target.casefold()))
        matches = tuple(items[:limit])
        ambiguous = bool(matches) and sum(item.score == matches[0].score for item in matches) > 1
        return LauncherSearchResults(query, matches, ambiguous)

    def open_search_result(self, item: LauncherItem) -> None:
        if self.opener is None:
            raise RuntimeError("Application must be started before launching")
        if item.kind == "APPLICATION":
            self.opener.open_selected(item.target)
        elif item.kind in {"FILE", "FOLDER"}:
            self.opener.open_indexed_path(
                item.target,
                self.settings.index_roots,
                self.settings.index_exclusions,
            )
        else:
            raise ValueError(f"Unsupported launcher result kind: {item.kind}")

    def close(self) -> None:
        database = self.database
        self.database = None
        try:
            if database is not None:
                database.close()
        finally:
            self.catalog = None
            self.opener = None
            self.task_service = None
            try:
                if self.logger is not None:
                    self.logger.info("Application foundation stopped")
            finally:
                shutdown_logging(self.logger)
                self.logger = None
