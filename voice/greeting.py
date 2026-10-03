"""Build a concise spoken summary of the user's open tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from todo.service import Task


def build_task_greeting(
    tasks: tuple[Task, ...],
    timezone_id: str,
    *,
    now: datetime | None = None,
    deadline_limit: int = 3,
) -> str:
    """Summarize open tasks and the nearest deadlines without exposing descriptions."""
    timezone = ZoneInfo(timezone_id)
    instant = datetime.now(UTC) if now is None else now
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Greeting time must be timezone-aware")
    local_now = instant.astimezone(timezone)
    hour = local_now.hour
    salutation = (
        "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    )
    open_tasks = tuple(task for task in tasks if not task.is_completed)
    if not open_tasks:
        return f"{salutation}, sir. You are all caught up; there are no open tasks."

    overdue = tuple(
        task for task in open_tasks
        if task.due_at_utc is not None and task.due_at_utc <= instant.astimezone(UTC)
    )
    task_count = len(open_tasks)
    summary = f"{salutation}, sir. You have {task_count} open task{'s' if task_count != 1 else ''}."
    if overdue:
        summary += f" {len(overdue)} {'has' if len(overdue) == 1 else 'have'} passed the deadline."

    upcoming = sorted(
        (
            task
            for task in open_tasks
            if task.due_at_utc is not None and task.due_at_utc > instant.astimezone(UTC)
        ),
        key=lambda task: task.due_at_utc,
    )[:max(0, deadline_limit)]
    if upcoming:
        summary += " Upcoming deadlines: "
        details = []
        for task in upcoming:
            deadline = task.due_at_utc.astimezone(timezone)
            date_text = deadline.strftime("%b %d").replace(" 0", " ")
            time_text = deadline.strftime("%I:%M %p").lstrip("0")
            details.append(f"{task.title}, {date_text} at {time_text}")
        summary += "; ".join(details) + "."
    return summary
