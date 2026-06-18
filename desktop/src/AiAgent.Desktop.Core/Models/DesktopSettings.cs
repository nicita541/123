namespace AiAgent.Desktop.Core.Models;

public sealed class DesktopSettings
{
    public string InfrastructureRoot { get; set; } = string.Empty;

    public string BackendBaseUrl { get; set; } = "http://127.0.0.1:8765";

    public string SelectedModel { get; set; } = "qwen2.5-coder:1.5b";

    public List<ProjectMount> Projects { get; set; } = [];
}

public sealed class ProjectMount
{
    public required string MountId { get; init; }

    public string? ProjectId { get; set; }

    public required string Name { get; set; }

    public required string HostPath { get; init; }

    public required string ContainerPath { get; init; }

    public DateTimeOffset LastOpenedAt { get; set; } = DateTimeOffset.UtcNow;
}
