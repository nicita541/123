namespace AiAgent.Desktop.Core.Services;

public static class InfrastructureLocator
{
    public static string Find(string? startPath = null)
    {
        var configured = Environment.GetEnvironmentVariable("AIAGENT_HOME");
        if (!string.IsNullOrWhiteSpace(configured) && HasComposeFile(configured))
        {
            return Path.GetFullPath(configured);
        }

        foreach (var origin in new[] { startPath, Environment.CurrentDirectory, AppContext.BaseDirectory })
        {
            if (string.IsNullOrWhiteSpace(origin))
            {
                continue;
            }

            var current = new DirectoryInfo(Path.GetFullPath(origin));
            while (current is not null)
            {
                if (HasComposeFile(current.FullName))
                {
                    return current.FullName;
                }

                current = current.Parent;
            }
        }

        throw new DirectoryNotFoundException(
            "Cannot find docker-compose.yml. Set AIAGENT_HOME to the repository directory.");
    }

    private static bool HasComposeFile(string directory) =>
        File.Exists(Path.Combine(directory, "docker-compose.yml"));
}
