using System.Collections.ObjectModel;
using AiAgent.Desktop.Core.Models;
using AiAgent.Desktop.Core.Services;
using AiAgent.Desktop.Services;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace AiAgent.Desktop.ViewModels;

public partial class MainWindowViewModel : ViewModelBase
{
    private readonly DesktopSettingsStore _settingsStore;
    private readonly ComposeOverrideWriter _overrideWriter;
    private readonly DockerComposeService _dockerService;
    private readonly AgentApiClient _apiClient;
    private readonly ProjectRegistrationCoordinator _projectCoordinator;
    private readonly IFolderPickerService _folderPicker;
    private DesktopSettings _settings = new();
    private CancellationTokenSource? _operationCancellation;

    public MainWindowViewModel(
        DesktopSettingsStore settingsStore,
        ComposeOverrideWriter overrideWriter,
        DockerComposeService dockerService,
        AgentApiClient apiClient,
        ProjectRegistrationCoordinator projectCoordinator,
        IFolderPickerService folderPicker)
    {
        _settingsStore = settingsStore;
        _overrideWriter = overrideWriter;
        _dockerService = dockerService;
        _apiClient = apiClient;
        _projectCoordinator = projectCoordinator;
        _folderPicker = folderPicker;
    }

    public ObservableCollection<ProjectMount> Projects { get; } = [];

    public ObservableCollection<TaskSummaryDto> Tasks { get; } = [];

    public ObservableCollection<string> AvailableModels { get; } = [];

    public IReadOnlyList<string> Modes { get; } = ["review", "plan", "dev"];

    public TaskDetailViewModel Detail { get; } = new();

    [ObservableProperty]
    private ProjectMount? _selectedProject;

    [ObservableProperty]
    private TaskSummaryDto? _selectedTask;

    [ObservableProperty]
    private string _selectedMode = "review";

    [ObservableProperty]
    private string _selectedModel = "qwen2.5-coder:1.5b";

    [ObservableProperty]
    private string _composerText = string.Empty;

    [ObservableProperty]
    private string _dockerStatus = "Not checked";

    [ObservableProperty]
    private string _backendStatus = "Offline";

    [ObservableProperty]
    private string _ollamaStatus = "Not checked";

    [ObservableProperty]
    private string _modelStatus = "Not checked";

    [ObservableProperty]
    private string _statusMessage = "Starting desktop application...";

    [ObservableProperty]
    private string _environmentLog = string.Empty;

    [ObservableProperty]
    private bool _isBusy;

    [RelayCommand]
    private Task InitializeAsync() => RunOperationAsync("Initializing", async cancellationToken =>
    {
        _settings = await _settingsStore.LoadAsync(cancellationToken);
        _settings.InfrastructureRoot = _dockerService.Context.InfrastructureRoot;
        SelectedModel = string.IsNullOrWhiteSpace(_settings.SelectedModel)
            ? "qwen2.5-coder:1.5b"
            : _settings.SelectedModel;
        ReplaceProjects(_settings.Projects);
        await _settingsStore.SaveAsync(_settings, cancellationToken);
        await _overrideWriter.WriteAsync(
            _dockerService.Context.OverrideFile,
            _settings.Projects,
            cancellationToken);

        try
        {
            var docker = await _dockerService.CheckDockerAsync(cancellationToken);
            DockerStatus = $"Available ({docker.Output})";
        }
        catch (Exception exception) when (exception is DockerOperationException or System.ComponentModel.Win32Exception)
        {
            DockerStatus = "Unavailable";
            AppendLog(exception.Message);
            return;
        }

        await RefreshBackendAsync(probeOllama: true, cancellationToken);
    });

    [RelayCommand]
    private Task StartServicesAsync() => RunOperationAsync("Starting Docker services", async cancellationToken =>
    {
        await _overrideWriter.WriteAsync(
            _dockerService.Context.OverrideFile,
            _settings.Projects,
            cancellationToken);
        await _dockerService.StartAsync(CreateProgress(), cancellationToken);
        DockerStatus = "Running";
        await _apiClient.WaitForHealthAsync(TimeSpan.FromMinutes(2), CreateProgress(), cancellationToken);
        await RefreshBackendAsync(probeOllama: true, cancellationToken);
    });

    [RelayCommand]
    private Task StopServicesAsync() => RunOperationAsync("Stopping Docker services", async cancellationToken =>
    {
        await _dockerService.StopAsync(CreateProgress(), cancellationToken);
        DockerStatus = "Stopped";
        BackendStatus = "Offline";
        OllamaStatus = "Stopped";
        ModelStatus = "Unavailable";
    });

    [RelayCommand]
    private Task RefreshStatusAsync() => RunOperationAsync("Refreshing environment", async cancellationToken =>
    {
        var docker = await _dockerService.CheckDockerAsync(cancellationToken);
        DockerStatus = $"Available ({docker.Output})";
        await RefreshBackendAsync(probeOllama: true, cancellationToken);
    });

