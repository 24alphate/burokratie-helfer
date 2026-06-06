# Local dev server — ALWAYS runs on backend/.venv so `anthropic` (and the rest
# of requirements.txt) is guaranteed present. Avoids the footgun of a PATH
# `uvicorn` resolving to a global Python that lacks `anthropic`, which makes
# translation silently fall back to German and scanning fail.
#
# Usage (from the backend/ folder):  ./run-dev.ps1
$ErrorActionPreference = "Stop"
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Error "backend/.venv not found. Create it: python -m venv .venv ; .\.venv\Scripts\python -m pip install -r requirements.txt"
  exit 1
}
& $py -m uvicorn app.main:app --reload --port 8000
