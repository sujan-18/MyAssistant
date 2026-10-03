"""Validate and open an explicitly selected Start Menu shortcut."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


class LaunchError(RuntimeError):
    """A selected application could not be safely opened."""


class ApplicationOpener:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def open_selected(self, launch_target: str) -> None:
        row = self.connection.execute(
            "SELECT launch_target, source FROM applications WHERE launch_target = ?",
            (launch_target,),
        ).fetchone()
        if row is None or row["source"] != "start-menu":
            raise LaunchError("This application is not in the discovered Start Menu catalog")

        shortcut = Path(row["launch_target"])
        if shortcut.suffix.casefold() != ".lnk" or not shortcut.is_file():
            raise LaunchError("The application shortcut no longer exists")
        if os.name != "nt":
            raise LaunchError("Start Menu shortcut launching is available only on Windows")
        try:
            os.startfile(str(shortcut))
        except OSError as exc:
            raise LaunchError(f"Windows could not open {shortcut.name}") from exc

    def open_indexed_path(
        self,
        path: str,
        roots: tuple[Path, ...] | None = None,
        exclusions: tuple[Path, ...] = (),
    ) -> None:
        """Open an explicitly selected indexed file/folder after revalidation."""
        row = self.connection.execute(
            "SELECT path, is_directory FROM indexed_entries WHERE path = ?", (path,)
        ).fetchone()
        if row is None:
            raise LaunchError("This path is not in the filesystem index")
        selected = Path(row["path"])
        selected_key = os.path.normcase(os.path.abspath(selected))
        if roots is not None and not any(
            _is_path_within(selected_key, os.path.normcase(os.path.abspath(root)))
            for root in roots
        ):
            raise LaunchError("This path is outside the configured filesystem roots")
        if any(
            _is_path_within(selected_key, os.path.normcase(os.path.abspath(excluded)))
            for excluded in exclusions
        ):
            raise LaunchError("This path is excluded from filesystem search")
        if selected.is_symlink() or not selected.exists():
            raise LaunchError("This indexed path no longer exists")
        if bool(row["is_directory"]) != selected.is_dir():
            raise LaunchError("This indexed path has changed type")
        if os.name != "nt":
            raise LaunchError("Indexed path launching is available only on Windows")
        try:
            os.startfile(str(selected))
        except OSError as exc:
            raise LaunchError(f"Windows could not open {selected.name}") from exc


def _is_path_within(path: str, parent: str) -> bool:
    try:
        return os.path.commonpath((path, parent)) == parent
    except ValueError:
        return False
