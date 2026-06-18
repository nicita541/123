# Multi-project Workflow

Each selected Windows folder has two identities:

- desktop mapping: host_path, stable mount_id, and /projects/<mount_id>;
- backend project: persisted project_id, name, host metadata, and validated container path.

The desktop validates the host folder before writing a structured Compose JSON override.
Backend registration requires the container path to equal /projects/<mount_id>, resolve
below AGENT_PROJECTS_ROOT, and exist as a directory. Host path is stored for display only;
all runtime safety policy, tools, shell cwd, snapshots, verification, and rollback use the
container path.

Tasks persist project_id. Opening another project changes the active workspace but cannot
change the root of an existing task. Task history, approvals, reports, and rollback metadata
therefore remain isolated.

Adding or changing a mount causes Compose to recreate the backend with the updated override.
Ollama and named volumes are not recreated or deleted.
