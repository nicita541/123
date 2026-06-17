# Desktop App

Desktop mode opens the same local task-centered UI in a native Windows window through
`pywebview`. It does not add a second UI and does not bypass the safe runtime.

## Install

```powershell
cd F:\aiAgent
.venv\Scripts\python.exe -m pip install -e ".[desktop]"
```

## Run

```powershell
.venv\Scripts\python.exe -m complex_agent.main desktop --project F:\1
```

or:

```powershell
scripts\run_desktop.ps1
```

The desktop launcher:

- finds a free localhost port;
- starts the FastAPI backend on `127.0.0.1`;
- opens the same `index.html`, `app.js`, and `styles.css` UI;
- uses the selected project root as the sandbox root;
- stops the backend when the desktop window closes.

## Browser vs Desktop

Browser mode:

```powershell
.venv\Scripts\python.exe -m complex_agent.main serve --project F:\1 --host 127.0.0.1 --port 8765
```

Desktop mode:

```powershell
.venv\Scripts\python.exe -m complex_agent.main desktop --project F:\1
```

Both modes use the same backend routes and the same static UI. Desktop mode only embeds
the localhost page in a desktop window titled `Локальный агент`.

## Sandbox

The agent can change files only inside the selected project folder. File preview, search,
patch validation, patch application, git status/diff, and shell checks all run through the
current runtime and safety policy.

Forbidden paths such as `.env`, `.agent`, `.venv`, `__pycache__`, private keys, `secret/*`,
and `token/*` are hidden or blocked.

There are no desktop endpoints for arbitrary shell commands, raw file writes, raw patch
apply, arbitrary git commands, cloud execution, auto-commit, or auto-push.

## Future Packaging

An `.exe` can be packaged later with PyInstaller or a similar tool. That is intentionally
outside the MVP; the current baseline is a Python-launched local desktop app.
