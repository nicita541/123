using AiAgent.Desktop.Core.Models;

namespace AiAgent.Desktop.Core.Services;

public sealed class ProjectRegistrationCoordinator(
    ProjectMountService mountService,
    DesktopSettingsStore settingsStore,
    ComposeOverrideWriter overrideWriter,
    DockerComposeService dockerService,
    AgentApiClient apiClient)
{
    public async Task<ProjectMount> RegisterAsync(
        DesktopSettings settings,
        string hostPath,
        string? name = null,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var candidate = mountService.Create(hostPath, name);
        var project = ProjectMountService.Upsert(settings, candidate);
        await settingsStore.SaveAsync(settings, cancellationToken);
        await overrideWriter.WriteAsync(
            dockerService.Context.OverrideFile,
            settings.Projects,
            cancellationToken);

        progress?.Report("Applying project mount and starting Docker services...");
        await dockerService.StartAsync(progress, cancellationToken);
        await apiClient.WaitForHealthAsync(TimeSpan.FromMinutes(2), progress, cancellationToken);

        progress?.Report("Registering the container project path with the backend...");
        var registered = await apiClient.RegisterProjectAsync(project, cancellationToken);
        project.ProjectId = registered.Id;
        project.LastOpenedAt = DateTimeOffset.UtcNow;
        await settingsStore.SaveAsync(settings, cancellationToken);
        return project;
    }

    public async Task OpenAsync(
        DesktopSettings settings,
        ProjectMount project,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(project.ProjectId))
        {
            throw new InvalidOperationException("The project is not registered with the backend.");
        }

        await apiClient.OpenProjectAsync(project.ProjectId, cancellationToken);
        project.LastOpenedAt = DateTimeOffset.UtcNow;
        await settingsStore.SaveAsync(settings, cancellationToken);
    }
}
