from pathlib import Path

import pytest

from core.database import Database
from launcher.catalog import ApplicationCatalog
from launcher.discovery import AppShortcut, DiscoveryReport
from launcher.opening import ApplicationOpener, LaunchError


@pytest.fixture
def app_database(tmp_path: Path):
    database = Database(tmp_path / "apps.sqlite3")
    connection = database.open()
    yield connection
    database.close()


def report(*paths: Path, complete: bool = True) -> DiscoveryReport:
    return DiscoveryReport(
        tuple(AppShortcut(path.stem, path) for path in paths),
        complete,
        0 if complete else 1,
    )


def test_catalog_ranks_exact_prefix_and_token_matches_and_marks_ties(app_database) -> None:
    catalog = ApplicationCatalog(app_database)
    catalog.refresh(report(Path("C:/Apps/Code.lnk"), Path("C:/Apps/Code - Insiders.lnk")))

    exact = catalog.search("code")
    assert exact.matches[0].name == "Code"
    assert exact.matches[0].score == 100
    assert not exact.ambiguous
    assert catalog.search("insiders").matches[0].name == "Code - Insiders"
    assert catalog.search(" ").matches == ()
    assert catalog.search("code", limit=0).matches == ()


def test_catalog_prunes_stale_rows_only_after_complete_discovery(app_database) -> None:
    catalog = ApplicationCatalog(app_database)
    first = Path("C:/Apps/First.lnk")
    second = Path("C:/Apps/Second.lnk")
    catalog.refresh(report(first, second))

    catalog.refresh(report(first, complete=False))
    assert len(catalog.search("second").matches) == 1

    catalog.refresh(report(first, complete=True))
    assert catalog.search("second").matches == ()


def test_catalog_reports_equal_best_scores_as_ambiguous(app_database) -> None:
    catalog = ApplicationCatalog(app_database)
    catalog.refresh(report(Path("C:/Apps/Editor.lnk"), Path("C:/Apps/Editor.lnk")))
    # Same target is de-duplicated by SQLite, so use two distinct targets with equal names.
    app_database.execute(
        """INSERT INTO applications(name, launch_target, source, discovered_at_utc)
           VALUES ('Editor', 'C:/Apps/Editor Copy.lnk', 'start-menu', 'now')"""
    )

    results = catalog.search("editor")
    assert len(results.matches) == 2
    assert results.ambiguous


def test_opener_revalidates_catalog_membership_and_shortcut_file(app_database, tmp_path, monkeypatch) -> None:
    shortcut = tmp_path / "Editor.lnk"
    shortcut.touch()
    catalog = ApplicationCatalog(app_database)
    catalog.refresh(report(shortcut))
    opened: list[str] = []
    monkeypatch.setattr("launcher.opening.os.startfile", opened.append)

    ApplicationOpener(app_database).open_selected(str(shortcut))
    assert opened == [str(shortcut)]

    with pytest.raises(LaunchError, match="not in the discovered"):
        ApplicationOpener(app_database).open_selected(str(tmp_path / "unknown.lnk"))

    shortcut.unlink()
    with pytest.raises(LaunchError, match="no longer exists"):
        ApplicationOpener(app_database).open_selected(str(shortcut))


def test_opener_wraps_windows_shell_errors(app_database, tmp_path, monkeypatch) -> None:
    shortcut = tmp_path / "Broken.lnk"
    shortcut.touch()
    ApplicationCatalog(app_database).refresh(report(shortcut))

    def fail(_target: str) -> None:
        raise OSError("shell unavailable")

    monkeypatch.setattr("launcher.opening.os.startfile", fail)
    with pytest.raises(LaunchError, match="could not open Broken.lnk"):
        ApplicationOpener(app_database).open_selected(str(shortcut))


def test_opener_revalidates_indexed_file_before_opening(app_database, tmp_path, monkeypatch) -> None:
    from search.filesystem import index_roots

    root = tmp_path / "documents"
    root.mkdir()
    document = root / "notes.txt"
    document.write_text("local metadata only", encoding="utf-8")
    index_roots(app_database, (root,))
    opened: list[str] = []
    monkeypatch.setattr("launcher.opening.os.startfile", opened.append)

    ApplicationOpener(app_database).open_indexed_path(str(document))
    assert opened == [str(document)]

    with pytest.raises(LaunchError, match="not in the filesystem index"):
        ApplicationOpener(app_database).open_indexed_path(str(tmp_path / "outside.txt"))

    document.unlink()
    with pytest.raises(LaunchError, match="no longer exists"):
        ApplicationOpener(app_database).open_indexed_path(str(document))
