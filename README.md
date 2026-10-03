# MyAssistant

MyAssistant is a local-first Windows desktop assistant for launching applications, finding files and folders, and managing tasks and deadlines. It also supports push-to-talk speech, Windows speech output, and an optional spoken task greeting at startup.

## Project status

**Phases 2–8 are implemented; hardware acceptance remains.** The Voice tab has push-to-talk capture, preview-only transcription, explicit local model download and on-demand Windows speech output. The pinned model is present and WAV transcription succeeded; physical microphone and audible TTS checks remain. The voice extra is optional, and no audio is captured until Record is pressed. A PyInstaller one-folder prototype is also configured. Read [PROJECT_DOCUMENT.md](PROJECT_DOCUMENT.md) for the roadmap and [docs/DECISION_LOG.md](docs/DECISION_LOG.md) for technology choices.

## Development environment

The inspected machine reports Windows build 26100, Python 3.14.8, Git 2.53.0, and an NVIDIA GeForce MX330 with 2 GB VRAM. Phase 1 upgraded the prior 3.14.5 system interpreter to the audited 3.14.8 baseline. CPU inference is the required baseline; MX330 GPU use is experimental because its 2 GB VRAM is limited and CUDA 13 drops Pascal support. Hardware inventory was partly blocked by Windows Management Instrumentation permissions; see the project document.

The project targets CPython 3.14.8 x64. PySide6 6.11.2 and tzdata 2026.4 are runtime dependencies; pytest 9.1.1 is installed for development. The editable project package is installed in `.venv`. SQLite FTS5 is enabled by migration 2. Run the full suite with `.venv\Scripts\python.exe -m pytest`.

To install the optional speech input/output stack in the development environment, run `.venv\Scripts\python.exe -m pip install -e ".[dev,voice]"`. The Whisper model is a separate one-time download initiated from the Voice tab after a confirmation prompt. It uses CPU int8 and stores model assets under `%LOCALAPPDATA%\MyAssistant\models` by default; override with `MYASSISTANT_SPEECH_MODEL_DIR`.

Open the **Voice** tab, approve the model download while online, then use **Record** and **Stop recording** to capture a clip. Review the transcript before choosing **Speak transcript**. Captured audio is temporary and removed after transcription; transcript text is never executed.

File and folder search is a separate Home search mode from application search. To enable it, open **Settings**, choose folders such as `C:\MyAssistant`, your `D:\Projects` folder, or your OneDrive folder, add any folders to exclude, and click **Save and index**. MyAssistant remembers these folders, so you do not need to set PowerShell variables every time. The first scan and later startup refreshes run in the background. Search uses file and folder names and paths, not document contents.

Environment variables remain available for scripted or development setup:

```powershell
$env:MYASSISTANT_TIMEZONE = "Asia/Kathmandu"
$env:MYASSISTANT_GLOBAL_HOTKEY = "Ctrl+Alt+M"
# Optional; defaults to false.
$env:MYASSISTANT_START_WITH_WINDOWS = "false"
```

To have MyAssistant start at Windows sign-in and optionally speak your task deadlines, open **Settings** and enable **Start MyAssistant when I sign in to Windows** and **Speak a greeting with my upcoming tasks**. These options are saved on this computer and are off by default. The greeting uses Windows speech output, reads open task titles and deadlines, and does not use the microphone. Enable startup after you are ready for this source-based development copy to launch at sign-in.

The app scans configured roots in a background worker on startup. It indexes names and metadata only; it does not read file contents. Hidden/system items and symlinks are skipped. A scan with errors retains old rows for the affected root.

Deadlines use the configured IANA timezone; if unset, the app uses UTC. It rejects local times skipped by daylight-saving transitions and asks which occurrence to use when a local time happens twice. Reminder rules are persisted and deduplicated, then delivered through tray messages when Windows reports tray notification support.

## Developer setup

After installing CPython 3.14.8 x64, create an environment and install the selected runtime and development dependencies:

```powershell
C:\Python314\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

The Python launcher (`py`) is not available on this machine. Use the installed Python executable directly if recreating the environment.

## Build a Windows one-folder prototype

Install the optional build extra and run the PowerShell script from the project:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,voice,build]"
.\scripts\build_windows.ps1
```

The built prototype is written to `dist\MyAssistant`. Keep the complete folder when running or distributing it. User data and the speech model remain under `%LOCALAPPDATA%\MyAssistant`; neither is bundled. This is a development build, not an installer or signed release.

## Project status

The core launcher, file search, tasks, Windows integration and voice code are implemented. The pinned speech model is present, and automated checks report **66 passed, 1 skipped** (Windows symlink creation is restricted). A one-folder build starts from an isolated working directory. Remaining acceptance work includes an actual desktop microphone/speaker check and checking the packaged build on a clean Windows account. The optional AI provider remains deferred. See [PROJECT_DOCUMENT.md](PROJECT_DOCUMENT.md) for the full status.
