$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project environment not found. Create .venv and install .[dev,voice,build] first."
}

Push-Location $projectRoot
try {
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --name MyAssistant `
        --collect-all faster_whisper `
        --collect-all ctranslate2 `
        --collect-all av `
        --collect-all onnxruntime `
        --collect-all sounddevice `
        --hidden-import pythoncom `
        --hidden-import pywintypes `
        --hidden-import win32timezone `
        main.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
