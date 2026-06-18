# Desktop Application

Install and run:

```powershell
scripts\install_desktop_deps.ps1
scripts\run_desktop.ps1 -Project F:\1
```

The launcher starts FastAPI on a free localhost port and embeds the same UI in pywebview. It
does not depend on an external browser. Closing the window stops the local server.

Desktop and browser modes share `AppStore`, so saved projects, history, settings, diffs,
reports, and rollback metadata are identical. `DesktopBridge.choose_project` opens the
native folder dialog; browser mode falls back to manual path entry.

If pywebview is missing, the command returns a clear instruction to install `.[desktop]`.
The backend remains bound to localhost by default.
