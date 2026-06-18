param(
    [string]$Workspace = (Join-Path (Split-Path -Parent $PSScriptRoot) "examples\docker_workspace"),
    [string]$OllamaBaseUrl = "http://host.docker.internal:11434",
    [string]$OllamaModel = "qwen2.5-coder:7b-instruct"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$resolved = [System.IO.Path]::GetFullPath($Workspace)
$root = [System.IO.Path]::GetPathRoot($resolved)
$home = [System.IO.Path]::GetFullPath($HOME)
$blocked = @(
    $root,
    $home,
    [Environment]::GetFolderPath("Windows"),
    [Environment]::GetFolderPath("ProgramFiles"),
    [Environment]::GetFolderPath("ProgramFilesX86")
) | Where-Object { $_ }

if ($blocked | Where-Object { [System.IO.Path]::GetFullPath($_).TrimEnd('\') -eq $resolved.TrimEnd('\') }) {
    throw "Choose a specific project folder, not an entire drive, home, or system directory."
}
if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
    New-Item -ItemType Directory -Path $resolved | Out-Null
}

Set-Location $repo
$env:AGENT_WORKSPACE = $resolved
$env:OLLAMA_BASE_URL = $OllamaBaseUrl
$env:OLLAMA_MODEL = $OllamaModel
docker compose up --build agent-app
