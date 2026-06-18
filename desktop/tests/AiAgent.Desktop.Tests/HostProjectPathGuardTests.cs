using AiAgent.Desktop.Core.Services;

namespace AiAgent.Desktop.Tests;

public sealed class HostProjectPathGuardTests
{
    [Fact]
    public void RequireAllowed_AcceptsSpecificProjectFolder()
    {
        using var root = new TemporaryDirectory();
        var project = Directory.CreateDirectory(Path.Combine(root.Path, "project")).FullName;
        var guard = new HostProjectPathGuard(
            homePath: Path.Combine(root.Path, "home"),
            systemPaths: [Path.Combine(root.Path, "system")]);

        Assert.Equal(HostProjectPathGuard.Normalize(project), guard.RequireAllowed(project));
    }

    [Fact]
    public void RequireAllowed_RejectsDriveRootHomeAndSystemDescendant()
    {
        using var root = new TemporaryDirectory();
        var home = Directory.CreateDirectory(Path.Combine(root.Path, "home")).FullName;
        var system = Directory.CreateDirectory(Path.Combine(root.Path, "system")).FullName;
        var systemChild = Directory.CreateDirectory(Path.Combine(system, "child")).FullName;
        var guard = new HostProjectPathGuard(home, [system]);

        Assert.Throws<ProjectPathException>(() => guard.RequireAllowed(Path.GetPathRoot(root.Path)!));
        Assert.Throws<ProjectPathException>(() => guard.RequireAllowed(home));
        Assert.Throws<ProjectPathException>(() => guard.RequireAllowed(systemChild));
    }
}
