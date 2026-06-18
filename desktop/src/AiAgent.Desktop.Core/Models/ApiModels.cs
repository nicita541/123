using System.Text.Json;
using System.Text.Json.Serialization;

namespace AiAgent.Desktop.Core.Models;

public sealed record ProjectRegistrationRequest(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("mount_id")] string MountId,
    [property: JsonPropertyName("host_path")] string HostPath,
    [property: JsonPropertyName("container_path")] string ContainerPath);

public sealed record ProjectDto(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("root_path")] string RootPath,
    [property: JsonPropertyName("mount_id")] string? MountId,
    [property: JsonPropertyName("host_path")] string? HostPath,
    [property: JsonPropertyName("container_path")] string ContainerPath,
    [property: JsonPropertyName("is_active")] bool IsActive,
    [property: JsonPropertyName("last_task_title")] string? LastTaskTitle);

public sealed record ProjectListResponse(
    [property: JsonPropertyName("projects")] IReadOnlyList<ProjectDto> Projects);

public sealed record AgentStatusDto(
    [property: JsonPropertyName("project_id")] string ProjectId,
    [property: JsonPropertyName("project_root")] string ProjectRoot,
    [property: JsonPropertyName("ollama_base_url")] string OllamaBaseUrl,
    [property: JsonPropertyName("ollama_model")] string OllamaModel,
    [property: JsonPropertyName("ollama_reachable")] bool OllamaReachable,
    [property: JsonPropertyName("ollama_generation_check")] bool OllamaGenerationCheck,
    [property: JsonPropertyName("ollama_models")] IReadOnlyList<string> OllamaModels,
    [property: JsonPropertyName("ollama_error")] string? OllamaError);

public sealed record OllamaProbeDto(
    [property: JsonPropertyName("ollama_reachable")] bool OllamaReachable,
    [property: JsonPropertyName("ollama_generation_check")] bool OllamaGenerationCheck,
    [property: JsonPropertyName("ollama_models")] IReadOnlyList<string> OllamaModels,
    [property: JsonPropertyName("ollama_error")] string? OllamaError);

public sealed record TaskListResponse(
    [property: JsonPropertyName("project_id")] string ProjectId,
    [property: JsonPropertyName("tasks")] IReadOnlyList<TaskSummaryDto> Tasks);

public sealed record TaskSummaryDto(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("title")] string Title,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("mode")] string Mode,
    [property: JsonPropertyName("updated_at")] string UpdatedAt);

public sealed record ApprovalDto(
    [property: JsonPropertyName("step_id")] string StepId,
    [property: JsonPropertyName("action")] string Action,
    [property: JsonPropertyName("description")] string Description,
    [property: JsonPropertyName("risk")] string Risk,
    [property: JsonPropertyName("target")] string Target);

public sealed record TaskDto(
    [property: JsonPropertyName("task_id")] string TaskId,
    [property: JsonPropertyName("project_id")] string ProjectId,
    [property: JsonPropertyName("title")] string Title,
    [property: JsonPropertyName("user_message")] string UserMessage,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("mode")] string Mode,
    [property: JsonPropertyName("plan")] JsonElement Plan,
    [property: JsonPropertyName("pending_approvals")] IReadOnlyList<ApprovalDto> PendingApprovals,
    [property: JsonPropertyName("proposed_diff")] string ProposedDiff,
    [property: JsonPropertyName("proposed_files")] IReadOnlyList<string> ProposedFiles,
    [property: JsonPropertyName("proposed_summary")] string ProposedSummary,
    [property: JsonPropertyName("verification_command")] string VerificationCommand,
    [property: JsonPropertyName("verification_output")] string VerificationOutput,
    [property: JsonPropertyName("final_report")] string FinalReport,
    [property: JsonPropertyName("skill_name")] string? SkillName,
    [property: JsonPropertyName("rollback_available")] bool RollbackAvailable,
    [property: JsonPropertyName("rollback_reason")] string RollbackReason,
    [property: JsonPropertyName("errors")] IReadOnlyList<string> Errors,
    [property: JsonPropertyName("warnings")] IReadOnlyList<string> Warnings);
