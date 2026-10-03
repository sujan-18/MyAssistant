"""Qt shell controls for the Windows hotkey, tray and task reminders."""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from ctypes import wintypes
from datetime import UTC, datetime

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from system.windows import parse_hotkey
from todo.service import TaskService


class HotkeyFilter(QAbstractNativeEventFilter):
    """Register one system-wide chord and receive its WM_HOTKEY message."""

    _HOTKEY_ID = 0x4D41
    _WM_HOTKEY = 0x0312

    def __init__(self, hotkey: str, on_activated: Callable[[], None]) -> None:
        super().__init__()
        self._on_activated = on_activated
        self._user32 = None
        self._registered = False
        if os.name != "nt":
            self.error = "Global hotkeys are available only on Windows."
            return
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        self._user32.RegisterHotKey.restype = wintypes.BOOL
        self._user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self._user32.UnregisterHotKey.restype = wintypes.BOOL
        modifiers, key = parse_hotkey(hotkey)
        self._registered = bool(self._user32.RegisterHotKey(None, self._HOTKEY_ID, modifiers, key))
        self.error = "" if self._registered else f"Hotkey {hotkey} is unavailable (it may be in use)."

    def nativeEventFilter(self, event_type, message):  # noqa: N802 - Qt override
        if not self._registered or not message:
            return False, 0
        native_message = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
        if native_message.message == self._WM_HOTKEY and native_message.wParam == self._HOTKEY_ID:
            self._on_activated()
            return True, 0
        return False, 0

    def close(self) -> None:
        if self._registered and self._user32 is not None:
            self._user32.UnregisterHotKey(None, self._HOTKEY_ID)
            self._registered = False


class WindowsIntegration(QObject):
    """Own tray lifecycle, hotkey registration and reminder delivery."""

    show_launcher = Signal()
    toggle_launcher = Signal()
    quit_requested = Signal()

    def __init__(self, app: QApplication, task_service: TaskService, hotkey: str = "Ctrl+Alt+M") -> None:
        super().__init__(app)
        self.app = app
        self.task_service = task_service
        self.tray = QSystemTrayIcon(app)
        self.tray.setIcon(self._assistant_icon())
        self.tray.setToolTip("MyAssistant")
        self.menu = QMenu()
        open_action = QAction("Open MyAssistant", self.menu)
        open_action.triggered.connect(self.show_launcher)
        tasks_action = QAction("Check reminders now", self.menu)
        tasks_action.triggered.connect(self.deliver_reminders)
        exit_action = QAction("Exit MyAssistant", self.menu)
        exit_action.triggered.connect(self.quit_requested)
        self.menu.addAction(open_action)
        self.menu.addAction(tasks_action)
        self.menu.addSeparator()
        self.menu.addAction(exit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self.hotkey_filter = HotkeyFilter(hotkey, self.show_launcher.emit)
        app.installNativeEventFilter(self.hotkey_filter)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(30_000)
        self.reminder_timer.timeout.connect(self.deliver_reminders)
        self.reminder_timer.start()
        QTimer.singleShot(0, self.deliver_reminders)

    @property
    def tray_available(self) -> bool:
        return self.tray.isSystemTrayAvailable()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_launcher.emit()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_launcher.emit()

    @staticmethod
    def _assistant_icon() -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3478f6"))
        painter.drawRoundedRect(1, 1, 30, 30, 9, 9)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(8, 9, 16, 15, 5, 5)
        painter.setPen(QColor("#3478f6"))
        painter.setBrush(QColor("#3478f6"))
        painter.drawEllipse(11, 14, 3, 3)
        painter.drawEllipse(18, 14, 3, 3)
        painter.setPen(QColor("#ffffff"))
        painter.drawLine(16, 5, 16, 8)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(14, 3, 4, 4)
        painter.end()
        return QIcon(pixmap)

    def deliver_reminders(self, now: datetime | None = None) -> int:
        if not self.tray_available or not self.tray.supportsMessages():
            return 0
        delivered = 0
        for notice in self.task_service.pending_reminders(now=now):
            task = notice.task
            title = "Task overdue" if "|overdue" in notice.reminder_key else "Task reminder"
            if not self.tray.supportsMessages():
                break
            self.tray.showMessage(title, task.title, QSystemTrayIcon.MessageIcon.Information, 10_000)
            if self.task_service.record_reminder(task.id, notice.reminder_key, now or datetime.now(UTC)):
                delivered += 1
        return delivered

    def close(self) -> None:
        self.reminder_timer.stop()
        self.app.removeNativeEventFilter(self.hotkey_filter)
        self.hotkey_filter.close()
        self.tray.hide()
