# Architecture Decision Log

**Document version:** 1.1  
**Last updated:** 2026-10-02  
**Status:** CPython 3.14.8 x64, PySide6 6.11.2, tzdata 2026.4, pytest 9.1.1, PyInstaller 6.22.3 and SQLite FTS5 are in use; optional voice packages are installed. The suite has 66 passing tests and one host-policy symlink skip; `pip check` is clean. The pinned local model is present, and WAV transcription was verified. Desktop microphone/speaker checks and clean-machine packaging acceptance remain open. See [TECHNOLOGY_EVALUATION.md](TECHNOLOGY_EVALUATION.md) for the original audit and later phase updates.

## ADR-001 — Build a native Python desktop application

- **Status:** Proposed
- **Decision:** Keep the application and domain logic in Python; use native Windows integration through narrow adapters.
- **Alternatives:** Electron/Tauri UI with a Python service; web application; a single script.
- **Reason:** The requirements center on Python, local filesystem access, Windows integration, and incremental development. A modular desktop process avoids an always-on local web server and avoids shipping a second UI runtime.
- **Consequences:** Packaging must collect Python and native GUI/runtime dependencies. Windows API calls should be isolated for testing and replacement.

## ADR-002 — PySide6 for the desktop UI

- **Status:** Selected; PySide6 6.11.2 installed in the project `.venv`
- **Decision:** Use Qt for Python (PySide6) for search, task dashboard/widget, tray and settings UI.
- **Alternatives:** PyQt6, Tkinter, Tauri, Electron.
- **Reason:** Official Qt Python bindings provide mature desktop widgets, event-loop and worker patterns, and suitable system-tray/window support. PySide uses LGPL/GPL/commercial licensing; redistribution must preserve applicable Qt notices and comply with the chosen license path. PyQt licensing is also GPL/commercial. Tkinter is bundled but has fewer facilities for a polished launcher and tray experience. Web-runtime options increase application size and introduce another stack.
- **Evidence:** Current official Qt for Python documentation and release history are linked in PROJECT_DOCUMENT.md.
- **Consequences:** The selected CPython 3.14.8 environment resolved the Windows x64 PySide6 wheel. GUI runtime and packaged application checks remain. Review Qt redistribution obligations before release. Use a UI-independent service layer.

## ADR-003 — SQLite as the local structured store; FTS5 for name/path search

- **Status:** Selected; FTS5 availability confirmed on the project interpreter and used by schema version 2.
- **Decision:** Store tasks, configuration metadata, application catalog and indexed filesystem metadata in SQLite; use FTS5 for text retrieval when the bundled SQLite build provides it.
- **Alternatives:** JSON files, a client/server database, Windows Search alone, a separate search service.
- **Reason:** The product is single-user and local-first. SQLite is embedded, transactional and needs no service; FTS5 supports indexed full-text matching and ranking. FTS5 is present in the selected Python SQLite build.
- **Consequences:** Keep writes short, use parameterized SQL, add schema migrations and backups, and avoid indexing file contents or unnecessary metadata by default. Database and WAL files belong in the user data directory, not the repository. If a future target lacks FTS5, its migration currently fails clearly; add a fallback only if needed.

## ADR-004 — Begin file indexing with a bounded Python walker; defer USN Journal

- **Status:** Selected for the initial implementation; large-drive performance remains to be measured.
- **Decision:** Prototype an explicit, cancellable `os.scandir`/filesystem walk over configured roots, persist metadata, and reconcile deleted/moved entries. Use `watchdog` only if incremental change events prove useful. Do not begin with whole-volume USN journal parsing.
- **Alternatives:** Windows Search API/provider, USN Change Journal, `watchdog` alone, scan-at-every-query.
- **Reason:** A basic walker is transparent and testable without elevated volume access. USN offers a potentially efficient NTFS change feed but has privilege, volume, journal-wrap, identity/reconciliation and implementation complexity. Windows Search can reuse an OS-managed index but only finds indexed scopes and complicates ranking and user configuration. A hybrid can be evaluated after measuring the prototype.
- **Consequences:** Configured roots are opt-in; the worker indexes in batches of 250 and reports progress. It skips hidden/system entries and symlinks; it reconciles stale rows only after a complete root scan. Startup scans can still be long for large roots. Incremental change detection and large-volume performance remain open questions.

