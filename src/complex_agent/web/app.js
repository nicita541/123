const state = {
  activeProjectId: null,
  currentProjectRoot: "",
  taskId: null,
  taskStatus: "idle",
  proposedDiff: "",
  proposedFiles: [],
  pendingApprovals: [],
  workspace: null,
  busy: false,
  continuing: false,
  projects: [],
  tasks: [],
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return map[char];
  });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = await response.text();
    try { detail = JSON.parse(detail).detail || detail; } catch (_) { /* plain response */ }
    throw new Error(String(detail));
  }
  return response.json();
}

function toast(message, type = "error") {
  const box = $("toast");
  box.textContent = message;
  box.className = `toast ${type}`;
  box.hidden = false;
  window.setTimeout(() => { box.hidden = true; }, 4200);
}

function setBusy(busy) {
  state.busy = busy;
  $("sendBtn").disabled = busy || !$("taskInput").value.trim();
  document.querySelectorAll("button").forEach((button) => {
    if (["closeSettingsBtn", "cancelProjectBtn"].includes(button.id)) return;
    if (button.hasAttribute("data-always-enabled")) return;
    button.disabled = busy || button.hasAttribute("data-disabled");
  });
}

function translateStatus(status) {
  const map = {
    idle: "Нет задачи", draft: "Черновик", planning: "План составляется",
    planned: "План готов", proposing: "Готовится Diff",
    waiting_approval: "Ожидается подтверждение", approved: "Подтверждено",
    applying: "Применяется patch", verifying: "Проверка", needs_fix: "Нужно исправление",
    completed: "Выполнено", failed: "Ошибка", rejected: "Отклонено", archived: "Архив",
  };
  return map[status] || status;
}

function setStatus(status) {
  state.taskStatus = status;
  $("envProgress").textContent = translateStatus(status);
  $("envTaskStatus").textContent = translateStatus(status);
}

function projectName(path) {
  const normalized = String(path || "").replaceAll("\\", "/").replace(/\/$/, "");
  return normalized.split("/").pop() || "проект";
}

function addFeedCard(className, html) {
  $("emptyState").hidden = true;
  const card = document.createElement("article");
  card.className = `feed-card ${className}`;
  card.innerHTML = html;
  $("feed").appendChild(card);
  return card;
}

function renderUserMessage(text) {
  addFeedCard("user-card", `<div class="card-label">Вы</div><p>${escapeHtml(text)}</p>`);
}

function renderSystemEvent(text) {
  addFeedCard("system-card", `<p>${escapeHtml(text)}</p>`);
}

function renderPlan(data, interactive = true) {
  const steps = (data.plan?.steps || []).map((step, index) => `
    <li><span>${index + 1}</span><div><strong>${escapeHtml(step.description)}</strong>
    <small>${escapeHtml(step.required_tool)} · ${escapeHtml(step.risk_level)}</small></div></li>`).join("");
  const actions = interactive && ["planned", "failed"].includes(data.status) ? `
    <div class="approval-actions">
      <button id="proposeBtn" class="card-action" type="button">Предложить изменения</button>
    </div>` : "";
  addFeedCard("plan-card", `<div class="card-label">Агент</div><h3>План выполнения</h3>
    <ol class="plan-list">${steps}</ol>${actions}`);
  if ($("proposeBtn")) $("proposeBtn").onclick = proposeChanges;
}

function renderDiffCard(data) {
  state.proposedDiff = data.proposed_diff || "";
  state.proposedFiles = data.proposed_files || [];
  const files = state.proposedFiles.map((file) => `<li>${escapeHtml(file)}</li>`).join("");
  addFeedCard("diff-card", `<div class="card-label">Предложены изменения</div>
    <h3>Diff готов к проверке</h3><p>${escapeHtml(data.proposed_summary || "")}</p>
    <ul class="changed-files">${files}</ul><details><summary>Показать Diff</summary>
    <pre class="diff-code">${escapeHtml(state.proposedDiff)}</pre></details>`);
  renderChangedFiles(state.proposedFiles);
}

function renderApprovalCard(data) {
  state.pendingApprovals = data.pending_approvals || [];
  if (!state.pendingApprovals.length) return;
  const approval = state.pendingApprovals[0];
  addFeedCard("approval-card", `<div class="card-label">Подтверждение</div>
    <h3>Разрешить изменение файлов?</h3><p>${escapeHtml(approval.description)}</p>
    <p class="muted">Цель: ${escapeHtml(approval.target || "")}</p>
    <div class="approval-actions"><button id="approveBtn" class="card-action">Подтвердить</button>
    <button id="rejectBtn" class="card-action secondary">Отклонить</button></div>`);
  $("approveBtn").onclick = () => approve(approval);
  $("rejectBtn").onclick = () => reject(approval);
}

