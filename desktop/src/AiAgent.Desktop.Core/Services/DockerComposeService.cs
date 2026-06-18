using System.Text.Json;

namespace AiAgent.Desktop.Core.Services;

public sealed record ComposeContext(string InfrastructureRoot, string OverrideFile)
{
    public string ComposeFile => Path.Combine(InfrastructureRoot, "docker-compose.yml");
}

public sealed record ModelInitState(string State, int? ExitCode)
{
    public bool IsRunning => string.Equals(State, "running", StringComparison.OrdinalIgnoreCase);

    public bool HasFailed => ExitCode is > 0;
}

public sealed class DockerComposeService(IProcessRunner processRunner, ComposeContext context)
{
    public ComposeContext Context { get; } = context;

    public Task<ProcessResult> CheckDockerAsync(CancellationToken cancellationToken = default) =>
        RunAsync(
            ["version", "--format", "{{.Server.Version}}"],
            "Docker check",
            cancellationToken: cancellationToken,
            compose: false);

    public Task<ProcessResult> StartAsync(
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default) =>
        RunAsync(["up", "-d", "--build"], "Docker services start", progress, cancellationToken);

    public Task<ProcessResult> StopAsync(
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default) =>
        RunAsync(["stop"], "Docker services stop", progress, cancellationToken);

    public Task<ProcessResult> RecreateBackendAsync(
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default) =>
        RunAsync(
            ["up", "-d", "--build", "--force-recreate", "backend"],
            "Backend recreate",
            progress,
            cancellationToken);

    public Task<ProcessResult> StatusAsync(CancellationToken cancellationToken = default) =>
        RunAsync(["ps", "-a", "--format", "json"], "Docker services status", cancellationToken: cancellationToken);

    public async Task<ModelInitState> GetModelInitStateAsync(
        CancellationToken cancellationToken = default)
    {
        var result = await RunAsync(
            ["ps", "-a", "--format", "json", "model-init"],
            "Model init status",
            cancellationToken: cancellationToken);
        if (string.IsNullOrWhiteSpace(result.Output))
        {
            return new ModelInitState("not-created", null);
        }

        try
        {
            using var document = JsonDocument.Parse(result.Output);
            if (document.RootElement.ValueKind == JsonValueKind.Array
                && document.RootElement.GetArrayLength() == 0)
            {
                return new ModelInitState("not-created", null);
            }

            var item = document.RootElement.ValueKind == JsonValueKind.Array
                ? document.RootElement.EnumerateArray().FirstOrDefault()
                : document.RootElement;
            var state = item.TryGetProperty("State", out var stateElement)
                ? stateElement.GetString() ?? "unknown"
                : "unknown";
            int? exitCode = item.TryGetProperty("ExitCode", out var exitCodeElement)
                && exitCodeElement.TryGetInt32(out var parsedExitCode)
                ? parsedExitCode
                : null;
            return new ModelInitState(state, exitCode);
        }
        catch (JsonException)
        {
            return new ModelInitState("unknown", null);
        }
    }

    public Task<ProcessResult> PullModelAsync(
        string model,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(model))
        {
            throw new ArgumentException("Choose an Ollama model.", nameof(model));
        }

        return RunAsync(
            ["run", "--rm", "model-init"],
            "Ollama model pull",
            progress,
            cancellationToken,
            new Dictionary<string, string> { ["OLLAMA_MODEL"] = model.Trim() });
    }

    public ProcessSpec CreateComposeInvocation(
        IReadOnlyList<string> command,
        IReadOnlyDictionary<string, string>? environment = null)
    {
        if (!File.Exists(Context.ComposeFile))
        {
            throw new DockerOperationException($"Compose file was not found: {Context.ComposeFile}");
        }

        var arguments = new List<string>
        {
            "compose",
            "-f",
            Context.ComposeFile,
        };
        if (File.Exists(Context.OverrideFile))
        {
            arguments.AddRange(["-f", Context.OverrideFile]);
        }

        arguments.AddRange(["--project-directory", Context.InfrastructureRoot]);
        arguments.AddRange(command);
        return new ProcessSpec("docker", arguments, Context.InfrastructureRoot, environment);
    }

    private async Task<ProcessResult> RunAsync(
        IReadOnlyList<string> command,
        string operation,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default,
        IReadOnlyDictionary<string, string>? environment = null,
        bool compose = true)
    {
        var spec = compose
            ? CreateComposeInvocation(command, environment)
            : new ProcessSpec("docker", command, Context.InfrastructureRoot, environment);
        var result = await processRunner.RunAsync(spec, progress, cancellationToken);
        result.EnsureSuccess(operation);
        return result;
    }
}