    [RelayCommand]
    private Task PullModelAsync() => RunOperationAsync($"Pulling model {SelectedModel}", async cancellationToken =>
    {
        await _dockerService.PullModelAsync(SelectedModel, CreateProgress(), cancellationToken);
        await _apiClient.SelectModelAsync(SelectedModel, cancellationToken);
        _settings.SelectedModel = SelectedModel;
        await _settingsStore.SaveAsync(_settings, cancellationToken);
        await RefreshBackendAsync(probeOllama: true, cancellationToken);
    });

    [RelayCommand]
    private Task AddProjectAsync() => RunOperationAsync("Adding project", async cancellationToken =>
    {
        var path = await _folderPicker.PickProjectFolderAsync(cancellationToken);
        if (string.IsNullOrWhiteSpace(path))
        {
            StatusMessage = "Project selection cancelled.";
            return;
        }

        var project = await _projectCoordinator.RegisterAsync(
            _settings,
            path,
            progress: CreateProgress(),
            cancellationToken: cancellationToken);
        ReplaceProjects(_settings.Projects);
        SelectedProject = Projects.First(item => item.MountId == project.MountId);
        await LoadTasksAsync(project, cancellationToken);
    });

    [RelayCommand]
    private Task OpenProjectAsync() => RunOperationAsync("Opening project", async cancellationToken =>
    {
        var project = SelectedProject
            ?? throw new InvalidOperationException("Select a project first.");
        await _projectCoordinator.OpenAsync(_settings, project, cancellationToken);
        await LoadTasksAsync(project, cancellationToken);
    });

    [RelayCommand]
    private Task OpenTaskAsync(TaskSummaryDto? task) => RunOperationAsync("Loading task", async cancellationToken =>
    {
        if (task is null)
        {
            return;
        }

        SelectedTask = task;
        Detail.Apply(await _apiClient.GetTaskAsync(task.Id, cancellationToken));
    });

    [RelayCommand]
    private Task SendTaskAsync() => RunOperationAsync("Creating plan", async cancellationToken =>
    {
        var project = SelectedProject
            ?? throw new InvalidOperationException("Select a project first.");
        if (string.IsNullOrWhiteSpace(project.ProjectId))
        {
            throw new InvalidOperationException("Register the selected project with the backend first.");
        }

        var request = ComposerText.Trim();
        if (request.Length == 0)
        {
            throw new InvalidOperationException("Enter a task for the agent.");
        }

        var planned = await _apiClient.PlanAsync(project.ProjectId, request, SelectedMode, cancellationToken);
        Detail.Apply(planned);
        StatusMessage = "Plan created. Waiting for Ollama proposal...";
        var proposed = await _apiClient.ProposeAsync(planned.TaskId, cancellationToken);
        Detail.Apply(proposed);
        ComposerText = string.Empty;
        await LoadTasksAsync(project, cancellationToken);
    });

    [RelayCommand]
    private Task ApproveAsync() => RunOperationAsync("Approving proposal", async cancellationToken =>
    {
        var task = Detail.Current ?? throw new InvalidOperationException("Open a task first.");
        var approval = task.PendingApprovals.FirstOrDefault()
            ?? throw new InvalidOperationException("This task has no pending approval.");
        Detail.Apply(await _apiClient.ApproveAsync(task.TaskId, approval, cancellationToken));
        StatusMessage = "Approved. Review the diff, then click Run.";
    });

    [RelayCommand]
    private Task RejectAsync() => RunOperationAsync("Rejecting proposal", async cancellationToken =>
    {
        var task = Detail.Current ?? throw new InvalidOperationException("Open a task first.");
        var approval = task.PendingApprovals.FirstOrDefault()
            ?? throw new InvalidOperationException("This task has no pending approval.");
        Detail.Apply(await _apiClient.RejectAsync(task.TaskId, approval, cancellationToken));
    });

    [RelayCommand]
    private Task RunTaskAsync() => RunOperationAsync("Applying and verifying task", async cancellationToken =>
    {
        var task = Detail.Current ?? throw new InvalidOperationException("Open a task first.");
        Detail.Apply(await _apiClient.RunAsync(task.TaskId, cancellationToken));
        if (SelectedProject is not null)
        {
            await LoadTasksAsync(SelectedProject, cancellationToken);
        }
    });

    [RelayCommand]
    private Task RollbackAsync() => RunOperationAsync("Rolling back task", async cancellationToken =>
    {
        var task = Detail.Current ?? throw new InvalidOperationException("Open a task first.");
        Detail.Apply(await _apiClient.RollbackAsync(task.TaskId, true, cancellationToken));
    });

    [RelayCommand]
    private void CancelOperation()
    {
        _operationCancellation?.Cancel();
    }

