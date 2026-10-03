"""Task editor/list UI backed by the local TaskService."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from PySide6.QtCore import QDate, QTime, QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from todo.service import (
    AmbiguousLocalTimeError,
    Task,
    TaskService,
    resolve_local_deadline,
)


class TaskPanel(QWidget):
    def __init__(self, service: TaskService, timezone_id: str = "UTC") -> None:
        super().__init__()
        self.service = service
        self.default_timezone = timezone_id
        self._editing_task_id: int | None = None
        self._tasks: dict[int, Task] = {}

        layout = QVBoxLayout(self)
        heading = QLabel("Tasks and deadlines")
        heading.setObjectName("TaskHeading")
        layout.addWidget(heading)

        filters = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter tasks…")
        self.status_filter = QComboBox()
        for title, value in (("Open", "open"), ("Completed", "completed"), ("All", "all")):
            self.status_filter.addItem(title, value)
        filters.addWidget(self.filter_input, 1)
        filters.addWidget(self.status_filter)
        layout.addLayout(filters)

        self.task_list = QListWidget()
        self.task_list.currentItemChanged.connect(self._selection_changed)
        layout.addWidget(self.task_list, 1)

        form = QFormLayout()
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("What needs to get done?")
        form.addRow("Title", self.title_input)

        self.description_input = QLineEdit()
        form.addRow("Description", self.description_input)

        deadline_row = QHBoxLayout()
        self.deadline_enabled = QCheckBox("Set deadline")
        configured_zone = ZoneInfo(timezone_id)
        local_now = datetime.now(configured_zone)
        self.deadline_date = QDateEdit(QDate(local_now.year, local_now.month, local_now.day))
        self.deadline_date.setDisplayFormat("yyyy-MM-dd")
        self.deadline_date.setCalendarPopup(True)
        self.deadline_time = QTimeEdit(QTime(local_now.hour, local_now.minute))
        self.deadline_time.setDisplayFormat("HH:mm")
        self.timezone_input = QLineEdit(timezone_id)
        self.timezone_input.setPlaceholderText("IANA zone, e.g. Asia/Kathmandu")
        deadline_row.addWidget(self.deadline_enabled)
        deadline_row.addWidget(self.deadline_date)
        deadline_row.addWidget(self.deadline_time)
        form.addRow("Deadline", deadline_row)
        form.addRow("Timezone", self.timezone_input)

        self.priority_input = QComboBox()
        for label, priority in (
            ("Urgent", 1),
            ("High", 2),
            ("Normal", 3),
            ("Low", 4),
            ("Someday", 5),
        ):
            self.priority_input.addItem(label, priority)
        form.addRow("Priority", self.priority_input)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Comma separated")
        form.addRow("Tags", self.tags_input)

        self.project_input = QLineEdit()
        self.project_input.setPlaceholderText("Optional absolute path")
        form.addRow("Project path", self.project_input)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Add task")
        self.clear_button = QPushButton("Clear")
        self.complete_button = QPushButton("Complete")
        self.delete_button = QPushButton("Delete")
        self.complete_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        buttons.addWidget(self.complete_button)
        buttons.addWidget(self.delete_button)
        layout.addLayout(buttons)

        self.status = QLabel("Tasks are stored locally.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.filter_input.textChanged.connect(self._refresh_tasks)
        self.status_filter.currentIndexChanged.connect(self._refresh_tasks)
        self.save_button.clicked.connect(self._save_task)
        self.clear_button.clicked.connect(self._clear_form)
        self.complete_button.clicked.connect(self._toggle_completed)
        self.delete_button.clicked.connect(self._delete_task)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(30_000)
        self._countdown_timer.timeout.connect(self._refresh_countdowns)
        self._countdown_timer.start()
        self._refresh_tasks()

    def _refresh_tasks(self, *_args) -> None:
        selected_id = self._editing_task_id
        tasks = self.service.list_tasks(
            self.status_filter.currentData(), self.filter_input.text()
        )
        self._tasks = {task.id: task for task in tasks}
        self.task_list.blockSignals(True)
        self.task_list.clear()
        selected_item = None
        for task in tasks:
            item = QListWidgetItem(self._task_label(task))
            item.setData(Qt.ItemDataRole.UserRole, task.id)
            self.task_list.addItem(item)
            if task.id == selected_id:
                selected_item = item
        if selected_item is not None:
            self.task_list.setCurrentItem(selected_item)
        self.task_list.blockSignals(False)
        if selected_item is None and selected_id is not None:
            self._clear_form()
        self._update_action_buttons()

    def _task_label(self, task: Task) -> str:
        countdown = self.service.countdown(task)
        due = "No deadline"
        if task.due_at_utc is not None:
            zone = ZoneInfo(task.timezone_id) if task.timezone_id else UTC
            local_due = task.due_at_utc.astimezone(zone)
            due = f"{local_due:%Y-%m-%d %H:%M} {task.timezone_id or 'UTC'}"
        state = "✓" if task.is_completed else f"Priority {task.priority}"
        return f"{task.title}\n{state}  ·  {countdown}  ·  {due}"

    def _refresh_countdowns(self) -> None:
        for index in range(self.task_list.count()):
            item = self.task_list.item(index)
            task_id = item.data(Qt.ItemDataRole.UserRole)
            task = self._tasks.get(task_id)
            if task is not None:
                item.setText(self._task_label(task))

    def _selection_changed(self, current, _previous) -> None:
        if current is None:
            self._editing_task_id = None
            self._update_action_buttons()
            return
        task = self._tasks.get(current.data(Qt.ItemDataRole.UserRole))
        if task is None:
            return
        self._editing_task_id = task.id
        self.title_input.setText(task.title)
        self.description_input.setText(task.description)
        self.priority_input.setCurrentIndex(task.priority - 1)
        self.tags_input.setText(", ".join(task.tags))
        self.project_input.setText(task.project_path or "")
        self.deadline_enabled.setChecked(task.due_at_utc is not None)
        if task.due_at_utc is not None:
            timezone_id = task.timezone_id or self.default_timezone
            self.timezone_input.setText(timezone_id)
            local_due = task.due_at_utc.astimezone(ZoneInfo(timezone_id))
            self.deadline_date.setDate(QDate(local_due.year, local_due.month, local_due.day))
            self.deadline_time.setTime(QTime(local_due.hour, local_due.minute))
        else:
            self.timezone_input.setText(self.default_timezone)
        self._update_action_buttons(task)

    def _save_task(self) -> None:
        title = self.title_input.text()
        try:
            due_at = None
            timezone_id = None
            if self.deadline_enabled.isChecked():
                timezone_id = self.timezone_input.text().strip()
                local_time = datetime.combine(
                    self.deadline_date.date().toPython(),
                    self.deadline_time.time().toPython(),
                )
                try:
                    due_at = resolve_local_deadline(local_time, timezone_id)
                except AmbiguousLocalTimeError:
                    answer = QMessageBox.question(
                        self,
                        "Ambiguous deadline time",
                        "This local time occurs twice. Use the first occurrence? Choose No for the second.",
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No
                        | QMessageBox.StandardButton.Cancel,
                    )
                    if answer == QMessageBox.StandardButton.Cancel:
                        self.status.setText("Deadline was not changed.")
                        return
                    due_at = resolve_local_deadline(
                        local_time,
                        timezone_id,
                        fold=0 if answer == QMessageBox.StandardButton.Yes else 1,
                    )
            tags = tuple(part.strip() for part in self.tags_input.text().split(","))
            common = {
                "description": self.description_input.text(),
                "priority": self.priority_input.currentData(),
                "due_at": due_at,
                "timezone_id": timezone_id,
                "project_path": self.project_input.text() or None,
                "tags": tags,
            }
            if self._editing_task_id is None:
                task = self.service.create_task(title, **common)
                self.status.setText(f"Added “{task.title}”.")
            else:
                task = self.service.update_task(self._editing_task_id, title=title, **common)
                self.status.setText(f"Saved changes to “{task.title}”.")
        except (KeyError, ValueError) as exc:
            self.status.setText(str(exc))
            return
        self._editing_task_id = task.id
        self._refresh_tasks()

    def _clear_form(self) -> None:
        self._editing_task_id = None
        self.title_input.clear()
        self.description_input.clear()
        self.priority_input.setCurrentIndex(2)
        self.tags_input.clear()
        self.project_input.clear()
        self.deadline_enabled.setChecked(False)
        self.timezone_input.setText(self.default_timezone)
        self._refresh_tasks()

    def _toggle_completed(self) -> None:
        if self._editing_task_id is None:
            return
        task = self._tasks.get(self._editing_task_id)
        if task is None:
            return
        updated = self.service.set_completed(task.id, not task.is_completed)
        self.status.setText("Task reopened." if not updated.is_completed else "Task completed.")
        self._refresh_tasks()

    def _delete_task(self) -> None:
        if self._editing_task_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete task",
            "Delete this task and its reminder history? This cannot be undone.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.service.delete_task(self._editing_task_id)
        self.status.setText("Task deleted.")
        self._clear_form()

    def _update_action_buttons(self, task: Task | None = None) -> None:
        if task is None and self._editing_task_id is not None:
            task = self._tasks.get(self._editing_task_id)
        selected = task is not None
        self.save_button.setText("Save changes" if selected else "Add task")
        self.complete_button.setEnabled(selected)
        self.delete_button.setEnabled(selected)
        if selected:
            self.complete_button.setText("Reopen" if task.is_completed else "Complete")
