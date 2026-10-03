from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from core.database import Database
from todo.service import TaskService, resolve_local_deadline


@pytest.fixture
def task_database(tmp_path: Path):
    database = Database(tmp_path / "tasks.sqlite3")
    connection = database.open()
    yield database, TaskService(connection)
    database.close()


def test_task_crud_tags_filters_and_project_path(task_database, tmp_path: Path) -> None:
    _database, tasks = task_database
    project = tmp_path / "my-project"
    created = tasks.create_task(
        "  Finish report  ",
        description="Draft and review",
        priority=2,
        project_path=project,
        tags=(" Work ", "work", "Urgent"),
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert created.title == "Finish report"
    assert created.tags == ("Urgent", "Work")
    assert created.project_path == str(project.resolve())
    assert tasks.list_tasks(query="review") == (created,)
    assert tasks.list_tasks(query="urgent") == (created,)

    updated = tasks.update_task(
        created.id,
        title="Submit report",
        priority=1,
        tags=("work", "done"),
        now=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert updated.title == "Submit report"
    assert updated.priority == 1
    assert updated.tags == ("done", "work")
    assert updated.project_path == str(project.resolve())

    completed = tasks.set_completed(updated.id, now=datetime(2026, 1, 3, tzinfo=UTC))
    assert completed.is_completed
    assert tasks.list_tasks("open") == ()
    assert tasks.list_tasks("completed") == (completed,)
    reopened = tasks.set_completed(updated.id, False, now=datetime(2026, 1, 4, tzinfo=UTC))
    assert not reopened.is_completed
    assert tasks.delete_task(updated.id)
    assert not tasks.delete_task(updated.id)


def test_task_validation_rejects_bad_title_priority_deadline_and_path(task_database) -> None:
    _database, tasks = task_database
    with pytest.raises(ValueError, match="title cannot be empty"):
        tasks.create_task(" \t ")
    with pytest.raises(ValueError, match="priority"):
        tasks.create_task("Bad priority", priority=3.5)
    with pytest.raises(ValueError, match="timezone-aware"):
        tasks.create_task("Naive deadline", due_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="absolute"):
        tasks.create_task("Relative project", project_path="relative/path")
    with pytest.raises(ValueError, match="timezone cannot be set"):
        tasks.create_task("Timezone only", timezone_id="UTC")


def test_local_deadline_handles_dst_gap_and_ambiguous_fold() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        resolve_local_deadline(datetime(2026, 3, 8, 2, 30), "America/New_York")
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_local_deadline(datetime(2026, 11, 1, 1, 30), "America/New_York")

    first = resolve_local_deadline(datetime(2026, 11, 1, 1, 30), "America/New_York", fold=0)
    second = resolve_local_deadline(datetime(2026, 11, 1, 1, 30), "America/New_York", fold=1)
    assert first.astimezone(UTC) + timedelta(hours=1) == second.astimezone(UTC)


def test_task_deadline_round_trips_and_countdown_states(task_database) -> None:
    _database, tasks = task_database
    deadline = datetime(2026, 1, 1, 18, 45, tzinfo=ZoneInfo("Asia/Kathmandu"))
    task = tasks.create_task("Deadline", due_at=deadline, timezone_id="Asia/Kathmandu")

    restored = tasks.get_task(task.id)
    assert restored.due_at_utc == deadline.astimezone(UTC)
    assert restored.timezone_id == "Asia/Kathmandu"
    assert tasks.countdown(restored, datetime(2026, 1, 1, 10, tzinfo=UTC)) == "Due in 3h"
    assert tasks.countdown(restored, datetime(2026, 1, 1, 16, tzinfo=UTC)) == "Deadline passed"
    assert tasks.countdown(tasks.create_task("No due date")) == "No deadline"
    assert tasks.countdown(tasks.set_completed(task.id)) == "Completed"


def test_reminder_windows_deduplicate_across_database_restart(task_database, tmp_path: Path) -> None:
    database, tasks = task_database
    due = datetime(2026, 1, 2, 12, tzinfo=UTC)
    task = tasks.create_task("Remind me", due_at=due)
    one_hour_before = datetime(2026, 1, 2, 11, 15, tzinfo=UTC)
    notices = tasks.pending_reminders(one_hour_before)
    assert len(notices) == 1
    assert "before:3600" in notices[0].reminder_key
    assert tasks.record_reminder(task.id, notices[0].reminder_key, one_hour_before)
    assert not tasks.record_reminder(task.id, notices[0].reminder_key, one_hour_before)

    database.close()
    connection = database.open()
    restarted = TaskService(connection)
    assert restarted.pending_reminders(one_hour_before) == ()
    quarter_hour_before = datetime(2026, 1, 2, 11, 50, tzinfo=UTC)
    assert "before:900" in restarted.pending_reminders(quarter_hour_before)[0].reminder_key
    overdue = datetime(2026, 1, 2, 12, 1, tzinfo=UTC)
    assert "overdue" in restarted.pending_reminders(overdue)[0].reminder_key


def test_deadline_update_creates_new_reminder_cycle(task_database) -> None:
    _database, tasks = task_database
    first_due = datetime(2026, 1, 2, 12, tzinfo=UTC)
    task = tasks.create_task("Move deadline", due_at=first_due)
    notice = tasks.pending_reminders(datetime(2026, 1, 2, 11, 15, tzinfo=UTC))[0]
    tasks.record_reminder(task.id, notice.reminder_key)

    new_due = datetime(2026, 1, 3, 12, tzinfo=UTC)
    tasks.update_task(task.id, title=task.title, due_at=new_due)
    new_notice = tasks.pending_reminders(datetime(2026, 1, 3, 11, 15, tzinfo=UTC))
    assert len(new_notice) == 1
    assert new_notice[0].reminder_key != notice.reminder_key