function renderResult(data) {
  const success = data.status === "completed";
  const controls = `
    <div class="approval-actions">
      ${data.status === "needs_fix" ? '<button id="fixBtn" class="card-action">Предложить исправление</button>' : ""}
      <button id="repeatBtn" class="card-action secondary">Повторить задачу</button>
      <button id="continueBtn" class="card-action secondary">Продолжить</button>
      ${data.rollback_available ? '<button id="rollbackBtn" class="card-action danger">Откатить</button>' : ""}
    </div>`;
  addFeedCard("result-card", `<div class="card-label">${success ? "Готово" : "Результат"}</div>
    <h3>${escapeHtml(translateStatus(data.status))}</h3>
    <details open><summary>Проверка</summary><pre>${escapeHtml(data.verification_output || "Нет вывода")}</pre></details>
    <details><summary>Финальный отчёт</summary><pre>${escapeHtml(data.final_report || "Отчёт пока не создан")}</pre></details>
    ${controls}`);
  if ($("fixBtn")) $("fixBtn").onclick = proposeFix;
  $("repeatBtn").onclick = repeatTask;
  $("continueBtn").onclick = startContinuation;
  if ($("rollbackBtn")) $("rollbackBtn").onclick = rollbackTask;
}

function renderChangedFiles(files) {
  $("envChangedFiles").innerHTML = files.length
    ? files.map((file) => `<li>${escapeHtml(file)}</li>`).join("") : "<li>Нет</li>";
}

function resetFeed() {
  $("feed").innerHTML = "";
  $("emptyState").hidden = false;
}

function resetChat() {
  state.taskId = null;
  state.continuing = false;
  state.proposedDiff = "";
  state.proposedFiles = [];
  resetFeed();
  setStatus("idle");
  renderChangedFiles([]);
}

async function loadProjects() {
  const data = await api(`/api/projects?search=${encodeURIComponent($("projectSearch").value.trim())}`);
  state.projects = data.projects || [];
  const list = $("projectList");
  list.innerHTML = state.projects.map((project) => `
    <li><button class="project-list-item ${project.is_active ? "active" : ""}" data-project-id="${escapeHtml(project.id)}">
      <strong>${escapeHtml(project.name)}</strong><small>${escapeHtml(project.last_task_title || project.root_path)}</small>
    </button></li>`).join("");
  list.querySelectorAll("[data-project-id]").forEach((button) => {
    button.onclick = () => openProject(button.dataset.projectId);
  });
}

async function loadTasks() {
  if (!state.activeProjectId) return;
  const data = await api(`/api/tasks?project_id=${encodeURIComponent(state.activeProjectId)}`);
  const search = $("taskSearch").value.trim().toLowerCase();
  state.tasks = (data.tasks || []).filter((task) => !search || task.title.toLowerCase().includes(search));
  const groups = { "Сегодня": [], "Вчера": [], "Ранее": [] };
  const now = new Date();
  state.tasks.forEach((task) => {
    const date = new Date(task.updated_at);
    const days = Math.floor((new Date(now.toDateString()) - new Date(date.toDateString())) / 86400000);
    groups[days === 0 ? "Сегодня" : days === 1 ? "Вчера" : "Ранее"].push(task);
  });
  $("taskHistory").innerHTML = Object.entries(groups).filter(([, tasks]) => tasks.length).map(([name, tasks]) => `
    <section><h3>${name}</h3><ul>${tasks.map((task) => `<li><button data-task-id="${escapeHtml(task.id)}">
    <span>${escapeHtml(task.title)}</span><small>${escapeHtml(translateStatus(task.status))}</small></button></li>`).join("")}</ul></section>`).join("") || "<p>Задач пока нет</p>";
  $("taskHistory").querySelectorAll("[data-task-id]").forEach((button) => {
    button.onclick = () => openTask(button.dataset.taskId);
  });
}

async function openProject(projectId) {
  setBusy(true);
  try {
    await api(`/api/projects/${projectId}/open`, { method: "POST" });
    resetChat();
    await loadStatus();
    toast("Проект открыт", "success");
  } catch (error) { handleError(error); } finally { setBusy(false); }
}

