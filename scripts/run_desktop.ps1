param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:AIAGENT_HOME = $repo

dotnet run --project desktop/src/AiAgent.Desktop/AiAgent.Desktop.csproj --configuration $Configuration
