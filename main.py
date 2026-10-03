"""MyAssistant process entry point."""

from __future__ import annotations

import logging
import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QIODevice, QLocalServer, QLocalSocket, QSettings, QTimer

from core.application import Application
from ui.launcher_window import LauncherWindow, create_application
from ui.dashboard_widget import DashboardWidget
from ui.index_worker import IndexWorker
from ui.task_panel import TaskPanel
from ui.windows_integration import WindowsIntegration
from system.windows import set_startup_enabled
from ui.voice_panel import SpeechOutputWorker, VoicePanel
from voice.greeting import build_task_greeting


def main() -> int:
    qt_application = create_application()
    instance_name = "MyAssistant.DesktopWidget"
    instance_server = QLocalServer(qt_application)
    if not instance_server.listen(instance_name):
        existing = QLocalSocket()
        existing.connectToServer(instance_name, QIODevice.OpenModeFlag.WriteOnly)
        if existing.waitForConnected(750):
            existing.write(b"show")
            existing.waitForBytesWritten(750)
            existing.disconnectFromServer()
            return 0
        instance_server.close()
        QLocalServer.removeServer(instance_name)
        if not instance_server.listen(instance_name):
            raise RuntimeError("Could not establish the MyAssistant single-instance channel")
    services = Application()
    preferences = QSettings("MyAssistant", "MyAssistant")
    stored_roots = preferences.value("index/roots", None)
    stored_exclusions = preferences.value("index/exclusions", None)
    start_with_windows = preferences.value(
        "startup/enabled", services.settings.start_with_windows, type=bool
    )
    speak_startup_greeting = preferences.value("startup/greeting", False, type=bool)
    if stored_roots is not None or stored_exclusions is not None:
        if isinstance(stored_roots, str):
            stored_roots = [stored_roots]
        if isinstance(stored_exclusions, str):
            stored_exclusions = [stored_exclusions]
        roots = services.settings.index_roots if stored_roots is None else tuple(
            Path(path).expanduser().resolve() for path in stored_roots
            if Path(path).expanduser().is_absolute()
        )
        exclusions = services.settings.index_exclusions if stored_exclusions is None else tuple(
            Path(path).expanduser().resolve() for path in stored_exclusions
            if Path(path).expanduser().is_absolute()
        )
        services.settings = replace(
            services.settings, index_roots=roots, index_exclusions=exclusions
        )
    window: LauncherWindow | None = None
    index_worker: IndexWorker | None = None
    index_generation = 0
    windows: WindowsIntegration | None = None
    dashboard: DashboardWidget | None = None
    greeting_worker: SpeechOutputWorker | None = None
    try:
        services.start()
        if services.task_service is None:
            raise RuntimeError("Task service did not initialize")
        model_dir = services.settings.speech_model_dir or (
            services.settings.paths.data_dir / "models" / "faster-whisper-tiny"
        )
        voice_panel = VoicePanel(model_dir)
        window = LauncherWindow(
            services.search_launcher,
            services.open_search_result,
            TaskPanel(services.task_service, services.settings.timezone_id),
            voice_panel,
            index_roots=tuple(map(str, services.settings.index_roots)),
            index_exclusions=tuple(map(str, services.settings.index_exclusions)),
            search_scoped=lambda query, scope: services.search_launcher(query, scope=scope),
            start_with_windows=start_with_windows,
            speak_startup_greeting=speak_startup_greeting,
        )
        window.hidden.connect(voice_panel.stop_recording)
        qt_application.aboutToQuit.connect(voice_panel.close)
        if sys.platform == "win32":
            set_startup_enabled(start_with_windows)
            windows = WindowsIntegration(qt_application, services.task_service, services.settings.global_hotkey)
            dashboard = DashboardWidget(
                services.task_service,
                lambda query, scope: services.search_launcher(query, scope=scope),
                services.open_search_result,
                window.show_and_focus,
                services.settings.timezone_id,
                tuple(map(str, services.settings.index_roots)),
            )
            windows.show_launcher.connect(dashboard.show_and_focus)
            windows.toggle_launcher.connect(dashboard.toggle_visible)
            windows.quit_requested.connect(qt_application.quit)
            window.set_tray_available(windows.tray_available)
            if windows.hotkey_filter.error and services.logger is not None:
                services.logger.warning("%s", windows.hotkey_filter.error)
                window.statusBar().showMessage(windows.hotkey_filter.error, 10_000)

        def activate_from_taskbar() -> None:
            while instance_server.hasPendingConnections():
                connection = instance_server.nextPendingConnection()
                if connection is None:
                    continue

                def read_request(client=connection) -> None:
                    if b"show" not in bytes(client.readAll()):
                        return
                    if dashboard is not None:
                        dashboard.show_and_focus()
                    elif window is not None:
                        window.show_and_focus()

                connection.readyRead.connect(read_request)
                connection.disconnected.connect(connection.deleteLater)
                if connection.bytesAvailable():
                    read_request()

        instance_server.newConnection.connect(activate_from_taskbar)
        window.exit_requested.connect(qt_application.quit)

        def update_startup_preferences(enabled: bool, _greeting_enabled: bool) -> None:
            if sys.platform != "win32":
                return
            try:
                set_startup_enabled(enabled)
                window.statusBar().showMessage(
                    "Windows sign-in startup " + ("enabled." if enabled else "disabled."), 4000
                )
            except OSError as exc:
                if services.logger is not None:
                    services.logger.exception("Could not update Windows startup preference")
                window.statusBar().showMessage(f"Could not update Windows startup: {exc}", 8000)

        window.startup_preferences_changed.connect(update_startup_preferences)
        window.index_configuration_changed.connect(
            lambda roots, exclusions: start_indexing(roots, exclusions)
        )
        window.result_activated.connect(
            lambda result: logging.getLogger("myassistant").info(
                "Application launched: %s", result.name
            )
        )
        if dashboard is not None and windows is not None:
            if windows.tray_available:
                dashboard.hide()
            else:
                dashboard.show_and_focus()
        else:
            window.show_and_focus()
        if sys.platform == "win32" and speak_startup_greeting:

            def speak_startup_tasks() -> None:
                nonlocal greeting_worker
                if services.task_service is None:
                    return
                tasks = services.task_service.list_tasks("open") 
                greeting = build_task_greeting(tasks, services.settings.timezone_id)
                greeting_worker = SpeechOutputWorker(greeting)
                greeting_worker.failed.connect(
                    lambda error: services.logger.warning("Startup greeting failed: %s", error)
                    if services.logger is not None else None
                )
                greeting_worker.start()

            QTimer.singleShot(1800, speak_startup_tasks)

        def start_indexing(roots, exclusions) -> None:
            nonlocal index_worker, index_generation
            if window is None:
                return
            index_generation += 1
            generation = index_generation
            root_paths = tuple(Path(path).expanduser().resolve() for path in roots)
            exclusion_paths = tuple(Path(path).expanduser().resolve() for path in exclusions)
            services.settings = replace(
                services.settings,
                index_roots=root_paths,
                index_exclusions=exclusion_paths,
            )
            window.set_index_roots(tuple(map(str, root_paths)), tuple(map(str, exclusion_paths)))
            if dashboard is not None:
                dashboard.set_index_roots(tuple(map(str, root_paths)))
            if index_worker is not None and index_worker.isRunning():
                index_worker.cancel()
                index_worker.wait()
            if not root_paths:
                window.set_index_status("File search is off. Add searchable folders in Settings.")
                return

            window.set_index_status("Indexing selected folders in the background…")
            worker = IndexWorker(
                services.settings.paths.database,
                root_paths,
                exclusion_paths,
            )
            index_worker = worker

            def indexing_finished(report) -> None:
                if generation != index_generation or window is None:
                    return
                if report.cancelled:
                    window.set_index_status("Filesystem indexing was cancelled; prior entries were retained.")
                elif report.errors:
                    window.set_index_status(
                        f"Index refreshed with {report.errors} inaccessible item(s); stale entries were retained."
                    )
                else:
                    window.set_index_status(
                        f"Indexed {report.entries_indexed} item(s) across {report.roots_completed} configured root(s)."
                    )
                window.refresh_search()
                if services.logger is not None:
                    services.logger.info("Filesystem index report: %s", report)

            worker.completed.connect(indexing_finished)
            worker.progress.connect(
                lambda count: window.set_index_status(
                    f"Indexing configured locations… {count} entries scanned."
                ) if window is not None and generation == index_generation else None
            )
            worker.failed.connect(
                lambda error: window.set_index_status(f"Filesystem indexing failed: {error}")
                if window is not None and generation == index_generation
                else None
            )
            worker.start()

        start_indexing(
            tuple(map(str, services.settings.index_roots)),
            tuple(map(str, services.settings.index_exclusions)),
        )
        if services.logger is not None:
            services.logger.info("Desktop launcher started")
        return qt_application.exec()
    finally:
        if index_worker is not None and index_worker.isRunning():
            index_worker.cancel()
            index_worker.wait()
        if greeting_worker is not None and greeting_worker.isRunning():
            greeting_worker.wait()
        if window is not None:
            window.hide()
        if dashboard is not None:
            dashboard.hide()
        if windows is not None:
            windows.close()
        services.close()


if __name__ == "__main__":
    raise SystemExit(main())
