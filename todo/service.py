"""SQLite-backed tasks with timezone-aware deadlines and reminder records."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


TaskStatus = Literal["open", "completed", "all"]
_UNSET = object()


class AmbiguousLocalTimeError(ValueError):
    """A wall time occurs twice during a daylight-saving transition."""


class NonexistentLocalTimeError(ValueError):
    """A wall time is skipped during a daylight-saving transition."""


@dataclass(frozen=True, slots=True)
class Task:
    id: int
    title: str
    description: str
    priority: int
    due_at_utc: datetime | None
    timezone_id: str | None
    project_path: str | None
    completed_at_utc: datetime | None
    created_at_utc: datetime
    updated_at_utc: datetime
    tags: tuple[str, ...]

    @property
    def is_completed(self) -> bool:
        return self.completed_at_utc is not None


@dataclass(frozen=True, slots=True)
class ReminderNotice:
    task: Task
    reminder_key: str
    scheduled_for_utc: datetime


def resolve_local_deadline(
    local_time: datetime,
    timezone_id: str,
    fold: int | None = None,
) -> datetime:
    """Resolve a wall time to an aware datetime, rejecting DST gaps/ambiguity.

    If the wall time occurs twice during a backward transition, callers must
    supply fold=0 for its first occurrence or fold=1 for its second.
    """
    if local_time.tzinfo is not None:
        raise ValueError("Local deadline input must not already have a timezone")
    if fold is not None and (isinstance(fold, bool) or fold not in (0, 1)):
        raise ValueError("fold must be 0 or 1")
    try:
        timezone = ZoneInfo(timezone_id)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown IANA timezone: {timezone_id!r}") from exc

    candidates: dict[int, datetime] = {}
    for candidate_fold in (0, 1):
        candidate = local_time.replace(tzinfo=timezone, fold=candidate_fold)
        round_trip = candidate.astimezone(UTC).astimezone(timezone).replace(tzinfo=None)
        if round_trip == local_time:
            candidates[candidate_fold] = candidate
    if not candidates:
        raise NonexistentLocalTimeError(
            "This local time does not exist because of a timezone transition"
        )

    distinct_instants = {candidate.astimezone(UTC) for candidate in candidates.values()}
    if len(distinct_instants) > 1:
        if fold is None:
            raise AmbiguousLocalTimeError(
                "This local time is ambiguous; choose the first or second occurrence"
            )
        return candidates[fold]
    if fold is not None and fold in candidates:
        return candidates[fold]
    return next(iter(candidates.values()))


class TaskService:
    """Validate and persist tasks using the shared application SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_task(
        self,
        title: str,
        *,
        description: str = "",
        priority: int = 3,
        due_at: datetime | None = None,
        timezone_id: str | None = None,
        project_path: str | Path | None = None,
        tags: tuple[str, ...] | list[str] = (),
        now: datetime | None = None,
    ) -> Task:
        clean_title = self._validate_title(title)
        clean_description = description.strip()
        self._validate_priority(priority)
        due_utc, stored_timezone = self._normalize_deadline(due_at, timezone_id)
        normalized_project = self._normalize_project_path(project_path)
        normalized_tags = self._normalize_tags(tags)
        instant = self._normalize_now(now)
        with self.connection:
            cursor = self.connection.execute(
                """INSERT INTO tasks(
                       title, description, priority, due_at_utc, timezone_id,
                       project_path, created_at_utc, updated_at_utc
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    clean_title,
                    clean_description,
                    priority,
                    self._serialize(due_utc),
                    stored_timezone,
                    normalized_project,
                    self._serialize(instant),
                    self._serialize(instant),
                ),
            )
            task_id = int(cursor.lastrowid)
            self._replace_tags(task_id, normalized_tags)
        return self.get_task(task_id)

    def update_task(
        self,
        task_id: int,
        *,
        title: str | object = _UNSET,
        description: str | object = _UNSET,
        priority: int | object = _UNSET,
        due_at: datetime | None | object = _UNSET,
        timezone_id: str | None | object = _UNSET,
        project_path: str | Path | None | object = _UNSET,
        tags: tuple[str, ...] | list[str] | object = _UNSET,
        now: datetime | None = None,
    ) -> Task:
        current = self.get_task(task_id)
        clean_title = current.title if title is _UNSET else self._validate_title(title)
        clean_description = current.description if description is _UNSET else description.strip()
        clean_priority = current.priority if priority is _UNSET else priority
        self._validate_priority(clean_priority)
        if due_at is _UNSET:
            due_utc = current.due_at_utc
            stored_timezone = current.timezone_id if timezone_id is _UNSET else timezone_id
            if due_utc is None and stored_timezone is not None:
                raise ValueError("A timezone cannot be set without a deadline")
            if stored_timezone is not None:
                try:
                    ZoneInfo(stored_timezone)
                except (ZoneInfoNotFoundError, ValueError) as exc:
                    raise ValueError(f"Unknown IANA timezone: {stored_timezone!r}") from exc
        else:
            due_utc, stored_timezone = self._normalize_deadline(
                due_at,
                None if timezone_id is _UNSET else timezone_id,
            )
        normalized_project = (
            current.project_path
            if project_path is _UNSET
            else self._normalize_project_path(project_path)
        )
        normalized_tags = current.tags if tags is _UNSET else self._normalize_tags(tags)
        instant = self._normalize_now(now)
        with self.connection:
            self.connection.execute(
                """UPDATE tasks SET title = ?, description = ?, priority = ?,
                       due_at_utc = ?, timezone_id = ?, project_path = ?, updated_at_utc = ?
                   WHERE id = ?""",
                (
                    clean_title,
                    clean_description,
                    clean_priority,
                    self._serialize(due_utc),
                    stored_timezone,
                    normalized_project,
                    self._serialize(instant),
                    task_id,
                ),
            )
            self._replace_tags(task_id, normalized_tags)
        return self.get_task(task_id)

    def get_task(self, task_id: int) -> Task:
        row = self.connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"Task {task_id} does not exist")
        tags = self.connection.execute(
            "SELECT tag FROM task_tags WHERE task_id = ? ORDER BY tag COLLATE NOCASE",
            (task_id,),
        ).fetchall()
        return self._from_row(row, tuple(tag["tag"] for tag in tags))

    def list_tasks(self, status: TaskStatus = "open", query: str = "") -> tuple[Task, ...]:
        if status not in {"open", "completed", "all"}:
            raise ValueError(f"Unsupported task status: {status!r}")
        clauses: list[str] = []
        parameters: list[object] = []
        if status == "open":
            clauses.append("completed_at_utc IS NULL")
        elif status == "completed":
            clauses.append("completed_at_utc IS NOT NULL")
        normalized_query = query.strip()
        if normalized_query:
            escaped_query = normalized_query.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            needle = f"%{escaped_query}%"
            clauses.append(
                """(title LIKE ? ESCAPE '!' OR description LIKE ? ESCAPE '!'
                   OR EXISTS (SELECT 1 FROM task_tags WHERE task_id = tasks.id
                              AND tag LIKE ? ESCAPE '!'))"""
            )
            parameters.extend((needle, needle, needle))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.connection.execute(
            f"""SELECT * FROM tasks {where}
                ORDER BY (completed_at_utc IS NOT NULL),
                         (due_at_utc IS NULL), due_at_utc, priority, created_at_utc DESC""",
            parameters,
        ).fetchall()
        if not rows:
            return ()
        ids = tuple(row["id"] for row in rows)
        placeholders = ",".join("?" for _ in ids)
        tag_rows = self.connection.execute(
            f"SELECT task_id, tag FROM task_tags WHERE task_id IN ({placeholders}) "
            "ORDER BY tag COLLATE NOCASE",
            ids,
        ).fetchall()
        tags_by_task: dict[int, list[str]] = {}
        for row in tag_rows:
            tags_by_task.setdefault(row["task_id"], []).append(row["tag"])
        return tuple(self._from_row(row, tuple(tags_by_task.get(row["id"], ()))) for row in rows)

    def set_completed(
        self,
        task_id: int,
        completed: bool = True,
        now: datetime | None = None,
    ) -> Task:
        self.get_task(task_id)
        updated_at = self._normalize_now(now)
        completed_at = self._serialize(updated_at) if completed else None
        with self.connection:
            self.connection.execute(
                "UPDATE tasks SET completed_at_utc = ?, updated_at_utc = ? WHERE id = ?",
                (completed_at, self._serialize(updated_at), task_id),
            )
        return self.get_task(task_id)

    def delete_task(self, task_id: int) -> bool:
        with self.connection:
            cursor = self.connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0

    def countdown(self, task: Task, now: datetime | None = None) -> str:
        if task.is_completed:
            return "Completed"
        if task.due_at_utc is None:
            return "No deadline"
        remaining = task.due_at_utc - self._normalize_now(now)
        if remaining.total_seconds() <= 0:
            return "Deadline passed"
        total_minutes = int(remaining.total_seconds() // 60)
        days, remainder = divmod(total_minutes, 24 * 60)
        hours, minutes = divmod(remainder, 60)
        components = []
        if days:
            components.append(f"{days}d")
        if hours:
            components.append(f"{hours}h")
        if minutes or not components:
            components.append(f"{minutes}m")
        return "Due in " + " ".join(components)

    def pending_reminders(
        self,
        now: datetime | None = None,
        offsets: tuple[timedelta, ...] = (timedelta(hours=1), timedelta(minutes=15)),
    ) -> tuple[ReminderNotice, ...]:
        instant = self._normalize_now(now)
        clean_offsets = sorted({offset for offset in offsets if offset.total_seconds() > 0}, reverse=True)
        notices: list[ReminderNotice] = []
        for task in self.list_tasks("open"):
            deadline = task.due_at_utc
            if deadline is None:
                continue
            key: str | None = None
            if instant >= deadline:
                key = f"{self._serialize(deadline)}|overdue"
            else:
                for position, offset in enumerate(clean_offsets):
                    boundary = deadline - offset
                    next_boundary = (
                        deadline - clean_offsets[position + 1]
                        if position + 1 < len(clean_offsets)
                        else deadline
                    )
                    if boundary <= instant < next_boundary:
                        key = f"{self._serialize(deadline)}|before:{int(offset.total_seconds())}"
                        break
            if key and not self._was_reminded(task.id, key):
                notices.append(ReminderNotice(task, key, instant))
        return tuple(notices)

    def record_reminder(
        self,
        task_id: int,
        reminder_key: str,
        delivered_at: datetime | None = None,
    ) -> bool:
        self.get_task(task_id)
        instant = self._serialize(self._normalize_now(delivered_at))
        with self.connection:
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO reminder_deliveries(
                       task_id, reminder_key, delivered_at_utc
                   ) VALUES (?, ?, ?)""",
                (task_id, reminder_key, instant),
            )
        return cursor.rowcount == 1

    def _was_reminded(self, task_id: int, reminder_key: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM reminder_deliveries WHERE task_id = ? AND reminder_key = ?",
            (task_id, reminder_key),
        ).fetchone() is not None

    def _replace_tags(self, task_id: int, tags: tuple[str, ...]) -> None:
        self.connection.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))
        self.connection.executemany(
            "INSERT INTO task_tags(task_id, tag) VALUES (?, ?)",
            ((task_id, tag) for tag in tags),
        )

    @staticmethod
    def _validate_title(title: str) -> str:
        clean = title.strip()
        if not clean:
            raise ValueError("Task title cannot be empty")
        return clean

    @staticmethod
    def _validate_priority(priority: int) -> None:
        if isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 5:
            raise ValueError("Task priority must be an integer from 1 to 5")

    @staticmethod
    def _normalize_project_path(path: str | Path | None) -> str | None:
        if path is None or not str(path).strip():
            return None
        selected = Path(path).expanduser()
        if not selected.is_absolute():
            raise ValueError("Project path must be absolute")
        return str(selected.resolve(strict=False))

    @staticmethod
    def _normalize_tags(tags: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        normalized: dict[str, str] = {}
        for tag in tags:
            clean = tag.strip()
            if clean:
                normalized.setdefault(clean.casefold(), clean)
        return tuple(normalized.values())

    @staticmethod
    def _normalize_deadline(
        deadline: datetime | None,
        timezone_id: str | None,
    ) -> tuple[datetime | None, str | None]:
        if deadline is None:
            if timezone_id is not None:
                raise ValueError("A timezone cannot be set without a deadline")
            return None, None
        if deadline.tzinfo is None or deadline.utcoffset() is None:
            raise ValueError("Deadline must be timezone-aware")
        stored_timezone = (
            timezone_id if timezone_id is not None else getattr(deadline.tzinfo, "key", None)
        )
        if stored_timezone is not None:
            try:
                ZoneInfo(stored_timezone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError(f"Unknown IANA timezone: {stored_timezone!r}") from exc
        return deadline.astimezone(UTC), stored_timezone

    @staticmethod
    def _normalize_now(now: datetime | None) -> datetime:
        instant = datetime.now(UTC) if now is None else now
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("Timestamp must be timezone-aware")
        return instant.astimezone(UTC)

    @staticmethod
    def _serialize(value: datetime | None) -> str | None:
        return value.astimezone(UTC).isoformat(timespec="microseconds") if value is not None else None

    @staticmethod
    def _parse(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value).astimezone(UTC) if value else None

    @classmethod
    def _from_row(cls, row: sqlite3.Row, tags: tuple[str, ...]) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            priority=row["priority"],
            due_at_utc=cls._parse(row["due_at_utc"]),
            timezone_id=row["timezone_id"],
            project_path=row["project_path"],
            completed_at_utc=cls._parse(row["completed_at_utc"]),
            created_at_utc=cls._parse(row["created_at_utc"]),
            updated_at_utc=cls._parse(row["updated_at_utc"]),
            tags=tags,
        )
