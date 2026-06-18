namespace AiAgent.Desktop.Services;

public interface IFolderPickerService
{
    Task<string?> PickProjectFolderAsync(CancellationToken cancellationToken = default);
}