    private async Task RefreshBackendAsync(bool probeOllama, CancellationToken cancellationToken)
    {
        try
        {
            if (!await _apiClient.HealthAsync(cancellationToken))
            {
                BackendStatus = "Unhealthy";
                return;
            }

            BackendStatus = "Healthy";
            var status = await _apiClient.GetStatusAsync(cancellationToken);
            OllamaStatus = status.OllamaReachable ? "Reachable" : "Not probed";
            if (probeOllama)
            {
                var probe = await _apiClient.ProbeOllamaAsync(cancellationToken);
                OllamaStatus = probe.OllamaReachable ? "Reachable" : $"Unavailable: {probe.OllamaError}";
                ReplaceModels(probe.OllamaModels);
                if (probe.OllamaModels.Contains(SelectedModel, StringComparer.OrdinalIgnoreCase))
                {
                    ModelStatus = "Installed";
                }
                else
                {
                    var init = await _dockerService.GetModelInitStateAsync(cancellationToken);
                    ModelStatus = init.IsRunning
                        ? "Downloading in model-init"
                        : init.HasFailed
                            ? "Download failed - use Pull model"
                            : "Missing - use Pull model";
                }
            }

            await SynchronizeProjectsAsync(cancellationToken);
        }
        catch (HttpRequestException exception)
        {
            BackendStatus = "Offline";
            OllamaStatus = "Unknown";
            AppendLog(exception.Message);
        }
    }

    private async Task SynchronizeProjectsAsync(CancellationToken cancellationToken)
    {
        var backendProjects = await _apiClient.GetProjectsAsync(cancellationToken);
        foreach (var backendProject in backendProjects)
        {
            var local = _settings.Projects.FirstOrDefault(item => item.MountId == backendProject.MountId);
            if (local is not null)
            {
                local.ProjectId = backendProject.Id;
            }
        }

        await _settingsStore.SaveAsync(_settings, cancellationToken);
        ReplaceProjects(_settings.Projects);
        var active = backendProjects.FirstOrDefault(static item => item.IsActive);
        SelectedProject = active is null
            ? Projects.FirstOrDefault()
            : Projects.FirstOrDefault(item => item.ProjectId == active.Id);
        if (SelectedProject is not null)
        {
            await LoadTasksAsync(SelectedProject, cancellationToken);
        }
    }

    private async Task LoadTasksAsync(ProjectMount project, CancellationToken cancellationToken)
    {
        Tasks.Clear();
        if (string.IsNullOrWhiteSpace(project.ProjectId))
        {
            return;
        }

        foreach (var task in await _apiClient.GetTasksAsync(project.ProjectId, cancellationToken))
        {
            Tasks.Add(task);
        }
    }

    private void ReplaceProjects(IEnumerable<ProjectMount> projects)
    {
        var selectedMount = SelectedProject?.MountId;
        Projects.Clear();
        foreach (var project in projects.OrderByDescending(static item => item.LastOpenedAt))
        {
            Projects.Add(project);
        }

        SelectedProject = Projects.FirstOrDefault(item => item.MountId == selectedMount)
            ?? Projects.FirstOrDefault();
    }

    private void ReplaceModels(IEnumerable<string> models)
    {
        AvailableModels.Clear();
        foreach (var model in models.Order(StringComparer.OrdinalIgnoreCase))
        {
            AvailableModels.Add(model);
        }
    }

    private async Task RunOperationAsync(
        string operation,
        Func<CancellationToken, Task> action)
    {
        if (IsBusy)
        {
            return;
        }

        _operationCancellation = new CancellationTokenSource();
        IsBusy = true;
        StatusMessage = operation;
        AppendLog(operation);
        try
        {
            await action(_operationCancellation.Token);
            if (!_operationCancellation.IsCancellationRequested)
            {
                StatusMessage = $"{operation}: complete";
            }
        }
        catch (OperationCanceledException)
        {
            StatusMessage = $"{operation}: cancelled";
        }
        catch (Exception exception) when (
            exception is DockerOperationException
            or AgentApiException
            or ProjectPathException
            or InvalidOperationException
            or HttpRequestException
            or TimeoutException
            or System.ComponentModel.Win32Exception)
        {
            StatusMessage = $"{operation}: failed";
            AppendLog(exception.Message);
        }
        finally
        {
            _operationCancellation.Dispose();
            _operationCancellation = null;
            IsBusy = false;
        }
    }

    private IProgress<string> CreateProgress() => new Progress<string>(AppendLog);

    private void AppendLog(string line)
    {
        var lines = (EnvironmentLog + Environment.NewLine + line)
            .Split(Environment.NewLine, StringSplitOptions.RemoveEmptyEntries)
            .TakeLast(80);
        EnvironmentLog = string.Join(Environment.NewLine, lines);
    }
}
