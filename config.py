"""Validated application settings and per-user runtime paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


APP_NAME = "MyAssistant"


def _default_data_dir() -> Path:
    override = os.environ.get("MYASSISTANT_DATA_DIR")
    if override:
        configured = Path(override).expanduser()
        if not configured.is_absolute():
            raise ValueError("MYASSISTANT_DATA_DIR must be an absolute path")
        return configured
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / ".local" / "share" / "myassistant"


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Filesystem locations owned by the application."""

    data_dir: Path

    @classmethod
    def from_environment(cls) -> AppPaths:
        return cls(_default_data_dir().resolve())

    @property
    def database(self) -> Path:
        return self.data_dir / "myassistant.sqlite3"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class Settings:
    """Small, safe bootstrap configuration; roots are opt-in."""

    paths: AppPaths
    log_level: str = "INFO"
    index_roots: tuple[Path, ...] = ()
    index_exclusions: tuple[Path, ...] = ()
    timezone_id: str = "UTC"
    start_with_windows: bool = False
    global_hotkey: str = "Ctrl+Alt+M"
    speech_model_dir: Path | None = None

    @classmethod
    def load(cls) -> Settings:
        level = os.environ.get("MYASSISTANT_LOG_LEVEL", "INFO").upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"Unsupported MYASSISTANT_LOG_LEVEL: {level!r}")

        roots_value = os.environ.get("MYASSISTANT_INDEX_ROOTS", "")
        roots_list: list[Path] = []
        for value in roots_value.split(os.pathsep):
            value = value.strip()
            if not value:
                continue
            root = Path(value).expanduser()
            if not root.is_absolute():
                raise ValueError(f"Index roots must be absolute paths: {value!r}")
            roots_list.append(root.resolve())
        exclusion_list: list[Path] = []
        for value in os.environ.get("MYASSISTANT_INDEX_EXCLUSIONS", "").split(os.pathsep):
            value = value.strip()
            if not value:
                continue
            excluded = Path(value).expanduser()
            if not excluded.is_absolute():
                raise ValueError(f"Index exclusions must be absolute paths: {value!r}")
            exclusion_list.append(excluded.resolve())
        timezone_id = os.environ.get("MYASSISTANT_TIMEZONE", "UTC").strip()
        try:
            ZoneInfo(timezone_id)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unsupported MYASSISTANT_TIMEZONE: {timezone_id!r}") from exc
        startup_value = os.environ.get("MYASSISTANT_START_WITH_WINDOWS", "false").strip().casefold()
        if startup_value not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("MYASSISTANT_START_WITH_WINDOWS must be true or false")
        global_hotkey = os.environ.get("MYASSISTANT_GLOBAL_HOTKEY", "Ctrl+Alt+M").strip()
        if not global_hotkey:
            raise ValueError("MYASSISTANT_GLOBAL_HOTKEY cannot be empty")
        configured_model_dir = os.environ.get("MYASSISTANT_SPEECH_MODEL_DIR", "").strip()
        model_dir = Path(configured_model_dir).expanduser() if configured_model_dir else None
        if model_dir is not None and not model_dir.is_absolute():
            raise ValueError("MYASSISTANT_SPEECH_MODEL_DIR must be an absolute path")
        return cls(
            paths=AppPaths.from_environment(),
            log_level=level,
            index_roots=tuple(dict.fromkeys(roots_list)),
            index_exclusions=tuple(dict.fromkeys(exclusion_list)),
            timezone_id=timezone_id,
            start_with_windows=startup_value in {"true", "1", "yes"},
            global_hotkey=global_hotkey,
            speech_model_dir=model_dir.resolve() if model_dir is not None else None,
        )
