"""Small, opt-in Windows integrations using the operating system APIs."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def startup_script_path() -> Path:
    """Return this user's Startup-folder script path without creating it."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise OSError("APPDATA is unavailable; cannot locate the Startup folder")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "MyAssistant.vbs"


def set_startup_enabled(enabled: bool, *, script_path: Path | None = None) -> None:
    """Add/remove a hidden per-user startup script; disabled by default."""
    target = script_path or startup_script_path()
    if not enabled:
        target.unlink(missing_ok=True)
        return

    executable = Path(sys.executable)
    if executable.name.casefold() == "python.exe":
        executable = executable.with_name("pythonw.exe")
    entry = Path(__file__).resolve().parents[1] / "main.py"
    escaped_exe = str(executable).replace('"', '""')
    escaped_entry = str(entry).replace('"', '""')
    content = (
        'Set shell = CreateObject("WScript.Shell")\r\n'
        f'shell.Run """{escaped_exe}"" ""{escaped_entry}""", 0, False\r\n'
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def parse_hotkey(value: str) -> tuple[int, int]:
    """Translate a conservative Ctrl/Alt/Shift/Win + key chord to Win32."""
    names = {"CTRL": 0x0002, "CONTROL": 0x0002, "ALT": 0x0001,
             "SHIFT": 0x0004, "WIN": 0x0008, "META": 0x0008}
    parts = [part.strip().upper() for part in value.split("+") if part.strip()]
    if len(parts) < 2 or parts[-1] in names:
        raise ValueError("Hotkey must include a modifier and a key, for example Ctrl+Space")
    modifiers = 0x4000  # MOD_NOREPEAT
    for modifier in parts[:-1]:
        if modifier not in names:
            raise ValueError(f"Unsupported hotkey modifier: {modifier}")
        modifiers |= names[modifier]
    key_name = parts[-1]
    virtual_keys = {"SPACE": 0x20, "ESC": 0x1B, "ESCAPE": 0x1B,
                    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
                    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
                    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B}
    if len(key_name) == 1 and key_name.isascii() and key_name.isalnum():
        key_code = ord(key_name)
    else:
        try:
            key_code = virtual_keys[key_name]
        except KeyError as exc:
            raise ValueError(f"Unsupported hotkey key: {key_name}") from exc
    return modifiers, key_code
