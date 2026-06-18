namespace AiAgent.Desktop.Core.Services;

public sealed class HostProjectPathGuard
{
    private readonly string _homePath;
    private readonly IReadOnlyList<string> _systemPaths;

    public HostProjectPathGuard(string? homePath = null, IEnumerable<string>? systemPaths = null)
    {
        _homePath = Normalize(homePath ?? Environment.GetFolderPath(Environment.SpecialFolder.UserProfile));
        _systemPaths = (systemPaths ?? GetSystemPaths())
            .Where(static path => !string.IsNullOrWhiteSpace(path))
            .Select(Normalize)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    public string RequireAllowed(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ProjectPathException("Choose a project folder.");
        }

        string path;
        try
        {
            path = Normalize(value);
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            throw new ProjectPathException("The selected project path is invalid.", exception);
        }

        if (!Directory.Exists(path))
        {
            throw new ProjectPathException($"Project folder does not exist: {path}");
        }

        var root = Normalize(Path.GetPathRoot(path) ?? path);
        if (PathEquals(path, root))
        {
            throw new ProjectPathException("An entire drive cannot be used as a project.");
        }

        if (PathEquals(path, _homePath))
        {
            throw new ProjectPathException("The entire user profile cannot be used as a project.");
        }

        if (_systemPaths.Any(blocked => IsSameOrDescendant(path, blocked)))
        {
            throw new ProjectPathException("Windows and program directories cannot be used as projects.");
        }

        return path;
    }

    public static string Normalize(string path)
    {
        var fullPath = Path.GetFullPath(path.Trim());
        var root = Path.GetPathRoot(fullPath);
        return string.Equals(fullPath, root, StringComparison.OrdinalIgnoreCase)
            ? fullPath
            : fullPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    }

    private static bool IsSameOrDescendant(string candidate, string parent) =>
        PathEquals(candidate, parent)
        || candidate.StartsWith(parent + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);

    private static bool PathEquals(string left, string right) =>
        string.Equals(left, right, StringComparison.OrdinalIgnoreCase);

    private static IEnumerable<string> GetSystemPaths()
    {
        yield return Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        yield return Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        yield return Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        yield return Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
    }
}

public sealed class ProjectPathException : Exception
{
    public ProjectPathException(string message)
        : base(message)
    {
    }

    public ProjectPathException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}
