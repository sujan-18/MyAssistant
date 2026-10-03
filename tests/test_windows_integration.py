from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

import pytest

from system.windows import parse_hotkey, set_startup_enabled
from ui import windows_integration


@pytest.mark.parametrize(
    ("hotkey", "expected"),
    [
        ("Ctrl+Space", (0x4002, 0x20)),
        ("Alt+Shift+F12", (0x4005, 0x7B)),
        ("Win+K", (0x4008, ord("K"))),
    ],
)
def test_parse_hotkey(hotkey: str, expected: tuple[int, int]) -> None:
    assert parse_hotkey(hotkey) == expected


@pytest.mark.parametrize("hotkey", ["Space", "Ctrl", "Ctrl+Bogus", "Hyper+A"])
def test_parse_hotkey_rejects_invalid_chords(hotkey: str) -> None:
    with pytest.raises(ValueError):
        parse_hotkey(hotkey)


def test_hotkey_filter_calls_callback_for_wm_hotkey(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(windows_integration.os, "name", "posix")
    activated: list[bool] = []
    hotkey_filter = windows_integration.HotkeyFilter("Ctrl+Space", lambda: activated.append(True))
    hotkey_filter._registered = True

    message = wintypes.MSG()
    message.message = hotkey_filter._WM_HOTKEY
    message.wParam = hotkey_filter._HOTKEY_ID

    handled, result = hotkey_filter.nativeEventFilter(None, ctypes.addressof(message))

    assert (handled, result) == (True, 0)
    assert activated == [True]


def test_startup_entry_is_opt_in_and_removable(tmp_path: Path) -> None:
    entry = tmp_path / "Startup" / "MyAssistant.vbs"
    set_startup_enabled(True, script_path=entry)
    content = entry.read_text(encoding="utf-8")
    assert "WScript.Shell" in content
    assert "main.py" in content
    set_startup_enabled(False, script_path=entry)
    assert not entry.exists()


def test_startup_disabled_does_not_create_files(tmp_path: Path) -> None:
    entry = tmp_path / "Startup" / "MyAssistant.vbs"
    set_startup_enabled(False, script_path=entry)
    assert not entry.parent.exists()


def test_packaged_startup_entry_runs_the_frozen_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entry = tmp_path / "Startup" / "MyAssistant.vbs"
    executable = tmp_path / "release" / "MyAssistant.exe"
    monkeypatch.setattr("system.windows.sys.frozen", True, raising=False)
    monkeypatch.setattr("system.windows.sys.executable", str(executable))

    set_startup_enabled(True, script_path=entry)

    content = entry.read_text(encoding="utf-8")
    assert str(executable) in content
    assert "main.py" not in content
