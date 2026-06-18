using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using AiAgent.Desktop.Services;
using AiAgent.Desktop.Views;

namespace AiAgent.Desktop;

public partial class App : Application
{
    public override void Initialize()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            var window = new MainWindow();
            var viewModel = DesktopBootstrapper.CreateMainWindowViewModel(window);
            window.DataContext = viewModel;
            window.Opened += async (_, _) => await viewModel.InitializeCommand.ExecuteAsync(null);
            desktop.MainWindow = window;
        }

        base.OnFrameworkInitializationCompleted();
    }
}
