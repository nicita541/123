using Avalonia.Controls;
using Avalonia.Platform.Storage;

namespace AiAgent.Desktop.Services;

public sealed class AvaloniaFolderPickerService(Window owner) : IFolderPickerService
{
    public async Task<string?> PickProjectFolderAsync(CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var folders = await owner.StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions
        {
            Title = "Choose a project folder",
            AllowMultiple = false,
        });
        cancellationToken.ThrowIfCancellationRequested();
        return folders.FirstOrDefault()?.TryGetLocalPath();
    }
}