## ADR-005 — Use native Win32 `RegisterHotKey` behind a hotkey adapter

- **Status:** Proposed
- **Decision:** Prefer a Qt-integrated native registration using `RegisterHotKey`/`WM_HOTKEY` (or an audited wrapper), with a configurable shortcut and conflict feedback.
- **Alternatives:** `keyboard` package global hooks; `pynput`; Qt-only shortcuts.
- **Reason:** Windows provides a system-wide registration API for this exact use. It is narrower than a global keyboard hook, while Qt-only shortcuts are not global. The Python `keyboard` package is convenient but hooks global input and has deployment and reliability considerations.
- **Consequences:** A shortcut can be unavailable due to conflict; do not suppress arbitrary keyboard input. Test registration, release and shutdown behavior on supported Windows builds.

## ADR-006 — Speech recognition remains an optional, replaceable adapter

- **Status:** Selected initial path: faster-whisper CPU/int8, with a replaceable recognizer interface
- **Decision:** Keep speech behind a `SpeechRecognizer` interface. Evaluate `whisper.cpp` first for a local CPU-capable prototype; compare faster-whisper CPU/int8 and Vosk with real microphone samples. Treat GPU inference as an optional optimization.
- **Reason:** The detected MX330 has 2 GB VRAM, making larger GPU models a poor default. Whisper-family quality is attractive, but CTranslate2 CUDA dependencies and version matching add deployment complexity. Vosk is light and streaming-oriented but may trade transcription quality and language flexibility. No model is downloaded or installed in Phase 0.
- **Consequences:** Benchmark latency, memory, accuracy, noise robustness, model license and redistribution separately on this machine. Provide a no-voice configuration and clear missing-model errors.

## ADR-007 — TTS uses Windows voices initially; Piper is not the default

- **Status:** Selected and implemented with Windows SAPI through optional pywin32
- **Decision:** First TTS adapter should use installed Windows speech voices through a supported Windows interface, subject to a small compatibility proof. Keep offline neural TTS as a later optional backend.
- **Alternatives:** Piper, pyttsx3/SAPI, cloud TTS.
- **Reason:** Existing Windows voices avoid model downloads and GPU requirements. The original `rhasspy/piper` repository is archived (October 2025), and voice/model licenses vary, so selecting it as a default would need extra maintenance and licensing review. Cloud TTS conflicts with local-first defaults.
- **Consequences:** Voice quality depends on installed Windows voices. Validate desktop Python interop and choose the exact API before implementation. Any neural voice must be separately licensed and opt-in.

## ADR-008 — Defer LLM provider and keep all actions typed and allowlisted

- **Status:** Proposed
- **Decision:** Implement deterministic command parsing first. Later AI may propose a typed action from an allowlist; validation and ordinary application code decide whether it is executable. No shell command is an allowed model output.
- **Alternatives:** Always-on cloud LLM, local LLM, no natural-language layer.
- **Reason:** Most initial commands are deterministic; private filesystem metadata should not be uploaded by default. A future provider must be justified by observed user needs.
- **Consequences:** Natural-language breadth will be limited initially. Any cloud provider requires explicit opt-in, data-flow disclosure, and minimization; local models need hardware and licensing evaluation.

## ADR-009 — Startup integration begins with the per-user Startup folder

- **Status:** Proposed
- **Decision:** When implemented, offer opt-in per-user Startup-folder registration as the initial mechanism; remove it cleanly when disabled.
- **Alternatives:** Run-key registry entry, Task Scheduler, package-managed startup.
- **Reason:** It is visible and reversible for a per-user assistant and does not require administrator rights. Task Scheduler can be reconsidered if reliable delayed/background startup or packaged deployment requires it.
- **Consequences:** Startup behavior is per-user and may be affected by Windows startup settings. Never enable it without user preference.

