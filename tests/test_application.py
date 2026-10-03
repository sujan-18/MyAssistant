from pathlib import Path

import pytest

from config import AppPaths, Settings
from core import application as application_module
from core.application import Application
from launcher.discovery import DiscoveryReport


def test_application_starts_initializes_database_and_closes_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        application_module,
        "discover_shortcuts",
        lambda: DiscoveryReport((), complete=False, errors=1),
    )
    settings = Settings(paths=AppPaths(tmp_path / "profile"))
    application = Application(settings)

    application.start()
    database_path = settings.paths.database
    assert database_path.is_file()
    assert settings.paths.log_dir.is_dir()
    assert application.database is not None
    assert application.database.connection is not None

    with pytest.raises(RuntimeError, match="already started"):
        application.start()

    application.close()
    application.close()
    assert application.database is None
    assert application.logger is None


def test_application_services_require_startup(tmp_path: Path) -> None:
    application = Application(Settings(paths=AppPaths(tmp_path / "profile")))

    with pytest.raises(RuntimeError, match="started"):
        application.search_applications("browser")
    with pytest.raises(RuntimeError, match="started"):
        application.open_application("shortcut.lnk")


def test_application_indexes_and_searches_files_through_launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        application_module,
        "discover_shortcuts",
        lambda: DiscoveryReport((), complete=False, errors=1),
    )
    root = tmp_path / "documents"
    root.mkdir()
    note = root / "meeting notes.txt"
    note.write_text("private file contents are never indexed", encoding="utf-8")
    settings = Settings(paths=AppPaths(tmp_path / "profile"), index_roots=(root,))
    application = Application(settings)
    application.start()
    try:
        report = application.index_filesystem()
        assert report.complete

        results = application.search_launcher("meeting notes")
        assert len(results.matches) == 1
        item = results.matches[0]
        assert item.name == note.name
        assert item.kind == "FILE"
        assert application.search_launcher("private").matches == ()

        opened: list[str] = []
        monkeypatch.setattr("launcher.opening.os.startfile", opened.append)
        application.open_search_result(item)
        assert opened == [str(note)]
    finally:
        application.close()
