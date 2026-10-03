import threading
from pathlib import Path

import pytest

from core.database import Database
from search.filesystem import index_roots, search_files


@pytest.fixture
def indexed_database(tmp_path: Path):
    database = Database(tmp_path / "assistant.sqlite3")
    connection = database.open()
    yield connection
    database.close()


def test_index_walks_configured_tree_and_searches_names_and_paths(indexed_database, tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    project = root / "Python Project"
    project.mkdir(parents=True)
    (project / "readme.md").write_text("content is deliberately not indexed", encoding="utf-8")
    (project / "budget 2026.xlsx").touch()
    (root / ".private.txt").touch()

    report = index_roots(indexed_database, (root,))

    assert report.complete
    assert report.roots_completed == 1
    assert report.entries_indexed == 4  # root, subfolder and two files; hidden file skipped
    results = search_files(indexed_database, "python proj")
    assert results.matches[0].name == "Python Project"
    assert results.matches[0].is_directory
    assert search_files(indexed_database, "readme").matches[0].name == "readme.md"
    assert search_files(indexed_database, "deliberately indexed").matches == ()
    assert search_files(indexed_database, "private").matches == ()


def test_excluded_subtrees_are_not_indexed(indexed_database, tmp_path: Path) -> None:
    root = tmp_path / "root"
    excluded = root / "ignored"
    excluded.mkdir(parents=True)
    (excluded / "secret.txt").touch()
    (root / "visible.txt").touch()

    report = index_roots(indexed_database, (root,), (excluded,))

    assert report.complete
    assert search_files(indexed_database, "secret").matches == ()
    assert search_files(indexed_database, "ignored").matches == ()
    assert search_files(indexed_database, "visible").matches[0].name == "visible.txt"


def test_symlinks_are_not_followed(indexed_database, tmp_path: Path) -> None:
    root = tmp_path / "root"
    excluded = root / "ignored"
    excluded.mkdir(parents=True)
    (excluded / "secret.txt").touch()
    link = root / "alias"
    try:
        link.symlink_to(excluded, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not permitted")

    report = index_roots(indexed_database, (root,))

    assert report.complete
    assert search_files(indexed_database, "alias").matches == ()


def test_successful_rescan_removes_deleted_entries(indexed_database, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    removed = root / "removed.txt"
    removed.touch()
    index_roots(indexed_database, (root,))
    removed.unlink()
    (root / "new.txt").touch()

    report = index_roots(indexed_database, (root,))

    assert report.complete
    assert search_files(indexed_database, "removed").matches == ()
    assert search_files(indexed_database, "new").matches[0].name == "new.txt"


def test_incomplete_or_cancelled_scan_preserves_existing_entries(indexed_database, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    old_file = root / "old.txt"
    old_file.touch()
    index_roots(indexed_database, (root,))
    old_file.unlink()

    root.rmdir()
    failed = index_roots(indexed_database, (root,))
    assert not failed.complete
    assert search_files(indexed_database, "old").matches


def test_cancelled_scan_never_prunes_previous_index(indexed_database, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    old_file = root / "old.txt"
    old_file.touch()
    index_roots(indexed_database, (root,))
    old_file.unlink()
    event = threading.Event()
    event.set()

    report = index_roots(indexed_database, (root,), cancel_event=event)

    assert report.cancelled
    assert search_files(indexed_database, "old").matches


def test_duplicate_names_are_reported_as_ambiguous(indexed_database, tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "first").mkdir(parents=True)
    (root / "second").mkdir()
    (root / "first" / "notes.txt").touch()
    (root / "second" / "notes.txt").touch()
    index_roots(indexed_database, (root,))

    results = search_files(indexed_database, "notes")

    assert len(results.matches) == 2
    assert results.ambiguous


def test_search_scope_obeys_configured_roots_and_exclusions(indexed_database, tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "shared.txt").touch()
    (second / "shared.txt").touch()
    index_roots(indexed_database, (first, second))

    scoped = search_files(indexed_database, "shared", roots=(first,))
    assert len(scoped.matches) == 1
    assert Path(scoped.matches[0].path).parent == first
    assert search_files(indexed_database, "shared", roots=()).matches == ()
    assert search_files(indexed_database, "shared", roots=(first, second), exclusions=(first,)).matches[0].path == str(second / "shared.txt")
