param(
    [string]$ProjectsRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) "examples"),
    [string]$DefaultProject = "docker_workspace",
    [string]$OllamaModel = "qwen2.5-coder:1.5b"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$resolved = [System.IO.Path]::GetFullPath($ProjectsRoot)
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
    throw "Choose a specific projects parent folder, not an entire drive, home, or system directory."
}
if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
    New-Item -ItemType Directory -Path $resolved | Out-Null
}

Set-Location $repo
$defaultPath = [System.IO.Path]::GetFullPath((Join-Path $resolved $DefaultProject))
if (-not $defaultPath.StartsWith($resolved.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "DefaultProject must resolve below ProjectsRoot."
}
if (-not (Test-Path -LiteralPath $defaultPath -PathType Container)) {
    New-Item -ItemType Directory -Path $defaultPath | Out-Null
}

$relativeDefault = $defaultPath.Substring($resolved.TrimEnd('\').Length).TrimStart('\').Replace('\', '/')
$env:AGENT_PROJECTS_ROOT = $resolved
$env:AGENT_DEFAULT_PROJECT = "/projects/$relativeDefault"
$env:OLLAMA_MODEL = $OllamaModel
docker compose up --build
