using System.Text.Json;
using AiAgent.Desktop.Core.Models;

namespace AiAgent.Desktop.Core.Services;

public sealed class ComposeOverrideWriter
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public async Task WriteAsync(
        string path,
        IEnumerable<ProjectMount> projects,
        CancellationToken cancellationToken = default)
    {
        var volumes = projects
            .OrderBy(static project => project.MountId, StringComparer.Ordinal)
            .Select(project => new Dictionary<string, object>
            {
                ["type"] = "bind",
                ["source"] = project.HostPath,
                ["target"] = project.ContainerPath,
                ["read_only"] = false,
            })
            .ToArray();
        var backend = volumes.Length == 0
            ? new Dictionary<string, object>()
            : new Dictionary<string, object> { ["volumes"] = volumes };
        var document = new Dictionary<string, object>
        {
            ["services"] = new Dictionary<string, object> { ["backend"] = backend },
        };

        var directory = Path.GetDirectoryName(path)
            ?? throw new InvalidOperationException("Compose override path has no parent directory.");
        Directory.CreateDirectory(directory);
        var temporaryPath = path + ".tmp";
        await File.WriteAllTextAsync(
            temporaryPath,
            JsonSerializer.Serialize(document, JsonOptions),
            cancellationToken);
        File.Move(temporaryPath, path, true);
    }
}
