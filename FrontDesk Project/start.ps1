# FrontDesk AI local starter (Windows PowerShell).
# From "FrontDesk Project":  .\start.ps1
# If PowerShell blocks the script, run once:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# or:  powershell -ExecutionPolicy Bypass -File .\start.ps1
# See HowToSetup.md, section A.
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (Test-Path -LiteralPath ".\.venv\Scripts\Activate.ps1") {
    . ".\.venv\Scripts\Activate.ps1"
} elseif (Test-Path -LiteralPath ".\venv\Scripts\Activate.ps1") {
    . ".\venv\Scripts\Activate.ps1"
} else {
    Write-Error "No virtual environment found in this folder. Create one first (see HowToSetup.md, section A): py -3.12 -m venv .venv ; .\.venv\Scripts\Activate.ps1"
    exit 1
}

python -c "import uvicorn, fastapi" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Dependencies are missing. With the venv activated, run: python -m pip install --require-hashes -r requirements.lock"
    exit 1
}

if (-not $env:PORT -or $env:PORT -eq "") { $env:PORT = "10000" }
Write-Host "Starting FrontDesk AI on http://127.0.0.1:$($env:PORT)  (Ctrl+C to stop)"
python -m uvicorn main:app --host 0.0.0.0 --port $env:PORT
