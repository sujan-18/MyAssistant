import os
from pathlib import Path

import pytest

from config import AppPaths, Settings


def test_settings_use_local_app_data_and_safe_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MYASSISTANT_DATA_DIR", raising=False)
    monkeypatch.delenv("MYASSISTANT_INDEX_ROOTS", raising=False)
    monkeypatch.delenv("MYASSISTANT_INDEX_EXCLUSIONS", raising=False)
    monkeypatch.delenv("MYASSISTANT_TIMEZONE", raising=False)
    monkeypatch.delenv("MYASSISTANT_LOG_LEVEL", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    settings = Settings.load()

    assert settings.paths.data_dir == (tmp_path / "MyAssistant").resolve()
    assert settings.log_level == "INFO"
    assert settings.index_roots == ()


def test_settings_parse_absolute_index_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    monkeypatch.setenv("MYASSISTANT_INDEX_ROOTS", os.pathsep.join((str(first), str(second))))

    assert Settings.load().index_roots == (first.resolve(), second.resolve())


def test_settings_parse_absolute_exclusions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    excluded = tmp_path / "private"
    monkeypatch.setenv("MYASSISTANT_INDEX_EXCLUSIONS", str(excluded))

    assert Settings.load().index_exclusions == (excluded.resolve(),)


def test_settings_reject_relative_exclusion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYASSISTANT_INDEX_EXCLUSIONS", "relative-folder")

    with pytest.raises(ValueError, match="exclusions must be absolute"):
        Settings.load()


def test_settings_validate_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYASSISTANT_TIMEZONE", "Asia/Kathmandu")
    assert Settings.load().timezone_id == "Asia/Kathmandu"
    monkeypatch.setenv("MYASSISTANT_TIMEZONE", "Not/AZone")
    with pytest.raises(ValueError, match="MYASSISTANT_TIMEZONE"):
        Settings.load()


def test_settings_reject_relative_index_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYASSISTANT_INDEX_ROOTS", "relative-folder")

    with pytest.raises(ValueError, match="absolute paths"):
        Settings.load()


def test_settings_reject_relative_data_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYASSISTANT_DATA_DIR", "relative-data")

    with pytest.raises(ValueError, match="MYASSISTANT_DATA_DIR"):
        AppPaths.from_environment()


def test_settings_reject_invalid_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYASSISTANT_LOG_LEVEL", "VERBOSE")

    with pytest.raises(ValueError, match="MYASSISTANT_LOG_LEVEL"):
        Settings.load()
