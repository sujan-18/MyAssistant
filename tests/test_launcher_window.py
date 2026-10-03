import os
from datetime import UTC, datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QDate, QEventLoop, QTime, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from core.application import LauncherItem, LauncherSearchResults
from core.database import Database
from ui.index_worker import IndexWorker
from ui.launcher_window import LauncherWindow, create_application
from ui.task_panel import TaskPanel
from todo.service import TaskService
from ui.voice_panel import VoicePanel


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return create_application([])


@pytest.fixture
def services():
    results = (
        LauncherItem("Visual Studio Code", r"C:\Users\user\VSCode.lnk", "APPLICATION", 100),
        LauncherItem("Visual Studio Code Insiders", r"C:\Users\user\CodeInsiders.lnk", "APPLICATION", 90),
        LauncherItem("Code notes.txt", r"C:\Users\user\Code notes.txt", "FILE", 70),
    )
    opened: list[LauncherItem] = []

    def search(query: str) -> LauncherSearchResults:
        matches = tuple(result for result in results if query.casefold() in result.name.casefold())
        ambiguous = len(matches) > 1 and matches[0].score == matches[1].score
        return LauncherSearchResults(query, matches, ambiguous)

    return search, opened.append, opened


@pytest.fixture
def window(qt_app: QApplication, services):
    launcher = LauncherWindow(services[0], services[1])
    launcher.show_and_focus()
    qt_app.processEvents()
    yield launcher
    launcher.hide()
    launcher.deleteLater()
    qt_app.processEvents()


def test_window_shows_search_results_and_filters_text(window: LauncherWindow) -> None:
    assert window.isVisible()
    assert window.search_input.hasFocus()
    # The default mode is applications; file matches are shown in the separate
    # Files & Folders scope.
    assert window.results.count() == 2

    QTest.keyClicks(window.search_input, "insiders")
    assert window.results.count() == 1
    assert "Visual Studio Code Insiders" in window.results.item(0).text()


def test_equal_rank_matches_explain_ambiguity(qt_app: QApplication) -> None:
    search = lambda query: LauncherSearchResults(  # noqa: E731
        query,
        (LauncherItem("Editor", "a.lnk", "APPLICATION", 80),
         LauncherItem("Editor", "b.lnk", "APPLICATION", 80)),
        True,
    )
    window = LauncherWindow(search, lambda _result: None)
    window.search_input.setText("editor")
    qt_app.processEvents()
    assert window.results.count() == 2
    assert "Choose the intended result" in window.match_notice.text()
    window.deleteLater()
    qt_app.processEvents()


def test_enter_opens_only_selected_result_and_hides(window: LauncherWindow, services) -> None:
    selected: list[LauncherItem] = []
    window.result_activated.connect(selected.append)
    QTest.keyClicks(window.search_input, "visual")
    QTest.keyClick(window.search_input, Qt.Key.Key_Down)
    QTest.keyClick(window.search_input, Qt.Key.Key_Return)

    assert services[2] == [services[0]("visual").matches[1]]
    assert selected == services[2]
    assert not window.isVisible()


def test_launch_error_keeps_window_open_and_reports_failure(qt_app: QApplication) -> None:
    def fail(_result: LauncherItem) -> None:
        raise OSError("shortcut is missing")

    window = LauncherWindow(
        lambda query: LauncherSearchResults(
            query, (LauncherItem("Editor", "missing.lnk", "APPLICATION", 100),), False
        ),
        fail,
    )
    window.show()
    window.search_input.setText("editor")
    QTest.keyClick(window.search_input, Qt.Key.Key_Return)
    assert window.isVisible()
    assert "shortcut is missing" in window.statusBar().currentMessage()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def test_escape_hides_and_window_can_be_reopened_with_focus(window: LauncherWindow, qt_app: QApplication) -> None:
    QTest.keyClick(window.search_input, Qt.Key.Key_Escape)
    qt_app.processEvents()
    assert not window.isVisible()

    window.show_and_focus()
    qt_app.processEvents()
    assert window.isVisible()


