using System.Collections.ObjectModel;
using System.Text.Json;
using AiAgent.Desktop.Core.Models;
using CommunityToolkit.Mvvm.ComponentModel;

namespace AiAgent.Desktop.ViewModels;

public partial class TaskDetailViewModel : ViewModelBase
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    [ObservableProperty]
    private string _taskId = string.Empty;

    [ObservableProperty]
    private string _title = "Select a task or create a new one";

    [ObservableProperty]
    private string _status = "idle";

    [ObservableProperty]
    private string _planText = string.Empty;

    [ObservableProperty]
    private string _diffText = string.Empty;

    [ObservableProperty]
    private string _verificationText = string.Empty;

    [ObservableProperty]
    private string _reportText = string.Empty;

    [ObservableProperty]
    private string _providerText = string.Empty;

    [ObservableProperty]
    private bool _hasTask;

    [ObservableProperty]
    private bool _hasPlan;

    [ObservableProperty]
    private bool _hasDiff;

    [ObservableProperty]
    private bool _hasApproval;

    [ObservableProperty]
    private bool _hasVerification;

    [ObservableProperty]
    private bool _hasReport;

    [ObservableProperty]
    private bool _canRollback;

    public ObservableCollection<ApprovalDto> Approvals { get; } = [];

    public TaskDto? Current { get; private set; }

    public void Apply(TaskDto task)
    {
        Current = task;
        TaskId = task.TaskId;
        Title = task.Title;
        Status = task.Status;
        PlanText = task.Plan.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined
            ? string.Empty
            : JsonSerializer.Serialize(task.Plan, JsonOptions);
        DiffText = task.ProposedDiff;
        VerificationText = string.Join(
            Environment.NewLine,
            new[] { task.VerificationCommand, task.VerificationOutput }.Where(
                static value => !string.IsNullOrWhiteSpace(value)));
        ReportText = task.FinalReport;
        ProviderText = string.IsNullOrWhiteSpace(task.SkillName)
            ? string.Empty
            : $"Provider: {task.SkillName}";
        HasTask = true;
        HasPlan = !string.IsNullOrWhiteSpace(PlanText);
        HasDiff = !string.IsNullOrWhiteSpace(DiffText);
        HasVerification = !string.IsNullOrWhiteSpace(VerificationText);
        HasReport = !string.IsNullOrWhiteSpace(ReportText);
        CanRollback = task.RollbackAvailable;
        Approvals.Clear();
        foreach (var approval in task.PendingApprovals)
        {
            Approvals.Add(approval);
        }

        HasApproval = Approvals.Count > 0;
    }
}
