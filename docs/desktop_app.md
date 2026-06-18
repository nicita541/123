# Avalonia Desktop Application

The primary desktop is a native C# Avalonia 12 application targeting .NET 10:

    dotnet restore desktop/AiAgent.Desktop.sln
    dotnet run --project desktop/src/AiAgent.Desktop/AiAgent.Desktop.csproj -c Release

scripts\run_desktop.ps1 sets AIAGENT_HOME and runs the same project.

## Responsibilities

- Docker availability and Compose start/stop/status.
- Non-blocking model pull with progress and cancellation.
- Backend/Ollama/model health.
- Native Windows project folder selection and host path safety checks.
- Persistent project mount registry under %LOCALAPPDATA%\AiAgent.
- Projects, task history, plan, diff, approval, execution, verification, report, and rollback.

The app is MVVM and has no WebView. AiAgent.Desktop.Core contains infrastructure and API
logic so UI code remains testable and replaceable.

For a published executable outside the repository:

    $env:AIAGENT_HOME = "F:\aiAgent"
    desktop\src\AiAgent.Desktop\bin\Release\net10.0\AiAgent.Desktop.exe
