from __future__ import annotations

from pathlib import Path

import pytest

from system.windows import parse_hotkey, set_startup_enabled


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
