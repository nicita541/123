using System.Text.Json;
using AiAgent.Desktop.Core.Models;

namespace AiAgent.Desktop.Core.Services;

public sealed class DesktopSettingsStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true,
    };

    public DesktopSettingsStore(string? settingsPath = null)
    {
        SettingsPath = settingsPath ?? Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "AiAgent",
            "desktop-settings.json");
    }

    public string SettingsPath { get; }

    public async Task<DesktopSettings> LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(SettingsPath))
        {
            return new DesktopSettings();
        }

        await using var stream = File.OpenRead(SettingsPath);
        return await JsonSerializer.DeserializeAsync<DesktopSettings>(stream, JsonOptions, cancellationToken)
            ?? new DesktopSettings();
    }

    public async Task SaveAsync(DesktopSettings settings, CancellationToken cancellationToken = default)
    {
        var directory = Path.GetDirectoryName(SettingsPath)
            ?? throw new InvalidOperationException("Desktop settings path has no parent directory.");
        Directory.CreateDirectory(directory);
        var temporaryPath = SettingsPath + ".tmp";
        await using (var stream = File.Create(temporaryPath))
        {
            await JsonSerializer.SerializeAsync(stream, settings, JsonOptions, cancellationToken);
        }

        File.Move(temporaryPath, SettingsPath, true);
    }
}
