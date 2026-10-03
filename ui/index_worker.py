"""Qt worker for scanning configured roots without blocking launcher input."""

from __future__ import annotations

from threading import Event

from PySide6.QtCore import QThread, Signal

from core.database import Database
from search.filesystem import index_roots


class IndexWorker(QThread):
    progress = Signal(int)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, database_path, roots, exclusions) -> None:
        super().__init__()
        self.database_path = database_path
        self.roots = roots
        self.exclusions = exclusions
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        database = Database(self.database_path)
        try:
            connection = database.open()
            report = index_roots(
                connection,
                self.roots,
                self.exclusions,
                self.cancel_event,
                self.progress.emit,
            )
            self.completed.emit(report)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            database.close()
