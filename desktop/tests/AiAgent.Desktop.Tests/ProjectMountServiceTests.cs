using AiAgent.Desktop.Core.Models;
using AiAgent.Desktop.Core.Services;

namespace AiAgent.Desktop.Tests;

public sealed class ProjectMountServiceTests
{
    [Fact]
    public void Create_ProducesStableContainerOnlyMapping()
    {
        using var root = new TemporaryDirectory();
        var projectPath = Directory.CreateDirectory(Path.Combine(root.Path, "todo")).FullName;
        var service = new ProjectMountService(new HostProjectPathGuard(
            Path.Combine(root.Path, "home"),
            []));

        var first = service.Create(projectPath);
        var secondMountId = ProjectMountService.CreateMountId(projectPath.ToUpperInvariant());

        Assert.Equal(first.MountId, secondMountId);
        Assert.Matches("^project_[a-f0-9]{16}$", first.MountId);
        Assert.Equal($"/projects/{first.MountId}", first.ContainerPath);
        Assert.Equal("todo", first.Name);
    }

    [Fact]
    public void Upsert_DoesNotDuplicateSameHostPath()
    {
        using var root = new TemporaryDirectory();
        var projectPath = Directory.CreateDirectory(Path.Combine(root.Path, "todo")).FullName;
        var service = new ProjectMountService(new HostProjectPathGuard(
            Path.Combine(root.Path, "home"),
            []));
        var settings = new DesktopSettings();

        ProjectMountService.Upsert(settings, service.Create(projectPath, "One"));
        ProjectMountService.Upsert(settings, service.Create(projectPath, "Two"));

        var project = Assert.Single(settings.Projects);
        Assert.Equal("Two", project.Name);
    }
}
