# MyAssistant

MyAssistant is a local-first Windows desktop assistant for launching applications, finding files and folders, and managing tasks and deadlines. Optional voice and natural-language features remain future work.

## Project status

**Phase 6 — Task management implemented.** The Tasks tab supports task CRUD, tags, priorities, filtering, deadlines, countdowns and durable reminder rules. Deadlines use UTC plus an IANA timezone. 43 tests pass; one symlink test is skipped because Windows restricts symlink creation. Read [PROJECT_DOCUMENT.md](PROJECT_DOCUMENT.md) for requirements and roadmap, and [docs/DECISION_LOG.md](docs/DECISION_LOG.md) for technology choices.

## Development environment

The inspected machine reports Windows build 26100, Python 3.14.8, Git 2.53.0, and an NVIDIA GeForce MX330 with 2 GB VRAM. Phase 1 upgraded the prior 3.14.5 system interpreter to the audited 3.14.8 baseline. CPU inference is the required baseline; MX330 GPU use is experimental because its 2 GB VRAM is limited and CUDA 13 drops Pascal support. Hardware inventory was partly blocked by Windows Management Instrumentation permissions; see the project document.

The project targets CPython 3.14.8 x64. PySide6 6.11.2 and tzdata 2026.4 are runtime dependencies; pytest 9.1.1 is installed for development. The editable project package is installed in `.venv`. SQLite FTS5 is enabled by migration 2. Run the full suite with `.venv\Scripts\python.exe -m pytest`.

Filesystem indexing is opt-in. In PowerShell, set absolute roots and optional excluded subfolders before launching:

```powershell
$env:MYASSISTANT_INDEX_ROOTS = "C:\Users\you\Documents;D:\Projects"
$env:MYASSISTANT_INDEX_EXCLUSIONS = "C:\Users\you\Documents\Private"
$env:MYASSISTANT_TIMEZONE = "Asia/Kathmandu"
```

The app scans configured roots in a background worker on startup. It indexes names and metadata only; it does not read file contents. Hidden/system items and symlinks are skipped. A scan with errors retains old rows for the affected root.

Deadlines use the configured IANA timezone; if unset, the app uses UTC. It rejects local times skipped by daylight-saving transitions and asks which occurrence to use when a local time happens twice. Reminder rules are persisted and deduplicated; tray/system notification delivery is part of Phase 7.

## Developer setup

After installing CPython 3.14.8 x64, create an environment and install the selected runtime and development dependencies:

```powershell
C:\Python314\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

The Python launcher (`py`) is not available on this machine. Use the installed Python executable directly if recreating the environment.

## Planned layout

```text
MyAssistant/
├── main.py                 # application composition and entry point
├── config.py               # configuration loading and validation
├── core/                   # lifecycle, command types, orchestration
├── database/               # SQLite access, schema and migrations
├── launcher/               # application and file opening adapters
├── search/                 # indexing, retrieval and ranking
├── todo/                   # tasks, deadlines and reminders
├── ui/                     # PySide6 windows, tray and notifications
├── system/                 # Windows startup and hotkey adapters
├── voice/                  # replaceable speech and TTS interfaces
├── docs/                   # architecture decisions and supporting docs
└── tests/                  # isolated tests, mocks and temporary fixtures
```

Directories and modules will be introduced as their phase begins; this is a proposed structure, not a claim that those components exist.

## Next step

Phase 6 task management is implemented. Phase 7 Windows integration (global hotkey, tray, notifications and opt-in startup) is next.
