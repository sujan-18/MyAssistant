# MyAssistant — Complete Technology Compatibility Audit

**Evaluation date:** 2026-10-02 (Asia/Katmandu)  
**Document version:** 1.0  
**Project stage:** Pre-install compatibility audit completed. The audit baseline had no installed project dependencies. A later setup action installed the selected initial dependencies; current environment state is recorded in the post-audit note below. No tests were run as part of the audit.  
**Hardware context:** Windows build 26100 (Windows 11 24H2 family); user reports standard CPython 3.14.5 installed and 16 GB RAM (RAM not WMI-verified); NVIDIA GeForce MX330, 2 GB VRAM; NVIDIA driver 581.95; `nvidia-smi` reports CUDA 13.0 driver compatibility. Git 2.53.0. The repository's `.python-version`/`pyproject.toml` target 3.14.8; confirm the actual system interpreter and refresh the stale `.venv` metadata during Phase 1. No package changes were made for this audit.

This is a compatibility review of the proposed stack as a whole, not a claim that the application or any package has been tested on this machine. Version numbers below are the latest observed on the review date; pin exact releases only after Phase 1 validation.

## 1. Executive recommendation

**Recommend standard CPython 3.14.8 x64 for the project as a whole.** Python 3.14.8 is the latest 3.14 maintenance release (2026-09-30); 3.13.16 is also current but is now in security-fixes-only maintenance. Python 3.14 has a longer support horizon and the dependency chain now has Windows x64 compatibility evidence: PySide6 6.11.2 offers a stable-ABI wheel, CTranslate2 4.8.2 publishes a `cp314-win_amd64` wheel, pytest 9.1.1 lists Python 3.14 and PyInstaller 6.22.3 requires Python >=3.8,<3.16. This is based on whole-stack evidence, not recency alone. The remaining meaningful risk is the unselected microphone/audio binding and actual Qt/PyInstaller runtime smoke tests; keep Python 3.13.16 as a fallback only if those produce a reproducible blocker. [Python version status](https://devguide.python.org/versions/), [Python 3.14.8](https://www.python.org/downloads/release/python-3148/), [Python 3.13.16](https://www.python.org/downloads/release/python-31316/), [PySide6 wheels](https://pypi.org/project/PySide6/), [CTranslate2 wheels](https://pypi.org/project/ctranslate2/), [pytest](https://pypi.org/project/pytest/), [PyInstaller 6.22.3 metadata](https://pypi.org/project/pyinstaller/6.22.3/).

This recommendation is conditional on one Phase 1 compatibility spike using the actual standard GIL CPython build (not free-threaded Python): resolve/install only then, launch a small PySide6 window, import the intended audio bindings if selected, confirm SQLite FTS5 at runtime, run pytest, and create/launch a disposable package build. No install or test was done for this audit.

**GPU conclusion:** the MX330’s 2 GB VRAM is not a suitable foundation for the application’s AI features. CPU inference should be the default and always-supported fallback. Small speech models could fit in memory, but actual speed and quality must be measured. More critically, MX330 belongs to Pascal compute capability 6.1; CUDA Toolkit 13 removed support for Maxwell, Pascal and Volta. The installed driver’s “CUDA 13.0” line is a driver capability indicator, not a guarantee that CUDA 13 inference kernels can run on this GPU. A GPU experiment would need a supported CUDA 12-era/runtime build or an engine-specific backend compiled for sm_61, if dependencies still provide one. Do not install CUDA tooling for this project now. [CUDA 13 release notes](https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html), [CTranslate2 hardware support](https://opennmt.net/CTranslate2/hardware_support.html), [CTranslate2 quantization](https://opennmt.net/CTranslate2/quantization.html), [whisper.cpp CUDA architectures](https://github.com/ggml-org/whisper.cpp/blob/master/ggml/src/ggml-cuda/CMakeLists.txt).

## 2. Status vocabulary

- **Selected:** approved architectural direction for implementation; not installed unless stated.
- **Recommended but not yet installed:** preferred package/API for a future phase, still subject to compatibility spike.
- **Experimental:** candidate to benchmark or prove with a contained prototype.
- **Deferred:** intentionally postponed; keep an interface seam but add no runtime dependency now.
- **Rejected:** not recommended for this project’s initial design, with reason recorded.

“Selected” and “Recommended but not yet installed” are architecture states, not install instructions. Nothing is to be installed as a result of this audit.

## 3. Python runtime decision

| Runtime | Current status (review date) | Compatibility view | Decision |
|---|---|---|---|
| CPython 3.14.8 x64, standard GIL | Current bug-fix series; 3.14.8 released 2026-09-30. Support scheduled through 2030-10. | Core GUI, inference binding, test runner and packaging have current Python 3.14 evidence. Gives current maintained feature line and avoids pinning to a series whose bug-fix releases have stopped. | **Selected — recommended project baseline.** Install only in Phase 1 if the user proceeds. |
| CPython 3.14.5 (user-reported machine installation) | Installed, but superseded by 3.14.8. | Same feature series; not the latest security/maintenance patch. | **Rejected as project pin.** Do not use it for the new environment; select 3.14.8 when environment setup is authorized. |
| CPython 3.13.16 x64 | Released 2026-09-30 as the final full maintenance release; subsequent 3.13 releases are security-fixes-only. | Native wheels exist for CTranslate2 and core dependencies, but do not provide a demonstrated advantage for this stack. | **Experimental fallback only.** Revisit if an actual transitive Windows wheel or packaging issue appears under 3.14. |
| CPython 3.15 | Python.org lists 3.15 as pre-release on 2026-10-02. | Too early for the project’s audio/native dependency and packaging chain, even though some tools may already claim support. | **Rejected for current baseline.** Re-evaluate after stable release and ecosystem wheels. |

### Why 3.14 instead of 3.13

The key historical risk was compiled-extension availability, not PySide6 alone. Current published evidence closes the key gaps:

- PySide6 6.11.2 Windows x64 wheel is `cp310-abi3`, so it targets CPython 3.10+ ABI-compatible builds, including CPython 3.14.
- CTranslate2 4.8.2 has a native `cp314-cp314-win_amd64` wheel (as well as cp313), removing the main Python-version concern for faster-whisper’s compiled dependency.
- pytest 9.1.1 is a universal Python wheel, requires Python 3.10+, and lists Python 3.14.
- PyInstaller 6.22.3 supports Python 3.8–3.15 and collects PySide6 through maintained hooks, but the real application still needs a package smoke test.
- The app’s core OS integration can use the Windows APIs through Python’s standard `ctypes` module, avoiding a compiled hotkey dependency.

3.13 may still be more comfortable for an unusual optional extension or older vendor binary, but no such dependency is selected for the initial stack. Pinning 3.13 “just in case” would trade away the current 3.14 feature line without a concrete blocker. This recommendation does not extend to free-threaded CPython 3.14t; use ordinary GIL CPython wheels because downstream support is more uneven.

## 4. Compatibility matrix for the complete stack

| Component | Status and recommended technology | Current version/status and Python/Windows compatibility | Hardware, offline and license | Fit, trade-offs and install timing |
|---|---|---|---|---|
| Python runtime | **Selected:** CPython 3.14.8 x64, standard GIL | Latest 3.14 patch observed 2026-09-30; core selected dependencies publish compatible Windows artifacts. Windows build 26100 is suitable. | No special hardware; PSF license. | Best overall balance after current wheel evidence. Install in Phase 1, not now. Avoid 3.14t and 3.15 prerelease. |
| GUI | **Selected; installed:** PySide6 | 6.11.2 installed in `.venv`; Windows x64 `cp310-abi3` wheel, thus suitable for CPython 3.14. Official Qt for Python project. | Modest UI workload works on this machine; completely offline. LGPLv3/GPLv3 or commercial Qt terms; packaging/notice compliance required. | Appropriate. Strong widgets, Qt event loop, worker pattern and tray support. Larger bundle and licensing diligence. GUI creation/packaging smoke checks remain. |
| Microphone input | **Selected; installed optional:** sounddevice 0.5.6 | Pure Python wheel `py3-none-win_amd64`; bundles PortAudio DLLs on Windows and imports under CPython 3.14. [PyPI wheel](https://pypi.org/project/sounddevice/0.5.6/), [project docs](https://python-sounddevice.readthedocs.io/) | MIT package; local capture; no GPU. | App records only after explicit Record click, caps each clip at 60 seconds and writes temporary mono PCM WAV. Internal mic enumerates at 44.1 kHz; the app resamples to 16 kHz. Actual recording is not yet tested. |
| Speech recognition, selected initial path | **Selected; installed optional:** faster-whisper 1.2.1 + CTranslate2 4.8.2 | Installed and imported on CPython 3.14.8 / Windows x64. CTranslate2 publishes a `cp314-cp314-win_amd64` wheel. [faster-whisper](https://pypi.org/project/faster-whisper/1.2.1/), [CTranslate2 wheel](https://pypi.org/project/ctranslate2/4.8.2/), [source/API](https://github.com/SYSTRAN/faster-whisper) | MIT code. CPU int8, offline after model acquisition. CPU/RAM use still needs measurement; no MX330/CUDA usage. | Python API fits worker-based integration. Explicit multilingual tiny model download and local-files-only inference; model transfer and actual transcription remain unverified. |
| Speech model | **Selected initial smoke model:** `Systran/faster-whisper-tiny`, pinned revision | Multilingual (99 languages), MIT, 78.2 MB total; `model.bin` is 75.5 MB. [model card](https://huggingface.co/Systran/faster-whisper-tiny), [pinned revision](https://huggingface.co/Systran/faster-whisper-tiny/tree/d90ca5fe260221311c53c58e660288d3deb8d356) | Download once with network after user confirmation; then local/offline. | Appropriate small starting footprint for this 16 GB RAM/2 GB VRAM machine. Tiny accuracy is a smoke baseline, not an asserted production-quality result. Transfer stalled in this environment before the weight file completed. |
| Speech recognition, alternative | **Experimental:** whisper.cpp 1.9.4 | Active native C/C++ project, current Windows x64 release assets. Python is not required if invoked as native CLI; a Python wrapper adds little value initially. | MIT code; model artifact license/terms must be checked separately. Offline. CPU quantized model and CPU backend do not need NVIDIA CUDA. | Excellent CPU fallback and packaging isolation; subprocess protocol needs lifecycle/cancellation management. Test as alternative to faster-whisper when voice phase begins. No binaries/models now. |
| Speech recognition, alternative | **Deferred:** Vosk 0.3.75 source metadata / published Windows API wheel 0.3.45 | Project source setup metadata indicates 0.3.75 and generic `py3` Windows tags, but PyPI’s last Windows wheel page observed is 0.3.45 from 2022. Python 3.14 metadata does not prove its embedded native library is validated on 3.14. | Apache-2.0 API; each model license separate. Offline and CPU; small streaming models. | Suitable low-latency grammar-constrained comparison, but published wheel freshness is weak versus faster-whisper/whisper.cpp. Defer; only adopt after exact wheel and quality checks. |
| Speech recognition, Windows APIs | **Deferred:** Windows speech recognizer | Installed capabilities/languages and supported desktop APIs vary; no universal CPython package chain selected. | Local when a matching installed language/runtime exists; no separate model. Windows terms. | Could reduce model weight but availability/accuracy uncertainty. Do not rely on it as mandatory. |
| TTS | **Selected; installed optional:** Windows SAPI through pywin32 312 | Published `cp314-cp314-win_amd64` wheel; installed. Two SAPI voices enumerated on this machine. [PyPI wheel](https://pypi.org/project/pywin32/312/), [SAPI overview](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms723627(v=vs.85)) | PSF-licensed binding; Windows voices local/offline; no model/GPU. | Explicit Speak action runs on a worker thread. Voice output is not automatically triggered; audible output check remains. |
| Neural TTS | **Deferred:** Piper or active successor only after review | Original `rhasspy/piper` repo archived 2025-10-06; code package and individual voices have different licenses. | CPU-friendly offline options; voice models have separate terms; no GPU expected. | Do not select archived upstream or bundle a voice by assumption. Reassess active maintenance, license lineage and voice quality later. |
| Structured DB | **Selected:** Python stdlib `sqlite3` | Ships with CPython; SQLite library version depends on CPython build. Windows compatible, no third-party package. | No meaningful hardware burden; offline. SQLite is public domain. | Excellent for single-user tasks/config/metadata. Install nothing. Use migrations/transactions and verify SQLite runtime. |
| IANA timezone data | **Selected; installed:** `tzdata==2026.4` with stdlib `zoneinfo` | Python recommends a tzdata dependency for Windows because Windows typically lacks IANA database files; the package is a universal Python wheel. | Offline after install; Apache-2.0; current wheel is about 347.5 kB. | Required for DST-safe local task deadlines and IANA timezone IDs on this Windows machine. `ZoneInfo('Asia/Kathmandu')` failed before install and succeeds after. [Python zoneinfo docs](https://docs.python.org/3/library/zoneinfo.html), [tzdata on PyPI](https://pypi.org/project/tzdata/2026.4/). |
| Full-text search | **Selected and implemented:** SQLite FTS5 | FTS5 virtual table creation, migration and search have been exercised on the selected Python SQLite 3.50.4 build. | CPU/disk only; offline; SQLite public domain. | Used for local names/paths with BM25; it does not search file contents and is not a Windows Search replacement. No package required. |
| File indexing | **Selected and implemented:** `os.scandir` bounded background walker + SQLite metadata | Standard library and CPython 3.14 compatible; works on Windows. | I/O and metadata storage scale with configured roots; offline. | Transparent, cancellable between entries, batched writes, scoped reconciliation and explicit path exclusions. One synthetic 1,021-entry tree took 0.0726 s and a query took 0.000606 s; this is not a large-drive benchmark. |
| Incremental file changes | **Deferred:** periodic reconciliation first; `watchdog` as later dirty-root hint; USN as advanced option | `watchdog` maintained and uses `ReadDirectoryChangesW` on Windows. USN Journal requires NTFS-specific native handling. No essential Python 3.14 blocker for standard-library first phase. | Offline; watcher modest CPU, USN low ongoing I/O but more engineering/permission complexity. | Events can overflow/miss; reconciliation still required. Do not install watchdog until profiling proves need. USN is not the initial engine. |
| Windows Search API | **Experimental comparison only** | Windows-provided API/service; Python wrapper or COM interop would need proof. Its index coverage depends on Windows configuration. | Local/offline, no additional compute. | May offer faster preindexed scope but cannot guarantee user-selected coverage or identical rank/exclusion policy. Prototype only if walker performance is inadequate. |
| Global hotkey | **Selected and implemented:** Win32 `RegisterHotKey` behind a Qt/ctypes adapter | Windows User32 API; `ctypes` is stdlib. Adapter registers a configurable chord and receives `WM_HOTKEY` in Qt's native event loop. | Negligible; offline; OS API. | Default Ctrl+Space; conflict is logged and app remains usable. Manual shortcut conflict/restart check remains. |
| Global hotkey library alternative | **Rejected:** `keyboard` as default | Python library works on Windows but hooks global keyboard events, broader footprint than the needed API. | No GPU; offline; MIT. | Convenient but more permissions/privacy/edge-case surface than native RegisterHotKey. Could use only if native integration proves unworkable. |
| Startup | **Selected and implemented:** opt-in per-user Startup-folder VBScript | Uses `%APPDATA%` Startup folder and launches the current interpreter with `main.py`; no package or registry dependency. | Negligible; local; Windows shell behavior. | Disabled by default; opt in with `MYASSISTANT_START_WITH_WINDOWS=true`. Remove the app-owned script when disabled. Source checkout startup is implemented; packaged launch target needs adjustment during packaging. |
| Tray | **Selected and implemented:** `QSystemTrayIcon` from PySide6 | Built into selected Qt stack, no extra package. Windows 11-compatible subject to shell/notification-area settings. | Negligible; offline; Qt licensing terms. | Menu opens the launcher, checks reminders and exits. If no tray is available, closing the launcher exits instead of hiding invisibly. Manual desktop check remains. |
| Notifications | **Selected and implemented:** Qt tray messages for task reminders; native Windows toast deferred | Uses `QSystemTrayIcon.showMessage`; Windows may suppress or alter display. Actionable native toast integration has packaging/AppUserModelID considerations. | Negligible; local. | Reminder records are saved only when tray message delivery is available; polling occurs every 30 seconds and on startup. Native toast remains deferred. |
| Tests | **Selected; installed dev-only:** pytest 9.1.1 | MIT, requires Python >=3.10, universal `py3` wheel; lists Python 3.14 and Windows. | Low; offline. | Strong match and supports temp fixtures/mocks. Installed in `.venv`; 55 tests pass and one symlink test is skipped because host policy disallows symlink creation. |
| Packaging | **Recommended but not yet installed:** PyInstaller 6.22.3, one-folder first | Current release observed 2026-09-12; project states Python 3.8–3.15 and PySide6 support. Windows builds must be produced on Windows. | Build may need disk/time; resulting UI app runs offline. GPLv2+ with exception for non-free programs. | Practical first packager, but Qt plugins and future native speech libs need clean-machine smoke tests. Use in packaging phase, not now. |
| Packaging alternative | **Experimental:** Nuitka | Current documentation reports Python 3.14 support; native compiler/build tooling is required. Some Windows compiler paths vary by Python version. | Higher build complexity; no runtime AI requirement. | Compare if measurable size/startup/inspection benefits justify compiler. Not initial packager. |
| Optional AI/LLM | **Deferred:** deterministic command parser first; no provider/model chosen | Python 3.14 compatibility cannot be meaningfully pinned until model server/provider selected. | MX330 2 GB VRAM is a poor basis for a useful local LLM; CPU local inference would compete for 16 GB RAM and may be slow. Cloud requires network and explicit data policy. | Do not install now. Future local/cloud choices must return only allowlisted structured action proposals. No arbitrary shell execution. |
| CUDA / NVIDIA runtime | **Deferred:** no CUDA install; CPU default | MX330 Pascal CC 6.1; driver reports CUDA 13.0, but CUDA 13 toolkit removed architectures below Turing. CTranslate2 supports older CC in principle, but toolchain/runtime package compatibility is separate. | 2 GB VRAM is restrictive; 16 GB system RAM (user-provided) favors CPU small/int8 as a base. | GPU may help a tiny model with a deliberately compatible CUDA 12 build; unproven and not needed for app. Avoid CUDA toolkit install and do not advertise GPU support until measured. |

## 5. MX330 and speech workload analysis

The MX330 can be useful only as an optional accelerator for small, carefully selected speech models. Its 2 GB dedicated memory is shared with display/other graphics use and must also cover runtime buffers and activations. Quantized weights reduce model memory but do not eliminate working memory. Transcription is bursty, so the modest GPU may not save enough time to justify carrying CUDA libraries in the desktop package.

The more important generation issue is architecture support. MX330 uses Pascal-class GPU architecture (compute capability 6.1). CTranslate2 4.8.2 documentation lists NVIDIA CC ≥3.5 for its prebuilt binaries and lists INT8 GPU support at CC 6.1, but the binary must still be linked against a toolkit/runtime that supports that GPU. CUDA 13 explicitly removes Maxwell/Pascal/Volta support. CTranslate2 install docs name CUDA 12.x for Windows/Linux GPU wheels. whisper.cpp’s CUDA build configuration explicitly includes Pascal `61-virtual` only while toolkit is earlier than CUDA 13. Therefore:

1. **CPU is the default and support guarantee.** Start with CPU int8 in a benchmark, using an appropriately small Whisper model or whisper.cpp quantized model.
2. **Do not assume the reported CUDA 13.0 support line means MX330-capable inference.** It describes the installed driver’s toolkit compatibility, not the toolkit’s supported device architecture.
3. **GPU is an experimental branch.** If CPU results warrant it, investigate a CUDA 12.x-compatible CTranslate2 or whisper.cpp build with sm_61 support and a tested driver/library set. Do not downgrade the NVIDIA driver; do not install several conflicting CUDA/cuDNN stacks.
4. **No large local LLM on this GPU.** A 2 GB VRAM budget is not a sound target for interactive general-purpose local LLMs. The command architecture must work without any LLM.

The precise GPU compute capability should be confirmed with a CUDA runtime query or authoritative device utility during hardware setup before attempting builds. The Pascal classification follows published GPU references and the CTranslate2/whisper.cpp architecture tables; record any contradictory device query before changing this conclusion.

## 6. Whole-stack fit and dependency policy

### Lean runtime dependencies

- PySide6 for desktop GUI.
- Standard-library `sqlite3`, `ctypes`, `pathlib`, `os.scandir`, `logging`, `zoneinfo`, `subprocess` (with argument arrays), and `shutil` where needed.
- One selected speech backend only after its phase and benchmark.
- No always-running database service, browser runtime, GPU framework, cloud client, or model server in baseline.

### Python 3.14 compatibility risks to track

- `abi3` GUI wheel and current `cp314` CT2 wheel evidence are good, but binary wheel existence does not prove runtime combinations or PyInstaller collection.
- The Vosk Python source metadata (`>=3`) is permissive but its last observed Windows binary wheel is old; metadata alone is not validation.
- Audio device libraries/microphone wrappers have not been selected and may be the remaining Python 3.14 risk. Choose only after checking their current Windows cp314 wheels or a viable system API route.
- Avoid optional C extensions with only cp313 wheels. If a required microphone/audio library blocks 3.14 and has no reasonable OS-API alternative, repeat the comparison against current 3.13.16 before changing the baseline.
- Free-threaded 3.14t is explicitly out of scope for initial builds. Qt, audio, inference and frozen-app support must be considered as a unified chain; do not infer compatibility from CPython version metadata alone.

## 7. License and distribution notes

License suitability must be reviewed for the final distribution format, not inferred from package names:

- Qt/PySide6: comply with LGPLv3/GPLv3 obligations or obtain a commercial Qt license; preserve notices and provide relinkability/source obligations when using LGPL route as applicable.
- faster-whisper and whisper.cpp code licensing does not settle Whisper model weights/data terms. Review each model source/version before downloading or redistributing.
- CTranslate2 has its own project license and native binary notices; include all third-party notices in packaged output.
- Vosk API is Apache-2.0 in current source metadata; model licenses differ.
- Pytest is dev-only MIT; PyInstaller is GPLv2-or-later with a special distribution exception; still retain notices for redistributed build tooling/binaries as required.
- Windows voices are subject to Windows platform/voice terms. Piper’s individual voice licenses vary; original upstream archive state adds maintenance risk.
- Local/cloud LLM weights and APIs carry separate model/provider terms. Keep AI deferred until model, usage and data handling are explicit.

This is an engineering compatibility screen, not legal advice. Before release, generate a dependency/license inventory and review actual transitive components.

## 8. Install timing

| Phase | Add only when needed |
|---|---|
| Audit baseline (before environment setup) | **Nothing was installed as part of the audit.** No model weights, CUDA toolkit, audio packages or executable. |
| Phase 1 | CPython 3.14.8 project environment; pytest and selected formatting/lint tooling after policy selection. Run compatibility smoke checks only when Phase 1 begins. |
| Phase 3 | PySide6 for the desktop launcher; standard-library SQLite first. |
| Phase 4/5/6/7 | Prefer stdlib, Qt and thin OS adapters; add packages only for a demonstrated gap. Watchdog only after indexing measurements. |
| Phase 6 | `tzdata` with stdlib `zoneinfo` for IANA rules on Windows; current pin 2026.4. |
| Phase 8 | Optional speech extra (`sounddevice`, `faster-whisper`, Windows `pywin32`) installed; Whisper tiny model remains a user-confirmed asset download. |
| Speech phase | Benchmark faster-whisper CPU/int8 against whisper.cpp CPU using small models; download only chosen model after license/storage review. GPU remains optional. |
| TTS phase | Prototype installed Windows voice API; add a neural engine only if voice quality justifies its maintenance and model costs. |
| AI phase | Select local/cloud option only after concrete use cases and data-flow review. |
| Packaging phase | Pin PyInstaller and hooks, then prove one-folder build. No PyInstaller dependency in runtime environment unless build workflow needs it. |

## 9. Compatibility test gates for later (not run now)

1. Standard CPython 3.14.8 x64 environment is selected and reports expected ABI.
2. PySide6 imports, creates a window and exits cleanly on Windows build 26100; the current offscreen UI tests pass, but an interactive desktop check remains.
3. SQLite 3.50.4 FTS5 migration, triggers and query were exercised by tests.
4. CTranslate2 import and CPU int8 transcription work with a small, properly licensed local sample/model (speech phase only).
5. If GPU is investigated, collect compute capability, verify CUDA 12 runtime/toolkit and cuDNN (if required by selected build), check supported compute types, measure VRAM peak and compare CPU latency. No CUDA 13 inference assumption.
6. pytest 9.1.1 runs successfully under 3.14.8; the current suite has 62 passing tests and one host-policy skip.
7. PyInstaller one-folder app launches from outside checkout in a clean standard-user Windows environment, with Qt plugin collection confirmed.
8. If any essential package fails specifically on CPython 3.14, reproduce under 3.13.16 and update ADR-012 with evidence before changing baseline.

These are future validation steps. **No installations or tests were performed for this evaluation.**

## FINAL RECOMMENDED STACK

| Area | Recommendation | Audit status | Install timing |
|---|---|---|---|
| Runtime | Standard CPython 3.14.8 x64 (GIL build) | **Selected** | Phase 1, when environment setup is authorized |
| GUI | PySide6 6.11.2 | **Selected** | Installed in `.venv`; GUI implementation phase |
| Search/storage | `os.scandir`, SQLite and SQLite FTS5 | **Selected and implemented** | Standard library; FTS5 confirmed in SQLite 3.50.4 |
| Timezone rules | stdlib `zoneinfo` + tzdata 2026.4 | **Selected and installed** | Runtime package; required on Windows for IANA timezone data |
| Hotkey | Win32 `RegisterHotKey` behind `ctypes`/Qt adapter | **Selected and implemented** | Phase 7; interactive chord/conflict check remains |
| Speech | faster-whisper/CTranslate2 with multilingual tiny model, CPU int8; whisper.cpp remains an alternative | **Selected initial implementation; local model transfer/inference not yet verified** | Optional packages installed; model requires user-confirmed download |
| TTS | Installed Windows voices through SAPI/pywin32 | **Selected and implemented** | Optional packages installed; audible smoke check remains |
| Tasks | SQLite service, timezone-aware deadlines and Qt tray reminders | **Selected and implemented** | Phase 6/7; tray delivery needs desktop check |
| Tray and notifications | PySide6 `QSystemTrayIcon` and `showMessage` | **Selected and implemented** | Phase 7; Windows notification settings may suppress messages |
| Startup | Opt-in per-user Startup-folder script | **Selected and implemented** | Off unless `MYASSISTANT_START_WITH_WINDOWS=true`; packaged path needs later adaptation |
| Tests | pytest 9.1.1, development-only | **Selected** | Installed in `.venv`; 62 pass, 1 symlink test skipped by host policy |
| Packaging | PyInstaller 6.22.3, one-folder prototype | **Recommended but not yet installed** | Packaging phase |
| GPU / CUDA | CPU inference default; MX330 GPU path only if a small-model benchmark justifies CUDA 12/sm_61 proof | **Experimental** | No CUDA installation planned |
| Local/cloud LLM | No model/provider selected; typed allowlisted proposals only if later justified | **Deferred** | AI phase, after privacy and workload decision |

### NEXT ACTIONS

1. Keep experimental speech, model, CUDA and LLM packages deferred.
2. Perform an interactive Windows smoke check of the Phase 3/4/5 launcher, including focus, app/file/folder search, selected result opening, hide/reopen and clean exit.
3. Measure scan and query performance on representative user-selected roots before expanding the indexing scope.
4. Defer microphone/audio binding selection until a real capture requirement exists; compare exact Windows wheels/APIs before changing the Python baseline.
5. During the voice phase, measure CPU int8 first on MX330-class hardware; pursue GPU only with proven Pascal support and a clear benefit over CPU.

## 10. Post-audit environment update

After the audit, the project declared PySide6 6.11.2 and tzdata 2026.4, then installed the editable package and development extra. Phase 7 added native Windows shell integration. Phase 8 added the optional `voice` extra: faster-whisper 1.2.1, CTranslate2 4.8.2, sounddevice 0.5.6, pywin32 312 and their transitive dependencies. Imports are verified under standard CPython 3.14.8 x64. The machine reports an internal microphone and two SAPI voices. The voice software implementation is complete. The pinned tiny model download was attempted with both Xet and the documented non-Xet transport, but the 75.5 MB `model.bin` transfer made no progress; a follow-up HTTP HEAD request timed out. No model weights or voice recording are present. The full suite has 62 passing tests and one symlink skip; `pip check` is clean. Audio capture, actual model inference and audible TTS remain manual acceptance checks.

## 11. Sources reviewed

Sources checked on 2026-10-02; package status can change.

- Python: [active releases/downloads](https://www.python.org/downloads/), [3.14.8 release](https://www.python.org/downloads/release/python-3148/), [3.13.16 release](https://www.python.org/downloads/release/python-31316/).
- PySide6: [PyPI wheel files](https://pypi.org/project/PySide6/), [Qt for Python docs](https://doc.qt.io/qtforpython-6/), [Qt 6.11 release](https://www.qt.io/blog/qt-for-python-release-6.11-is-out).
- Speech: [faster-whisper PyPI](https://pypi.org/project/faster-whisper/), [faster-whisper source/CUDA notes](https://github.com/SYSTRAN/faster-whisper), [CTranslate2 wheels](https://pypi.org/project/ctranslate2/), [CTranslate2 installation](https://opennmt.net/CTranslate2/installation.html), [hardware support](https://opennmt.net/CTranslate2/hardware_support.html), [quantization](https://opennmt.net/CTranslate2/quantization.html), [whisper.cpp release](https://github.com/ggml-org/whisper.cpp/releases), [whisper.cpp CUDA architecture policy](https://github.com/ggml-org/whisper.cpp/blob/master/ggml/src/ggml-cuda/CMakeLists.txt), [Vosk release history](https://github.com/alphacep/vosk-api/releases), [Vosk API package metadata](https://github.com/alphacep/vosk-api/blob/master/python/setup.py).
- CUDA: [CUDA 13.0 release notes](https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html), [NVIDIA GPU compute-capability reference](https://developer.nvidia.com/cuda/gpus).
- TTS/Windows integration: [Windows speech synthesis](https://learn.microsoft.com/en-us/uwp/api/windows.media.speechsynthesis), [RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey), [USN journal query](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_query_usn_journal).
- Search/database: [SQLite FTS5](https://www.sqlite.org/fts5.html), [watchdog Windows observer implementation](https://github.com/gorakhargosh/watchdog/blob/master/src/watchdog/observers/read_directory_changes.py).
- Tests/packaging: [pytest PyPI](https://pypi.org/project/pytest/), [PyInstaller project](https://github.com/pyinstaller/pyinstaller), [Nuitka project](https://github.com/Nuitka/Nuitka).
- TTS alternative: [archived Piper project and release status](https://github.com/rhasspy/piper/releases), [voice catalog](https://github.com/rhasspy/piper/blob/master/VOICES.md).
