Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

dotnet restore desktop/AiAgent.Desktop.sln
if ($LASTEXITCODE -ne 0) {
    throw "Desktop restore failed. Install the .NET 10 SDK and try again."
}
