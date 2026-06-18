Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    python -m venv (Join-Path $repo ".venv")
}

Set-Location $repo
& $python -m pip install -e ".[desktop,dev]"