def test_close_button_hides_and_quit_action_requests_application_exit(
    window: LauncherWindow, qt_app: QApplication
) -> None:
    exit_requests: list[bool] = []
    window.exit_requested.connect(lambda: exit_requests.append(True))
    window.set_tray_available(True)

    window.close()
    qt_app.processEvents()
    assert not window.isVisible()
    assert exit_requests == []

    window.show_and_focus()
    QTest.keyClick(window.search_input, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier)
    assert exit_requests == [True]


def test_close_without_tray_requests_application_exit(window: LauncherWindow) -> None:
    exit_requests: list[bool] = []
    window.exit_requested.connect(lambda: exit_requests.append(True))
    window.close()
    assert not window.isVisible()
    assert exit_requests == [True]


def test_voice_panel_is_available_as_explicit_launcher_tab(qt_app, tmp_path) -> None:
    panel = VoicePanel(tmp_path / "missing-model")
    launcher = LauncherWindow(
        lambda query: LauncherSearchResults(query, (), False),
        lambda _result: None,
        voice_panel=panel,
    )
    assert launcher.pages.count() == 4
    assert launcher.pages.widget(launcher._page_indices["voice"]) is panel
    assert "Microphone is off" in panel.status_label.text()
    assert panel.record_button.text() == "Record"
    launcher.deleteLater()
    qt_app.processEvents()


def test_index_worker_runs_off_ui_connection_and_reports_completion(
    qt_app: QApplication, tmp_path
) -> None:
    root = tmp_path / "indexed"
    root.mkdir()
    (root / "worker document.txt").touch()
    database = Database(tmp_path / "worker.sqlite3")
    connection = database.open()
    worker = IndexWorker(database.path, (root,), ())
    loop = QEventLoop()
    reports = []
    errors = []
    worker.completed.connect(lambda report: (reports.append(report), loop.quit()))
    worker.failed.connect(lambda error: (errors.append(error), loop.quit()))
    QTimer.singleShot(5000, loop.quit)

    worker.start()
    loop.exec()
    assert worker.wait(1000)
    assert errors == []
    assert reports and reports[0].complete
    assert connection.execute(
        "SELECT 1 FROM indexed_entries WHERE name = 'worker document.txt'"
    ).fetchone() is not None
    database.close()


def test_task_panel_creates_edits_completes_and_reopens_tasks(
    qt_app: QApplication, tmp_path
) -> None:
    database = Database(tmp_path / "task-panel.sqlite3")
    connection = database.open()
    service = TaskService(connection)
    panel = TaskPanel(service, "UTC")
    launcher = LauncherWindow(
        lambda query: LauncherSearchResults(query, (), False),
        lambda _result: None,
        panel,
    )
    assert launcher.pages.widget(launcher._page_indices["tasks"]) is panel
    panel.title_input.setText("Prepare release")
    panel.deadline_enabled.setChecked(True)
    panel.deadline_date.setDate(QDate(2026, 12, 1))
    panel.deadline_time.setTime(QTime(15, 30))
    panel.tags_input.setText("release, project")
    QTest.mouseClick(panel.save_button, Qt.MouseButton.LeftButton)
    assert panel.task_list.count() == 1
    task = service.list_tasks()[0]
    assert task.title == "Prepare release"
    assert task.tags == ("project", "release")
    assert task.due_at_utc == datetime(2026, 12, 1, 15, 30, tzinfo=UTC)

    panel.title_input.setText("Prepare v1 release")
    QTest.mouseClick(panel.save_button, Qt.MouseButton.LeftButton)
    assert service.get_task(task.id).title == "Prepare v1 release"

    QTest.mouseClick(panel.complete_button, Qt.MouseButton.LeftButton)
    assert service.get_task(task.id).is_completed
    panel.status_filter.setCurrentIndex(1)
    qt_app.processEvents()
    panel.task_list.setCurrentRow(0)
    QTest.mouseClick(panel.complete_button, Qt.MouseButton.LeftButton)
    assert not service.get_task(task.id).is_completed
    panel._countdown_timer.stop()
    launcher.deleteLater()
    panel.deleteLater()
    qt_app.processEvents()
    database.close()
