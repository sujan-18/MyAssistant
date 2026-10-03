"""Discover application shortcuts from the current user's Start Menu."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


MAX_DEPTH = 12
MAX_SHORTCUTS = 20_000


@dataclass(frozen=True, slots=True)
class AppShortcut:
    name: str
    shortcut_path: Path


@dataclass(frozen=True, slots=True)
class DiscoveryReport:
    shortcuts: tuple[AppShortcut, ...]
    complete: bool
    errors: int


def start_menu_roots(environ: dict[str, str] | None = None) -> tuple[Path, ...]:
    """Return standard per-user and all-users Programs folders if configured."""
    env = os.environ if environ is None else environ
    candidates = []
    if env.get("APPDATA"):
        candidates.append(Path(env["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if env.get("PROGRAMDATA"):
        candidates.append(Path(env["PROGRAMDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    seen: set[str] = set()
    result = []
    for candidate in candidates:
        key = os.path.normcase(os.path.abspath(candidate))
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return tuple(result)


def discover_shortcuts(roots: tuple[Path, ...] | None = None) -> DiscoveryReport:
    """Walk Start Menu roots without following directory symlinks.

    A report is complete only when every configured root was traversed. Catalog
    callers can then avoid deleting stale records after a partial or failed scan.
    """
    selected_roots = start_menu_roots() if roots is None else roots
    found: dict[str, AppShortcut] = {}
    errors = 1 if not selected_roots else 0

    for root in selected_roots:
        try:
            root_exists = root.is_dir()
        except OSError:
            root_exists = False
        if not root_exists:
            errors += 1
            continue
        pending: list[tuple[Path, int]] = [(root, 0)]
        while pending:
            directory, depth = pending.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if depth < MAX_DEPTH:
                                    pending.append((Path(entry.path), depth + 1))
                                else:
                                    errors += 1
                                continue
                            if not entry.is_file(follow_symlinks=False) or Path(entry.name).suffix.casefold() != ".lnk":
                                continue
                            shortcut_path = Path(entry.path)
                            normalized = os.path.normcase(os.path.abspath(shortcut_path))
                            found.setdefault(normalized, AppShortcut(shortcut_path.stem, shortcut_path))
                            if len(found) >= MAX_SHORTCUTS:
                                return DiscoveryReport(tuple(found.values()), False, errors + 1)
                        except OSError:
                            errors += 1
            except OSError:
                errors += 1

    return DiscoveryReport(tuple(found.values()), errors == 0, errors)
