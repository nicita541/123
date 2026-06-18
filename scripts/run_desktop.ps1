param(
    [string]$Project = (Get-Location).Path,
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Virtual environment not found. Run scripts\install_desktop_deps.ps1 first."
}

Set-Location $repo
& $python -m complex_agent.main desktop --project $Project --host $HostAddress --port $Port
