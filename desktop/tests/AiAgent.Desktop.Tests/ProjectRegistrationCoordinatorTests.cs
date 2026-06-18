using System.Net;
using System.Text;
using AiAgent.Desktop.Core.Models;
using AiAgent.Desktop.Core.Services;

namespace AiAgent.Desktop.Tests;

public sealed class ProjectRegistrationCoordinatorTests
{
    [Fact]
    public async Task RegisterAsync_WritesMountStartsComposeAndPersistsBackendId()
    {
        using var root = new TemporaryDirectory();
        var projectPath = Directory.CreateDirectory(Path.Combine(root.Path, "todo")).FullName;
        var composePath = Path.Combine(root.Path, "docker-compose.yml");
        var overridePath = Path.Combine(root.Path, "compose.projects.json");
        var settingsPath = Path.Combine(root.Path, "settings.json");
        await File.WriteAllTextAsync(composePath, "services: {}", CancellationToken.None);

        var processRunner = new RecordingProcessRunner();
        var docker = new DockerComposeService(
            processRunner,
            new ComposeContext(root.Path, overridePath));
        using var http = new HttpClient(new StubHandler(request =>
        {
            var body = request.RequestUri!.AbsolutePath == "/health"
                ? "{\"status\":\"ok\"}"
                : """
                  {
                    "id":"backend_project",
                    "name":"Todo",
                    "root_path":"/projects/project_unused",
                    "mount_id":"project_unused",
                    "host_path":"F:\\1",
                    "container_path":"/projects/project_unused",
                    "is_active":true,
                    "last_task_title":null
                  }
                  """;
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(body, Encoding.UTF8, "application/json"),
            });
        }))
        {
            BaseAddress = new Uri("http://127.0.0.1:8765"),
        };
        var settingsStore = new DesktopSettingsStore(settingsPath);
        var coordinator = new ProjectRegistrationCoordinator(
            new ProjectMountService(new HostProjectPathGuard(Path.Combine(root.Path, "home"), [])),
            settingsStore,
            new ComposeOverrideWriter(),
            docker,
            new AgentApiClient(http));
        var settings = new DesktopSettings { InfrastructureRoot = root.Path };

        var project = await coordinator.RegisterAsync(
            settings,
            projectPath,
            "Todo",
            cancellationToken: CancellationToken.None);

        Assert.Equal("backend_project", project.ProjectId);
        Assert.True(File.Exists(overridePath));
        Assert.Single(processRunner.Specs);
        var restored = await settingsStore.LoadAsync(CancellationToken.None);
        Assert.Equal("backend_project", Assert.Single(restored.Projects).ProjectId);
    }

    private sealed class RecordingProcessRunner : IProcessRunner
    {
        public List<ProcessSpec> Specs { get; } = [];

        public Task<ProcessResult> RunAsync(
            ProcessSpec spec,
            IProgress<string>? progress = null,
            CancellationToken cancellationToken = default)
        {
            Specs.Add(spec);
            return Task.FromResult(new ProcessResult(0, "ok"));
        }
    }

    private sealed class StubHandler(Func<HttpRequestMessage, Task<HttpResponseMessage>> responder)
        : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken) => responder(request);
    }
}
