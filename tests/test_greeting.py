from datetime import UTC, datetime

from core.database import Database
from todo.service import TaskService
from voice.greeting import build_task_greeting


def test_greeting_summarizes_overdue_and_nearest_upcoming_tasks(tmp_path) -> None:
    database = Database(tmp_path / "greeting.sqlite3")
    connection = database.open()
    service = TaskService(connection)
    now = datetime(2026, 4, 1, 3, 0, tzinfo=UTC)
    service.create_task("Overdue report", due_at=datetime(2026, 4, 1, 2, 0, tzinfo=UTC))
    service.create_task("Prepare demo", due_at=datetime(2026, 4, 1, 6, 15, tzinfo=UTC))
    service.create_task("Review proposal", due_at=datetime(2026, 4, 2, 3, 0, tzinfo=UTC))
    service.create_task("No deadline")
    completed = service.create_task("Finished work", due_at=datetime(2026, 4, 1, 5, 0, tzinfo=UTC))
    service.set_completed(completed.id)

    greeting = build_task_greeting(service.list_tasks("open"), "Asia/Kathmandu", now=now)

    assert greeting.startswith("Good morning, sir. You have 4 open tasks.")
    assert "1 has passed the deadline" in greeting
    assert "Prepare demo, Apr 1 at 12:00 PM" in greeting
    assert "Review proposal" in greeting
    assert "No deadline" not in greeting
    assert "Finished work" not in greeting
    connection.close()


def test_greeting_says_when_there_are_no_open_tasks(tmp_path) -> None:
    database = Database(tmp_path / "empty-greeting.sqlite3")
    connection = database.open()

    greeting = build_task_greeting(
        TaskService(connection).list_tasks("open"),
        "UTC",
        now=datetime(2026, 4, 1, 19, 0, tzinfo=UTC),
    )

    assert greeting == "Good evening, sir. You are all caught up; there are no open tasks."
    connection.close()
