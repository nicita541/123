using AiAgent.Desktop.Core.Services;

namespace AiAgent.Desktop.Tests;

public sealed class DockerComposeServiceTests
{
    [Fact]
    public async Task StartAsync_UsesBaseAndGeneratedOverrideWithoutShell()
    {
        using var root = new TemporaryDirectory();
        var compose = Path.Combine(root.Path, "docker-compose.yml");
        var composeOverride = Path.Combine(root.Path, "compose.projects.json");
        await File.WriteAllTextAsync(compose, "services: {}", CancellationToken.None);
        await File.WriteAllTextAsync(composeOverride, "{\"services\":{}}", CancellationToken.None);
        var runner = new RecordingProcessRunner();
        var service = new DockerComposeService(runner, new ComposeContext(root.Path, composeOverride));

        await service.StartAsync(cancellationToken: CancellationToken.None);

        var spec = Assert.Single(runner.Specs);
        Assert.Equal("docker", spec.FileName);
        Assert.Equal(root.Path, spec.WorkingDirectory);
        Assert.Equal(
            [
                "compose", "-f", compose, "-f", composeOverride,
                "--project-directory", root.Path, "up", "-d", "--build",
            ],
            spec.Arguments);
    }

    [Fact]
    public async Task PullModelAsync_PassesModelAsEnvironmentValue()
    {
        using var root = new TemporaryDirectory();
        await File.WriteAllTextAsync(
            Path.Combine(root.Path, "docker-compose.yml"),
            "services: {}",
            CancellationToken.None);
        var runner = new RecordingProcessRunner();
        var service = new DockerComposeService(
            runner,
            new ComposeContext(root.Path, Path.Combine(root.Path, "missing.json")));

        await service.PullModelAsync("qwen3:8b", cancellationToken: CancellationToken.None);

        var spec = Assert.Single(runner.Specs);
        Assert.Equal("qwen3:8b", spec.Environment!["OLLAMA_MODEL"]);
        Assert.Equal(["run", "--rm", "model-init"], spec.Arguments.TakeLast(3));
    }

    [Fact]
    public async Task GetModelInitStateAsync_ParsesRunningComposeService()
    {
        using var root = new TemporaryDirectory();
        await File.WriteAllTextAsync(
            Path.Combine(root.Path, "docker-compose.yml"),
            "services: {}",
            CancellationToken.None);
        var runner = new RecordingProcessRunner(
            "[{\"Service\":\"model-init\",\"State\":\"running\",\"ExitCode\":0}]");
        var service = new DockerComposeService(
            runner,
            new ComposeContext(root.Path, Path.Combine(root.Path, "missing.json")));

        var state = await service.GetModelInitStateAsync(CancellationToken.None);

        Assert.True(state.IsRunning);
        Assert.False(state.HasFailed);
    }

    private sealed class RecordingProcessRunner(string output = "ok") : IProcessRunner
    {
        public List<ProcessSpec> Specs { get; } = [];

        public Task<ProcessResult> RunAsync(
            ProcessSpec spec,
            IProgress<string>? progress = null,
            CancellationToken cancellationToken = default)
        {
            Specs.Add(spec);
            return Task.FromResult(new ProcessResult(0, output));
        }
    }
}
