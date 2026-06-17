Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = "F:\aiAgent"
$project = "F:\1"

Set-Location $repo
& ".\.venv\Scripts\python.exe" -m complex_agent.main desktop --project $project