async function openTask(taskId) {
  setBusy(true);
  try {
    const data = await api(`/api/tasks/${taskId}`);
    state.taskId = taskId;
    state.continuing = false;
    resetFeed();
    (data.messages || []).filter((message) => message.role === "user").forEach((message) => renderUserMessage(message.content));
    renderPlan(data, false);
    if (data.proposed_diff) renderDiffCard(data);
    renderApprovalCard(data);
    if (["completed", "failed", "needs_fix", "rejected"].includes(data.status)) renderResult(data);
    setStatus(data.status);
    renderChangedFiles(data.proposed_files || []);
  } catch (error) { handleError(error); } finally { setBusy(false); }
}

async function loadStatus() {
  const [project, status, workspace] = await Promise.all([
    api("/api/project"), api("/api/status"), api("/api/workspace"),
  ]);
  state.activeProjectId = project.id || status.project_id;
  state.currentProjectRoot = project.project_root;
  state.workspace = workspace;
  $("projectName").textContent = project.name || projectName(project.project_root);
  $("projectPath").textContent = project.project_root;
  $("projectInput").value = project.project_root;
  $("envProject").textContent = project.project_root;
  $("envBranch").textContent = workspace.git_branch || "нет ветки";
  $("envChanges").textContent = `${workspace.changed_files.length} файлов`;
  $("envProvider").textContent = "Ollama";
  $("envModel").textContent = status.ollama_model;
  $("envModelStatus").textContent = status.ollama_reachable
    ? (status.ollama_generation_check ? "Подключено" : "Доступен, generation check не пройден")
    : "Не проверен или недоступен";
  const ollamaModels = status.ollama_models || [];
  $("agentSelector").innerHTML = ollamaModels.length
    ? ollamaModels.map((model) => `<option>${escapeHtml(model)}</option>`).join("")
    : `<option>${escapeHtml(status.ollama_model)}</option>`;
  $("envSources").innerHTML = (workspace.files || []).slice(0, 4)
    .map((file) => `<li>${escapeHtml(file.path)}</li>`).join("") || "<li>Источников пока нет</li>";
  await Promise.all([loadProjects(), loadTasks()]);
}

async function selectProject(event) {
  event.preventDefault();
  const path = $("projectInput").value.trim();
  if (!path) return;
  setBusy(true);
  try {
    await api("/api/project/select", { method: "POST", body: JSON.stringify({ path }) });
    $("projectForm").hidden = true;
    resetChat();
    await loadStatus();
    toast("Рабочая папка добавлена", "success");
  } catch (error) { handleError(error); } finally { setBusy(false); }
}

async function chooseFolder() {
  $("projectForm").hidden = false;
  $("projectInput").focus();
}

async function archiveCurrentProject() {
  if (!state.activeProjectId || !window.confirm("Архивировать текущий проект?")) return;
  await api(`/api/projects/${state.activeProjectId}/archive`, { method: "POST" });
  resetChat();
  await loadStatus();
}

async function submitTask(taskOverride = "") {
  const task = taskOverride || $("taskInput").value.trim();
  if (!task) return;
  $("taskInput").value = "";
  setBusy(true);
  try {
    let data;
    if (state.continuing && state.taskId) {
      data = await api(`/api/tasks/${state.taskId}/continue`, { method: "POST", body: JSON.stringify({ message: task }) });
      state.continuing = false;
    } else {
      data = await api("/api/tasks/plan", { method: "POST", body: JSON.stringify({
        task, mode: $("mode").value, project_id: state.activeProjectId,
      }) });
      state.taskId = data.task_id;
    }
    await openTask(data.task_id);
    await loadTasks();
  } catch (error) { handleError(error); } finally { setBusy(false); }
}

async function proposeChanges() {
  if (!state.taskId) return;
  setBusy(true);
  try {
    const data = await api(`/api/tasks/${state.taskId}/propose`, { method: "POST" });
    await openTask(data.task_id);
    await loadTasks();
  } catch (error) { handleError(error); } finally { setBusy(false); }
}

async function runGoal() {
  if (!state.taskId) return submitTask();
  if (state.taskStatus === "planned") return proposeChanges();
  if (state.taskStatus === "waiting_approval") return renderSystemEvent("Сначала подтвердите Diff.");
  return runTask();
}

async function approve(approval) {
  setBusy(true);
  try {
    await api(`/api/tasks/${state.taskId}/approve`, { method: "POST", body: JSON.stringify({
      step_id: approval.step_id, action: approval.action,
    }) });
    await runTask();
  } catch (error) { handleError(error); } finally { setBusy(false); }
}

