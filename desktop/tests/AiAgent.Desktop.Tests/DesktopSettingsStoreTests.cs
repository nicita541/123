using AiAgent.Desktop.Core.Models;
using AiAgent.Desktop.Core.Services;

namespace AiAgent.Desktop.Tests;

public sealed class DesktopSettingsStoreTests
{
    [Fact]
    public async Task SaveAndLoad_PreservesProjectMappings()
    {
        using var root = new TemporaryDirectory();
        var store = new DesktopSettingsStore(Path.Combine(root.Path, "settings.json"));
        var settings = new DesktopSettings
        {
            InfrastructureRoot = @"F:\aiAgent",
            Projects =
            [
                new ProjectMount
                {
                    MountId = "project_12345678",
                    ProjectId = "project_backend",
                    Name = "Todo",
                    HostPath = @"F:\1",
                    ContainerPath = "/projects/project_12345678",
                },
            ],
        };

        await store.SaveAsync(settings, CancellationToken.None);
        var restored = await store.LoadAsync(CancellationToken.None);

        Assert.Equal(@"F:\aiAgent", restored.InfrastructureRoot);
        Assert.Equal("project_backend", Assert.Single(restored.Projects).ProjectId);
    }
}
