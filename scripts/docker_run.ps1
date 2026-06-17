param(
    [string]$Workspace = "F:\1",
    [string]$OllamaBaseUrl = "http://host.docker.internal:11434",
    [string]$OllamaModel = "qwen2.5-coder:7b-instruct"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$env:AGENT_WORKSPACE = $Workspace
$env:OLLAMA_BASE_URL = $OllamaBaseUrl
$env:OLLAMA_MODEL = $OllamaModel

docker compose up --build agent-app
