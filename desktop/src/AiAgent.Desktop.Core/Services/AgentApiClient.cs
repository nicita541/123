using System.Net.Http.Json;
using System.Text.Json;
using AiAgent.Desktop.Core.Models;

namespace AiAgent.Desktop.Core.Services;

public sealed class AgentApiClient
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private readonly HttpClient _httpClient;

    public AgentApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<bool> HealthAsync(CancellationToken cancellationToken = default)
    {
        using var response = await _httpClient.GetAsync("/health", cancellationToken);
        return response.IsSuccessStatusCode;
    }

    public Task<AgentStatusDto> GetStatusAsync(CancellationToken cancellationToken = default) =>
        GetAsync<AgentStatusDto>("/api/status", cancellationToken);

    public Task<OllamaProbeDto> ProbeOllamaAsync(CancellationToken cancellationToken = default) =>
        SendAsync<OllamaProbeDto>(
            new HttpRequestMessage(HttpMethod.Post, "/api/ollama/probe"),
            cancellationToken);

    public Task<JsonElement> SelectModelAsync(
        string model,
        CancellationToken cancellationToken = default) =>
        PostAsync<JsonElement>("/api/settings", new { selected_model = model }, cancellationToken);

    public async Task<IReadOnlyList<ProjectDto>> GetProjectsAsync(CancellationToken cancellationToken = default) =>
        (await GetAsync<ProjectListResponse>("/api/projects", cancellationToken)).Projects;

    public Task<ProjectDto> RegisterProjectAsync(
        ProjectMount project,
        CancellationToken cancellationToken = default) =>
        PostAsync<ProjectDto>(
            "/api/projects/register",
            new ProjectRegistrationRequest(
                project.Name,
                project.MountId,
                project.HostPath,
                project.ContainerPath),
            cancellationToken);

    public Task<ProjectDto> OpenProjectAsync(string projectId, CancellationToken cancellationToken = default) =>
        PostAsync<ProjectDto>($"/api/projects/{Uri.EscapeDataString(projectId)}/open", new { }, cancellationToken);

    public async Task<IReadOnlyList<TaskSummaryDto>> GetTasksAsync(
        string projectId,
        CancellationToken cancellationToken = default) =>
        (await GetAsync<TaskListResponse>(
            $"/api/tasks?project_id={Uri.EscapeDataString(projectId)}",
            cancellationToken)).Tasks;

    public Task<TaskDto> GetTaskAsync(string taskId, CancellationToken cancellationToken = default) =>
        GetAsync<TaskDto>($"/api/tasks/{Uri.EscapeDataString(taskId)}", cancellationToken);

    public Task<TaskDto> PlanAsync(
        string projectId,
        string task,
        string mode = "review",
        CancellationToken cancellationToken = default) =>
        PostAsync<TaskDto>("/api/tasks/plan", new { task, mode, project_id = projectId }, cancellationToken);

    public Task<TaskDto> ProposeAsync(string taskId, CancellationToken cancellationToken = default) =>
        PostAsync<TaskDto>($"/api/tasks/{Uri.EscapeDataString(taskId)}/propose", new { }, cancellationToken);

    public Task<TaskDto> ApproveAsync(
        string taskId,
        ApprovalDto approval,
        CancellationToken cancellationToken = default) =>
        PostAsync<TaskDto>(
            $"/api/tasks/{Uri.EscapeDataString(taskId)}/approve",
            new { step_id = approval.StepId, action = approval.Action },
            cancellationToken);

    public Task<TaskDto> RejectAsync(
        string taskId,
        ApprovalDto approval,
        CancellationToken cancellationToken = default) =>
        PostAsync<TaskDto>(
            $"/api/tasks/{Uri.EscapeDataString(taskId)}/reject",
            new { step_id = approval.StepId, action = approval.Action },
            cancellationToken);

    public Task<TaskDto> RunAsync(string taskId, CancellationToken cancellationToken = default) =>
        PostAsync<TaskDto>($"/api/tasks/{Uri.EscapeDataString(taskId)}/run", new { }, cancellationToken);

    public Task<TaskDto> RollbackAsync(
        string taskId,
        bool confirmCreatedDeletions,
        CancellationToken cancellationToken = default) =>
        PostAsync<TaskDto>(
            $"/api/tasks/{Uri.EscapeDataString(taskId)}/rollback",
            new { confirm_created_deletions = confirmCreatedDeletions },
            cancellationToken);

    public async Task WaitForHealthAsync(
        TimeSpan timeout,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var deadline = DateTimeOffset.UtcNow + timeout;
        Exception? lastError = null;
        while (DateTimeOffset.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                if (await HealthAsync(cancellationToken))
                {
                    return;
                }
            }
            catch (HttpRequestException exception)
            {
                lastError = exception;
            }

            progress?.Report("Waiting for backend health...");
            await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
        }

        throw new TimeoutException($"Backend did not become healthy within {timeout}. {lastError?.Message}");
    }

    private Task<T> GetAsync<T>(string path, CancellationToken cancellationToken) =>
        SendAsync<T>(new HttpRequestMessage(HttpMethod.Get, path), cancellationToken);

    private Task<T> PostAsync<T>(string path, object body, CancellationToken cancellationToken)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, path)
        {
            Content = JsonContent.Create(body, options: JsonOptions),
        };
        return SendAsync<T>(request, cancellationToken);
    }

    private async Task<T> SendAsync<T>(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        using (request)
        using (var response = await _httpClient.SendAsync(request, cancellationToken))
        {
            if (!response.IsSuccessStatusCode)
            {
                var body = await response.Content.ReadAsStringAsync(cancellationToken);
                throw new AgentApiException((int)response.StatusCode, ReadError(body));
            }

            return await response.Content.ReadFromJsonAsync<T>(JsonOptions, cancellationToken)
                ?? throw new AgentApiException((int)response.StatusCode, "Backend returned an empty response.");
        }
    }

    private static string ReadError(string body)
    {
        try
        {
            using var document = JsonDocument.Parse(body);
            if (document.RootElement.TryGetProperty("detail", out var detail))
            {
                return detail.GetString() ?? body;
            }
        }
        catch (JsonException)
        {
            // Return the original response when the backend did not send JSON.
        }

        return body;
    }
}

public sealed class AgentApiException(int statusCode, string message) : Exception(message)
{
    public int StatusCode { get; } = statusCode;
}
