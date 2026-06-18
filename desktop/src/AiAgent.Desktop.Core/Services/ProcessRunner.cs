using System.Diagnostics;
using System.Text;

namespace AiAgent.Desktop.Core.Services;

public sealed record ProcessSpec(
    string FileName,
    IReadOnlyList<string> Arguments,
    string WorkingDirectory,
    IReadOnlyDictionary<string, string>? Environment = null);

public sealed record ProcessResult(int ExitCode, string Output)
{
    public void EnsureSuccess(string operation)
    {
        if (ExitCode != 0)
        {
            throw new DockerOperationException($"{operation} failed with exit code {ExitCode}.\n{Output}");
        }
    }
}

public interface IProcessRunner
{
    Task<ProcessResult> RunAsync(
        ProcessSpec spec,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default);
}

public sealed class ProcessRunner : IProcessRunner
{
    public async Task<ProcessResult> RunAsync(
        ProcessSpec spec,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = spec.FileName,
            WorkingDirectory = spec.WorkingDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        foreach (var argument in spec.Arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        if (spec.Environment is not null)
        {
            foreach (var item in spec.Environment)
            {
                startInfo.Environment[item.Key] = item.Value;
            }
        }

        using var process = new Process { StartInfo = startInfo };
        if (!process.Start())
        {
            throw new DockerOperationException($"Failed to start {spec.FileName}.");
        }

        var output = new StringBuilder();
        var stdout = PumpAsync(process.StandardOutput, output, progress, cancellationToken);
        var stderr = PumpAsync(process.StandardError, output, progress, cancellationToken);
        try
        {
            await process.WaitForExitAsync(cancellationToken);
            await Task.WhenAll(stdout, stderr);
        }
        catch (OperationCanceledException)
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }

            throw;
        }

        return new ProcessResult(process.ExitCode, output.ToString().TrimEnd());
    }

    private static async Task PumpAsync(
        StreamReader reader,
        StringBuilder output,
        IProgress<string>? progress,
        CancellationToken cancellationToken)
    {
        while (await reader.ReadLineAsync(cancellationToken) is { } line)
        {
            lock (output)
            {
                output.AppendLine(line);
            }

            progress?.Report(line);
        }
    }
}

public sealed class DockerOperationException : Exception
{
    public DockerOperationException(string message)
        : base(message)
    {
    }
}
