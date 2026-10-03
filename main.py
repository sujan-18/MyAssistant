"""MyAssistant process entry point."""

from __future__ import annotations

import logging
import sys

from core.application import Application
from ui.launcher_window import LauncherWindow, create_application
from ui.index_worker import IndexWorker
from ui.task_panel import TaskPanel
from ui.windows_integration import WindowsIntegration
from system.windows import set_startup_enabled
from ui.voice_panel import VoicePanel


def main() -> int:
    qt_application = create_application()
    services = Application()
    window: LauncherWindow | None = None
    index_worker: IndexWorker | None = None
    windows: WindowsIntegration | None = None
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
        )
        window.hidden.connect(voice_panel.stop_recording)
        qt_application.aboutToQuit.connect(voice_panel.close)
        if sys.platform == "win32":
            set_startup_enabled(services.settings.start_with_windows)
            windows = WindowsIntegration(qt_application, services.task_service, services.settings.global_hotkey)
            windows.show_launcher.connect(window.show_and_focus)
            windows.quit_requested.connect(qt_application.quit)
            window.set_tray_available(windows.tray_available)
            if windows.hotkey_filter.error and services.logger is not None:
                services.logger.warning("%s", windows.hotkey_filter.error)
                window.statusBar().showMessage(windows.hotkey_filter.error, 10_000)
        window.exit_requested.connect(qt_application.quit)
        window.result_activated.connect(
            lambda result: logging.getLogger("myassistant").info(
                "Application launched: %s", result.name
            )
        )
        window.show_and_focus()
        if services.settings.index_roots:
            index_worker = IndexWorker(
                services.settings.paths.database,
                services.settings.index_roots,
                services.settings.index_exclusions,
            )

            def indexing_finished(report) -> None:
                if window is not None:
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
                if services.logger is not None:
                    services.logger.info("Filesystem index report: %s", report)

            index_worker.completed.connect(indexing_finished)
            index_worker.progress.connect(
                lambda count: window.set_index_status(f"Indexing configured locations… {count} entries scanned.")
                if window is not None
                else None
            )
            index_worker.failed.connect(
                lambda error: window.set_index_status(f"Filesystem indexing failed: {error}")
                if window is not None
                else None
            )
            index_worker.start()
        else:
            window.set_index_status(
                "Filesystem search is off. Configure absolute roots with MYASSISTANT_INDEX_ROOTS."
            )
        if services.logger is not None:
            services.logger.info("Desktop launcher started")
        return qt_application.exec()
    finally:
        if index_worker is not None and index_worker.isRunning():
            index_worker.cancel()
            index_worker.wait()
        if window is not None:
            window.hide()
        if windows is not None:
            windows.close()
        services.close()


if __name__ == "__main__":
    raise SystemExit(main())