## ADR-010 — PyInstaller is the first packaging candidate

- **Status:** Selected for a one-folder prototype; clean-machine and installer acceptance remain.
- **Decision:** Use pinned PyInstaller 6.22.3 to build a one-folder Windows prototype; evaluate a one-file bundle only if distribution needs it. Compare Nuitka on startup, size, reliability and build maintenance before release.
- **Reason:** PyInstaller has a mature Python application bundling workflow and avoids introducing a compiler toolchain in the default path. Nuitka supports newer Python but requires compiler/build tooling and creates more complex build diagnostics.
- **Consequences:** The build extra and `scripts/build_windows.ps1` collect the GUI, local speech runtime and native dependencies. Build on Windows for Windows, audit Qt plugins/native libraries, and produce clean-machine startup/voice checks before declaring a release. User data and speech weights stay outside the bundle.

## ADR-011 — Keep runtime state out of the source checkout

- **Status:** Proposed
- **Decision:** Store mutable database, logs, user configuration and downloaded models under Windows per-user application data (for example `%LOCALAPPDATA%\MyAssistant`); allow a documented override for development.
- **Reason:** The source path is not a reliable writable runtime location after installation, and personal data should not enter Git.
- **Consequences:** Resolve paths via a platform-aware path service; define backup/retention behavior and do not log raw queries or private paths by default.

## ADR-012 — Use CPython 3.14.8 x64 as the project baseline

- **Status:** Selected; CPython 3.14.8 x64 GIL environment active; PySide6 and pytest installed; Phase 2 tests pass
- **Decision:** Target standard GIL CPython 3.14.8 x64 for development and initial packaging. Do not target free-threaded `3.14t` or Python 3.15 prerelease.
- **Alternatives:** Keep installed CPython 3.14.5; target CPython 3.13.16; wait for Python 3.15 stable.
- **Reason:** As of 2026-10-02, 3.14.8 is the latest 3.14 maintenance release. PySide6 6.11.2 publishes a `cp310-abi3-win_amd64` wheel, CTranslate2 4.8.2 publishes a `cp314-win_amd64` wheel, pytest 9.1.1 supports Python 3.14 and PyInstaller 6.22.3 supports Python 3.14. Thus the key proposed native dependencies no longer justify defaulting to 3.13. Python.org still lists 3.15 as prerelease. See [Technology Evaluation](TECHNOLOGY_EVALUATION.md).
- **Consequences:** The standard GIL 3.14.8 environment is active and PySide6/pytest resolve on it. Keep 3.13.16 as fallback only if an essential later-selected native dependency demonstrably fails on 3.14. Validate a packaged GUI rather than relying only on wheel tags. The Phase 2 tests pass; this does not validate the GUI or packaging.

## ADR-013 — CPU speech inference is mandatory; MX330 CUDA is optional and experimental

- **Status:** Selected
- **Decision:** All voice architecture must work on CPU. GPU acceleration is an optional backend, never an application requirement.
- **Alternatives:** Make CUDA mandatory; target CUDA 13 for GPU; omit GPU experiments entirely.
- **Reason:** MX330 is Pascal compute capability 6.1 and has 2 GB VRAM. CUDA 13 drops Pascal support. CTranslate2 and whisper.cpp indicate CC 6.1 can be supported by suitable older toolchains, but that is separate from the currently reported CUDA 13 driver level. For small speech models, the speed benefit may not justify CUDA runtime packaging complexity; benchmark CPU first.
- **Consequences:** Do not install CUDA or model assets during setup. If an experiment is justified, prove a CUDA 12/sm_61-supported engine/runtime combination, quantify memory and speed, and keep a clean CPU fallback. Do not plan a local LLM around 2 GB VRAM.

## ADR-014 — Bundle IANA timezone data for correct Windows deadlines

