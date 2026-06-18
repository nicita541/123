using System.Security.Cryptography;
using System.Text;
using AiAgent.Desktop.Core.Models;

namespace AiAgent.Desktop.Core.Services;

public sealed class ProjectMountService(HostProjectPathGuard pathGuard)
{
    public ProjectMount Create(string hostPath, string? name = null)
    {
        var normalized = pathGuard.RequireAllowed(hostPath);
        var mountId = CreateMountId(normalized);
        return new ProjectMount
        {
            MountId = mountId,
            Name = string.IsNullOrWhiteSpace(name) ? Path.GetFileName(normalized) : name.Trim(),
            HostPath = normalized,
            ContainerPath = $"/projects/{mountId}",
        };
    }

    public static string CreateMountId(string normalizedHostPath)
    {
        var canonical = HostProjectPathGuard.Normalize(normalizedHostPath).ToUpperInvariant();
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(canonical));
        return $"project_{Convert.ToHexString(hash)[..16].ToLowerInvariant()}";
    }

    public static ProjectMount Upsert(DesktopSettings settings, ProjectMount project)
    {
        var existing = settings.Projects.FirstOrDefault(
            item => string.Equals(item.HostPath, project.HostPath, StringComparison.OrdinalIgnoreCase));
        if (existing is not null)
        {
            existing.Name = project.Name;
            existing.LastOpenedAt = DateTimeOffset.UtcNow;
            return existing;
        }

        settings.Projects.Add(project);
        return project;
    }
}
