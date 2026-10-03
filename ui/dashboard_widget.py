"""Compact, always-on-top dashboard for local search and upcoming tasks."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.application import LauncherItem, LauncherSearchResults
from todo.service import TaskService


class DashboardWidget(QWidget):
    """Show local search, task deadlines, and quick links in a small desktop panel."""

    def __init__(
        self,
        task_service: TaskService,
        search: Callable[[str, str], LauncherSearchResults],
        open_result: Callable[[LauncherItem], None],
        open_page: Callable[[str], None],
        timezone_id: str = "UTC",
        index_roots: tuple[str, ...] = (),
    ) -> None:
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.task_service = task_service
        self.search = search
        self.open_result = open_result
        self.open_page = open_page
        self.timezone = ZoneInfo(timezone_id)
        self.index_roots = index_roots
        self.setWindowTitle("MyAssistant")
        self.setObjectName("DashboardWidget")
        self.setMinimumSize(350, 520)
        self.resize(390, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(7)

        header = QHBoxLayout()
        brand = QLabel("◉  MyAssistant")
        brand.setObjectName("DashboardBrand")
        header.addWidget(brand, 1)
        settings = QPushButton("⚙")
        settings.setToolTip("Open settings")
        settings.clicked.connect(lambda: self._go_to_page("settings"))
        header.addWidget(settings)
        minimize = QPushButton("−")
        minimize.setToolTip("Minimize to the system tray")
        minimize.clicked.connect(self.hide)
        header.addWidget(minimize)
        layout.addLayout(header)

        self.greeting = QLabel()
        self.greeting.setObjectName("DashboardGreeting")
        layout.addWidget(self.greeting)

        deadline_heading = QHBoxLayout()
        heading = QLabel("Upcoming deadlines")
        heading.setObjectName("DashboardSection")
        deadline_heading.addWidget(heading, 1)
        view_all = QPushButton("View all  →")
        view_all.clicked.connect(lambda: self._go_to_page("tasks"))
        deadline_heading.addWidget(view_all)
        layout.addLayout(deadline_heading)
        self.deadline_list = QListWidget()
        self.deadline_list.setObjectName("DashboardDeadlines")
        self.deadline_list.setMaximumHeight(150)
        self.deadline_list.itemActivated.connect(lambda _item: self._go_to_page("tasks"))
        layout.addWidget(self.deadline_list)
        self.refresh_tasks()

        quick_heading = QLabel("Quick actions")
        quick_heading.setObjectName("DashboardSection")
        layout.addWidget(quick_heading)
        quick = QHBoxLayout()
        for label, page in (("Voice", "voice"), ("Tasks", "tasks"), ("Files", "files"), ("Settings", "settings")):
            button = QPushButton(label)
            button.setMinimumHeight(54)
            button.clicked.connect(lambda _checked=False, value=page: self._go_to_page(value))
            quick.addWidget(button)
        layout.addLayout(quick)

        search_heading = QLabel("Search applications and files")
        search_heading.setObjectName("DashboardSection")
        layout.addWidget(search_heading)
        search_row = QHBoxLayout()
        self.scope = QComboBox()
        self.scope.addItem("Files & folders", "files")
        self.scope.addItem("Applications", "applications")
        self.scope.currentIndexChanged.connect(self._refresh_results)
        search_row.addWidget(self.scope)
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search names and folders…")
        self.query.setClearButtonEnabled(True)
        self.query.textChanged.connect(self._queue_search)
        self.query.returnPressed.connect(self._open_current)
        search_row.addWidget(self.query, 1)
        layout.addLayout(search_row)
        self.search_status = QLabel()
        self.search_status.setObjectName("DashboardStatus")
        self.search_status.setWordWrap(True)
        layout.addWidget(self.search_status)
        self.search_results = QListWidget()
        self.search_results.setObjectName("DashboardResults")
        self.search_results.setMaximumHeight(96)
        self.search_results.itemActivated.connect(self._open_item)
        layout.addWidget(self.search_results)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self._refresh_results)
        self._update_search_status()
        self._position_on_screen()
        self._task_timer = QTimer(self)
        self._task_timer.setInterval(60_000)
        self._task_timer.timeout.connect(self.refresh_tasks)
        self._task_timer.start()

    def _position_on_screen(self) -> None:
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen is not None:
            bounds = screen.availableGeometry()
            self.move(bounds.right() - self.width() - 20, bounds.top() + 20)

    def refresh_tasks(self) -> None:
        now = datetime.now(UTC).astimezone(self.timezone)
        greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"
        self.greeting.setText(f"☀  {greeting}! Here are your upcoming tasks.")
        tasks = [task for task in self.task_service.list_tasks("open") if task.due_at_utc is not None]
        tasks.sort(key=lambda task: task.due_at_utc)
        self.deadline_list.clear()
        if not tasks:
            self.deadline_list.addItem("No upcoming deadlines. Add a task to see it here.")
            return
        for task in tasks[:5]:
            due = task.due_at_utc.astimezone(self.timezone)
            date_label = "Overdue" if due < now else "Today" if due.date() == now.date() else due.strftime("%d %b %Y")
            detail = task.description.strip().replace("\n", " ")
            summary = f"{task.title}\n{detail or date_label}   ·   {due:%I:%M %p}"
            item = QListWidgetItem(summary)
            item.setData(Qt.ItemDataRole.UserRole, task.id)
            self.deadline_list.addItem(item)

    def set_index_roots(self, roots: tuple[str, ...]) -> None:
        self.index_roots = roots
        self._refresh_results()

    def _update_search_status(self) -> None:
        if self.scope.currentData() == "files" and not self.index_roots:
            self.query.setPlaceholderText("Choose searchable folders first…")
            self.search_status.setText("File search is off. Choose folders in Settings to enable it.")
        elif self.scope.currentData() == "files":
            self.query.setPlaceholderText("Search file and folder names…")
            self.search_status.setText("Search names and paths in your configured folders.")
        else:
            self.query.setPlaceholderText("Search installed applications…")
            self.search_status.setText("Search applications discovered from your Start Menu.")

    def _queue_search(self, _text: str = "") -> None:
        self._search_timer.start()

    def _refresh_results(self, *_args) -> None:
        self._update_search_status()
        query = self.query.text().strip()
        self.search_results.clear()
        if not query:
            return
        try:
            results = self.search(query, self.scope.currentData())
        except Exception:
            self.search_status.setText("Search is temporarily unavailable.")
            return
        for result in results.matches:
            item = QListWidgetItem(f"{result.name}\n{result.kind}  ·  {result.target}")
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.search_results.addItem(item)
        if self.search_results.count():
            self.search_results.setCurrentRow(0)
        if self.scope.currentData() == "files" and not self.index_roots:
            self.search_status.setText("File search is off. Choose folders in Settings to enable it.")
        elif not results.matches:
            self.search_status.setText("No matching applications, files, or folders.")

    def _open_current(self) -> None:
        item = self.search_results.currentItem()
        if item is not None:
            self._open_item(item)

    def _open_item(self, item: QListWidgetItem) -> None:
        result = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(result, LauncherItem):
            try:
                self.open_result(result)
                self.hide()
            except Exception as exc:
                self.search_status.setText(f"Could not open result: {exc}")

    def _go_to_page(self, page: str) -> None:
        self.hide()
        self.open_page(page)

    def show_and_focus(self) -> None:
        self.refresh_tasks()
        self.show()
        self.raise_()
        self.activateWindow()
        self.query.setFocus(Qt.FocusReason.OtherFocusReason)

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show_and_focus()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        event.ignore()
        self.hide()
