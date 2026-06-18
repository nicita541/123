using System.Net;
using System.Text;
using AiAgent.Desktop.Core.Models;
using AiAgent.Desktop.Core.Services;

namespace AiAgent.Desktop.Tests;

public sealed class AgentApiClientTests
{
    [Fact]
    public async Task RegisterProjectAsync_SendsSeparatedHostAndContainerPaths()
    {
        string? requestBody = null;
        var handler = new StubHandler(async request =>
        {
            requestBody = await request.Content!.ReadAsStringAsync(CancellationToken.None);
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(
                    """
                    {
                      "id":"project_backend",
                      "name":"Todo",
                      "root_path":"/projects/project_12345678",
                      "mount_id":"project_12345678",
                      "host_path":"F:\\1",
                      "container_path":"/projects/project_12345678",
                      "is_active":true,
                      "last_task_title":null
                    }
                    """,
                    Encoding.UTF8,
                    "application/json"),
            };
        });
        using var httpClient = new HttpClient(handler) { BaseAddress = new Uri("http://127.0.0.1:8765") };
        var client = new AgentApiClient(httpClient);
        var project = new ProjectMount
        {
            MountId = "project_12345678",
            Name = "Todo",
            HostPath = @"F:\1",
            ContainerPath = "/projects/project_12345678",
        };

        var registered = await client.RegisterProjectAsync(project, CancellationToken.None);

        Assert.Equal("project_backend", registered.Id);
        Assert.Contains("\"host_path\":\"F:\\\\1\"", requestBody, StringComparison.Ordinal);
        Assert.Contains("\"container_path\":\"/projects/project_12345678\"", requestBody, StringComparison.Ordinal);
    }

    private sealed class StubHandler(Func<HttpRequestMessage, Task<HttpResponseMessage>> responder)
        : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken) => responder(request);
    }
}
