"""Keyboard-first launcher UI connected to application search services."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from core.application import LauncherItem, LauncherSearchResults


class SearchInput(QLineEdit):
    move_selection = Signal(int)
    activate_selection = Signal()
    dismiss = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if event.key() == Qt.Key.Key_Down:
            self.move_selection.emit(1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Up:
            self.move_selection.emit(-1)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate_selection.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class LauncherWindow(QMainWindow):
    """Render catalog search results and open only the explicitly selected app."""

    result_activated = Signal(object)
    exit_requested = Signal()
    hidden = Signal()

    def __init__(
        self,
        search_applications: Callable[[str], LauncherSearchResults],
        open_application: Callable[[LauncherItem], None],
        task_panel: QWidget | None = None,
        voice_panel: QWidget | None = None,
    ) -> None:
        super().__init__()
        self._search_applications = search_applications
        self._open_application = open_application
        self._tray_available = False
        self.setWindowTitle("MyAssistant")
        self.setMinimumSize(560, 420)
        self.resize(700, 500)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 22)
        layout.setSpacing(14)

        eyebrow = QLabel("MYASSISTANT  /  QUICK LAUNCHER")
        eyebrow.setObjectName("Eyebrow")
        layout.addWidget(eyebrow)

        heading = QLabel("What are you looking for?")
        heading.setObjectName("Heading")
        layout.addWidget(heading)

        self.search_input = SearchInput()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Search applications, files, and folders…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_results)
        self.search_input.move_selection.connect(self._move_selection)
        self.search_input.activate_selection.connect(self._activate_current)
        self.search_input.dismiss.connect(self.hide)
        layout.addWidget(self.search_input)

        self.match_notice = QLabel("Search your discovered applications and indexed locations")
        self.match_notice.setObjectName("MatchNotice")
        self.match_notice.setWordWrap(True)
        layout.addWidget(self.match_notice)

        self.results = QListWidget()
        self.results.setObjectName("Results")
        self.results.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results.itemDoubleClicked.connect(self._activate_item)
        layout.addWidget(self.results, 1)

        footer = QLabel("↑ ↓  Navigate     ↵  Open selected result     Esc  Hide     Ctrl+Q  Quit")
        footer.setObjectName("Footer")
        layout.addWidget(footer)

        tabs = QTabWidget(self)
        tabs.addTab(container, "Search")
        if task_panel is not None:
            tabs.addTab(task_panel, "Tasks")
        if voice_panel is not None:
            tabs.addTab(voice_panel, "Voice")
        self.setCentralWidget(tabs)
        self.setStyleSheet(
            """
            QMainWindow { background: #11151d; }
            QWidget { color: #edf2fa; font-family: 'Segoe UI'; }
            QLabel#Eyebrow { color: #6cc7bd; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
            QLabel#Heading { color: #f4f7fb; font-size: 25px; font-weight: 600; padding-bottom: 3px; }
            QLineEdit#SearchInput {
                background: #1a202b; border: 1px solid #394655; border-radius: 10px;
                padding: 14px 16px; color: #ffffff; font-size: 17px;
                selection-background-color: #397f7a;
            }
            QLineEdit#SearchInput:focus { border: 1px solid #6cc7bd; }
            QLabel#MatchNotice {
                color: #9eb8b5; background: #1b292c; border: 1px solid #30494a;
                border-radius: 7px; padding: 9px 11px; font-size: 11px;
            }
            QListWidget#Results {
                background: #171c25; border: 1px solid #2c3541; border-radius: 10px;
                outline: 0; padding: 5px;
            }
            QListWidget#Results::item { padding: 14px 12px; border-radius: 7px; color: #e8edf5; }
            QListWidget#Results::item:selected { background: #263b43; border: 1px solid #47766f; }
            QLabel#Footer { color: #8995a5; font-size: 11px; padding-top: 2px; }
            """
        )

        self.statusBar().setStyleSheet("color: #aab5c2; background: #11151d; border: 0;")
        self.statusBar().showMessage("Type to search applications, files, and folders.")

        self.exit_action = QAction("Exit MyAssistant", self)
        self.exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        self.exit_action.triggered.connect(self.exit_requested.emit)
        self.addAction(self.exit_action)

        self._refresh_results("")

    def _refresh_results(self, query: str) -> None:
        try:
            search = self._search_applications(query)
        except Exception as exc:
            self.results.clear()
            self.match_notice.setText("Search is temporarily unavailable.")
            self.statusBar().showMessage(f"Search failed: {exc}")
            return
        self.results.clear()
        for result in search.matches:
            item = QListWidgetItem(f"{result.name}\n{result.kind}  ·  {result.target}")
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.results.addItem(item)
        if search.ambiguous:
            self.match_notice.setText("Several results match equally. Choose the intended result.")
        else:
            self.match_notice.setText("Search your discovered applications and indexed locations")
        if self.results.count():
            self.results.setCurrentRow(0)
            self.statusBar().showMessage(f"{self.results.count()} result(s). Press Enter to open.")
        else:
            message = "No results found." if query.strip() else "Type to search applications, files, and folders."
            self.statusBar().showMessage(message)

    def _move_selection(self, offset: int) -> None:
        count = self.results.count()
        if count == 0:
            return
        current = self.results.currentRow()
        self.results.setCurrentRow((current + offset) % count)

    def _activate_current(self) -> None:
        item = self.results.currentItem()
        if item is not None:
            self._activate_item(item)

    def _activate_item(self, item: QListWidgetItem) -> None:
        result = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(result, LauncherItem):
            try:
                self._open_application(result)
            except Exception as exc:
                self.statusBar().showMessage(f"Could not open {result.name}: {exc}")
                return
            self.result_activated.emit(result)
            self.statusBar().showMessage(f"Opened {result.name}.")
            self.hide()

    def show_and_focus(self) -> None:
        self.show()
        screen = QApplication.primaryScreen()
        if screen is not None:
            bounds = screen.availableGeometry()
            self.move(bounds.center() - self.rect().center())
        self.raise_()
        self.activateWindow()
        # Window activation is asynchronous on Windows. Focus after Qt has
        # completed the show/activation event so reopening behaves consistently.
        QTimer.singleShot(0, lambda: self.search_input.setFocus(Qt.FocusReason.OtherFocusReason))

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show_and_focus()

    def set_tray_available(self, available: bool) -> None:
        self._tray_available = available

    def set_index_status(self, text: str) -> None:
        self.match_notice.setText(text)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if self._tray_available:
            event.ignore()
            self.hide()
        else:
            event.accept()
            self.exit_requested.emit()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override name
        self.hidden.emit()
        super().hideEvent(event)


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create a Qt application that remains alive while the launcher is hidden."""
    app = QApplication.instance()
    if app is None:
        import sys

        app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("MyAssistant")
    app.setQuitOnLastWindowClosed(False)
    return app