async function reject(approval) {
  setBusy(true);
  try {
    await api(`/api/tasks/${state.taskId}/reject`, { method: "POST", body: JSON.stringify({
      step_id: approval.step_id, action: approval.action,
    }) });
    await openTask(state.taskId);
    await loadTasks();
  } catch (error) { handleError(error); } finally { setBusy(false); }
}

async function runTask() {
  const data = await api(`/api/tasks/${state.taskId}/run`, { method: "POST" });
  await openTask(data.task_id);
  await Promise.all([loadTasks(), loadStatus()]);
}

async function proposeFix() {
  const data = await api(`/api/tasks/${state.taskId}/propose-fix`, { method: "POST" });
  await openTask(data.task_id);
}

async function repeatTask() {
  const data = await api(`/api/tasks/${state.taskId}/repeat`, { method: "POST" });
  state.taskId = data.task_id;
  await openTask(data.task_id);
  await loadTasks();
}

function startContinuation() {
  state.continuing = true;
  $("taskInput").placeholder = "Продолжите текущую задачу";
  $("taskInput").focus();
}

async function rollbackTask() {
  const confirmed = window.confirm("Откатить изменения? Созданные агентом файлы будут удалены.");
  if (!confirmed) return;
  const data = await api(`/api/tasks/${state.taskId}/rollback`, {
    method: "POST", body: JSON.stringify({ confirm_created_deletions: true }),
  });
  await openTask(data.task_id);
  await loadStatus();
}

function showCurrentDiff() {
  if (state.proposedDiff) addFeedCard("diff-card", `<h3>Diff</h3><pre class="diff-code">${escapeHtml(state.proposedDiff)}</pre>`);
  else renderSystemEvent("Diff пока не создан.");
}

async function openSettings() {
  const settings = await api("/api/settings");
  $("settingOllamaUrl").value = settings.ollama_base_url;
  $("settingModel").value = settings.selected_model;
  $("settingMode").value = settings.default_access_mode;
  $("settingFixIterations").value = settings.max_fix_iterations;
  $("settingAppData").value = settings.app_data_path;
  $("settingsDialog").showModal();
}

async function saveSettings(event) {
  event.preventDefault();
  await api("/api/settings", { method: "POST", body: JSON.stringify({
    ollama_base_url: $("settingOllamaUrl").value.trim(), selected_model: $("settingModel").value.trim(),
    default_access_mode: $("settingMode").value, max_fix_iterations: Number($("settingFixIterations").value),
  }) });
  $("settingsDialog").close();
  await loadStatus();
  toast("Настройки сохранены", "success");
}

function handleError(error) {
  const message = error instanceof Error ? error.message : String(error);
  toast(message);
  renderSystemEvent(`Ошибка: ${message}`);
}

function setupEvents() {
  $("taskInput").addEventListener("input", () => { $("sendBtn").disabled = state.busy || !$("taskInput").value.trim(); });
  $("taskInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submitTask(); }
  });
  $("sendBtn").onclick = () => submitTask();
  $("newChatBtn").onclick = resetChat;
  $("refreshBtn").onclick = () => loadStatus().catch(handleError);
  $("envCheckBtn").onclick = async () => { await api("/api/ollama/probe", { method: "POST" }); await loadStatus(); };
  $("envDiffBtn").onclick = showCurrentDiff;
  $("chooseProjectBtn").onclick = chooseFolder;
  $("openFolderBtn").onclick = chooseFolder;
  $("archiveProjectBtn").onclick = () => archiveCurrentProject().catch(handleError);
  $("projectForm").onsubmit = selectProject;
  $("cancelProjectBtn").onclick = () => { $("projectForm").hidden = true; };
  $("projectSearch").oninput = () => loadProjects().catch(handleError);
  $("taskSearch").oninput = () => loadTasks().catch(handleError);
  $("settingsBtn").onclick = () => openSettings().catch(handleError);
  $("closeSettingsBtn").onclick = () => $("settingsDialog").close();
  $("settingsForm").onsubmit = (event) => saveSettings(event).catch(handleError);
  $("clearCacheBtn").onclick = async () => { await api("/api/maintenance/cache/clear", { method: "POST" }); toast("Cache очищен", "success"); };
  document.querySelectorAll(".quick-prompts button").forEach((button) => { button.onclick = () => submitTask(button.textContent || ""); });
}

setupEvents();
setStatus("idle");
loadStatus().catch(handleError);
