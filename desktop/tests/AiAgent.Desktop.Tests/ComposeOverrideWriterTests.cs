using System.Text.Json;
using AiAgent.Desktop.Core.Models;
using AiAgent.Desktop.Core.Services;

namespace AiAgent.Desktop.Tests;

public sealed class ComposeOverrideWriterTests
{
    [Fact]
    public async Task WriteAsync_CreatesStructuredBindMounts()
    {
        using var root = new TemporaryDirectory();
        var path = Path.Combine(root.Path, "compose.projects.json");
        var project = new ProjectMount
        {
            MountId = "project_12345678",
            Name = "Todo",
            HostPath = @"F:\1",
            ContainerPath = "/projects/project_12345678",
        };

        await new ComposeOverrideWriter().WriteAsync(path, [project], CancellationToken.None);

        using var document = JsonDocument.Parse(await File.ReadAllTextAsync(path, CancellationToken.None));
        var volume = document.RootElement
            .GetProperty("services")
            .GetProperty("backend")
            .GetProperty("volumes")[0];
        Assert.Equal("bind", volume.GetProperty("type").GetString());
        Assert.Equal(@"F:\1", volume.GetProperty("source").GetString());
        Assert.Equal("/projects/project_12345678", volume.GetProperty("target").GetString());
        Assert.False(volume.GetProperty("read_only").GetBoolean());
    }
}
