using AiAgent.Desktop.Core.Services;
using AiAgent.Desktop.ViewModels;
using Avalonia.Controls;

namespace AiAgent.Desktop.Services;

public static class DesktopBootstrapper
{
    public static MainWindowViewModel CreateMainWindowViewModel(Window window)
    {
        var infrastructureRoot = InfrastructureLocator.Find();
        var settingsStore = new DesktopSettingsStore();
        var settingsDirectory = Path.GetDirectoryName(settingsStore.SettingsPath)
            ?? throw new InvalidOperationException("Desktop settings directory is unavailable.");
        var overridePath = Path.Combine(settingsDirectory, "compose.projects.json");
        var processRunner = new ProcessRunner();
        var dockerService = new DockerComposeService(
            processRunner,
            new ComposeContext(infrastructureRoot, overridePath));
        var httpClient = new HttpClient(new SocketsHttpHandler { UseProxy = false })
        {
            BaseAddress = new Uri("http://127.0.0.1:8765"),
            Timeout = Timeout.InfiniteTimeSpan,
        };
        var apiClient = new AgentApiClient(httpClient);
        var mountService = new ProjectMountService(new HostProjectPathGuard());
        var overrideWriter = new ComposeOverrideWriter();
        var coordinator = new ProjectRegistrationCoordinator(
            mountService,
            settingsStore,
            overrideWriter,
            dockerService,
            apiClient);

        return new MainWindowViewModel(
            settingsStore,
            overrideWriter,
            dockerService,
            apiClient,
            coordinator,
            new AvaloniaFolderPickerService(window));
    }
}