- **Status:** Selected; `tzdata==2026.4` installed in `.venv` and declared as a runtime dependency.
- **Decision:** Use the standard-library `zoneinfo` API backed by the first-party `tzdata` package so deadlines can use IANA timezone IDs and historical/future daylight-saving rules on Windows.
- **Evidence:** `ZoneInfo("Asia/Kathmandu")` raised `ZoneInfoNotFoundError` on the machine before installation; it resolves after installing tzdata. Python’s documentation recommends declaring tzdata on Windows when IANA timezone data is required. The selected wheel is platform-independent and Apache-2.0.
- **Alternatives:** Store only UTC/fixed offsets; query Windows timezone APIs and maintain a Windows-to-IANA map; add a larger third-party datetime library.
- **Consequences:** Adds a small pure-data runtime dependency that should be updated when timezone rules change. Local deadline input rejects nonexistent DST wall times and asks the user to choose a fold for ambiguous times. The project stores UTC instants plus the IANA zone ID.

## ADR-015 — Use Qt tray messages and an opt-in Startup-folder script for Phase 7

- **Status:** Selected and implemented; interactive Windows verification remains.
- **Decision:** Use `QSystemTrayIcon` for launcher access and task reminders; expose startup as an off-by-default Settings choice with `MYASSISTANT_START_WITH_WINDOWS` as a scripted default. The startup script targets `main.py` in development and the frozen executable in packaged mode. Use native Win32 `RegisterHotKey` with a configurable `MYASSISTANT_GLOBAL_HOTKEY` (default `Ctrl+Alt+M`, chosen to avoid common Ctrl+Space input-method conflicts).
- **Alternatives:** Global keyboard hooks, registry Run key, Task Scheduler, native actionable toast integration.
- **Reason:** Qt is already a runtime dependency; `RegisterHotKey` is the narrow OS facility for this behavior; the Startup-folder script is visible and reversible without admin rights. Native toast actions need a packaging identity and are deferred.
- **Consequences:** A hotkey conflict is logged and leaves the app usable. Reminder delivery checks tray/message availability and persists deduplication only when message delivery can be attempted. Without a tray, closing exits rather than leaving a hidden process. Startup uses the frozen executable path in packaged mode.

## ADR-016 — Add explicit, local CPU-first speech input and output

- **Status:** Selected and implemented as the Phase 8 initial path; model/audio smoke checks remain.
- **Decision:** Use the optional `sounddevice` 0.5.6 package for user-triggered push-to-talk; use faster-whisper 1.2.1/CTranslate2 4.8.2 on CPU int8; offer the multilingual Whisper tiny model at a pinned revision; use installed Windows SAPI voices through optional pywin32 312 for user-triggered TTS.
- **Alternatives:** whisper.cpp CLI, Vosk, CUDA inference, always-on microphone, cloud STT/TTS, neural TTS.
- **Reason:** Current Windows/Python 3.14 wheels were installed and imported successfully. This chain has a direct Python API and CPU path, fits the MX330's 2 GB VRAM limitation, and supports local processing. The small model is MIT licensed and supports multilingual recognition. SAPI avoids another voice model and package beyond the optional Windows bindings.
- **Consequences:** Voice dependencies are optional and do not prevent app startup if absent. Microphone capture is explicit, capped at 60 seconds, stored temporarily and deleted after transcription. Model download is separate and requires confirmation; transcribed text remains preview-only. The pinned model weights are present locally and WAV transcription succeeded after the PyAV compatibility fix. No CUDA is installed. Physical microphone capture and audible TTS still need desktop verification.

## ADR-017 — Make the startup task greeting opt-in and local

- **Status:** Selected and implemented; audible Windows verification remains.
- **Decision:** Let the user independently enable Windows sign-in startup and a spoken task greeting. Generate the greeting from open task counts, overdue tasks and up to three upcoming deadlines, then speak it through the existing Windows SAPI adapter. Both preferences are off by default.
- **Alternatives:** Always speak on launch; use microphone/wake-word input; send task data to a cloud speech service.
- **Reason:** The user's requested laptop greeting should work without a network model or microphone and should announce relevant deadlines while preserving explicit control.
- **Consequences:** The optional pywin32/SAPI dependency and an installed Windows speech voice are required. The greeting reveals task titles to anyone within hearing range, so it stays separately opt-in. No task descriptions are spoken.
