const state = {
  taskId: null,
  sessionId: null,
  uiState: "idle",
  isBusy: false,
  files: [],
  tools: [],
  pendingApprovals: [],
  lastReport: "",
  lastDiff: "",
};

const $ = (id) => document.getElementById(id);

const stateMap = {
  idle: "stateIdle",
  draft: "stateDraft",
  planning: "statePlanning",
  planned: "statePlanned",
  running: "stateRunning",
  waiting_approval: "stateApproval",
  completed: "stateDone",
  failed: "stateDone",
};

const labels = {
  toolStatus: { enabled: "активен", disabled: "отключён", internal: "внутренний", stub: "заглушка" },
  stepStatus: {
    pending: "Ожидает",
    running: "Выполняется",
    completed: "Готово",
    failed: "Ошибка",
    skipped: "Пропущено",
    rejected: "Отклонено",
  },
  risk: { low: "Низкий", medium: "Средний", high: "Высокий", critical: "Критический" },
  fileStatus: { added: "добавлен", modified: "изменён", deleted: "удалён" },
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return map[char];
  });
}

function nowTime() {
  return new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text}`);
  }
  return response.json();
}

function showToast(message, type = "error") {
  const toast = $("toast");
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.hidden = false;
  window.setTimeout(() => {
    toast.hidden = true;
  }, 4200);
}

function setBusy(isBusy, label = "") {
  state.isBusy = isBusy;
  $("serverStatus").textContent = isBusy ? label || "Выполняется..." : "Подключено";
  $("serverStatus").className = isBusy ? "text-warning" : "text-success";
  syncButtons();
}

function setUiState(nextState) {
  state.uiState = nextState;
  document.querySelectorAll(".state-step").forEach((item) => item.classList.remove("active"));
  const active = $(stateMap[nextState] || "stateIdle");
  if (active) active.classList.add("active");
  $("taskStatusBadge").textContent = translateTaskState(nextState);
  syncButtons();
}

function syncButtons() {
  const hasText = $("taskInput").value.trim().length > 0;
  const hasTask = Boolean(state.taskId);
  $("sendBtn").disabled = state.isBusy || !hasText;
  $("planBtn").disabled = state.isBusy || !hasText;
  $("runBtn").disabled = state.isBusy || !hasTask || state.uiState === "running";
  $("stopBtn").disabled = state.uiState !== "running";
  $("openReportBtn").disabled = !state.lastReport;
}

function translateTaskState(status) {
  const map = {
    idle: "Нет задачи",
    draft: "Задача введена",
    planning: "План составляется",
    planned: "План готов",
    running: "Выполнение идёт",
    pending_approval: "Ожидается подтверждение",
    waiting_approval: "Ожидается подтверждение",
    completed: "Выполнено",
    failed: "Ошибка",
    rejected: "Отклонено",
  };
  return map[status] || status || "Нет задачи";
}

function renderMessage(role, content, status = "") {
  const row = document.createElement("article");
  row.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  const roleText = role === "user" ? "Вы" : role === "assistant" ? "Агент" : "Система";
  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.innerHTML = `<strong>${escapeHtml(roleText)}</strong><span>${escapeHtml(status || nowTime())}</span>`;
  const body = document.createElement("p");
  body.textContent = content;
  bubble.appendChild(meta);
  bubble.appendChild(body);
  row.appendChild(bubble);
  $("messages").appendChild(row);
  $("messages").scrollTop = $("messages").scrollHeight;
}

function activateSideTab(id) {
  document.querySelectorAll(".side-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.sideTab === id));
  document.querySelectorAll(".side-content").forEach((panel) => panel.classList.toggle("active", panel.id === id));
}

function activateWorkbenchTab(id) {
  document
    .querySelectorAll(".workbench-tab")
    .forEach((tab) => tab.classList.toggle("active", tab.dataset.workbenchTab === id));
  document.querySelectorAll(".workbench-content").forEach((panel) => panel.classList.toggle("active", panel.id === id));
}

async function loadWorkspace() {
  const workspace = await api("/api/workspace");
  $("projectPath").textContent = workspace.project_root;
  $("gitBranch").textContent = workspace.git_branch || "нет ветки";
  $("workspaceCount").textContent = `${workspace.files.length} файлов`;
  renderImportantDirs(workspace.important_directories || []);
  renderChanges(workspace.changed_files || []);
  state.files = workspace.files || [];
  renderFiles(state.files);
  await Promise.all([loadFiles(), loadTools(), loadGlobalDiff()]);
}

async function loadFiles() {
  const data = await api("/api/files");
  state.files = data.files || [];
  $("workspaceCount").textContent = `${data.count} файлов`;
  renderFiles(state.files);
}

function renderImportantDirs(dirs) {
  const box = $("importantDirs");
  box.innerHTML = "";
  if (!dirs.length) {
    box.innerHTML = '<span class="status-pill neutral">Нет ключевых директорий</span>';
    return;
  }
  for (const dir of dirs) {
    const item = document.createElement("button");
    item.className = "dir-chip";
    item.type = "button";
    item.textContent = dir;
    item.onclick = () => {
      $("fileSearchInput").value = dir;
      renderSearchResults(dir);
      activateSideTab("searchPanel");
    };
    box.appendChild(item);
  }
}

function renderFiles(files) {
  const list = $("fileList");
  list.innerHTML = "";
  if (!files.length) {
    list.innerHTML = '<li class="empty">Файлы не найдены.</li>';
    return;
  }
  for (const file of files) {
    list.appendChild(fileListItem(file));
  }
}

function fileListItem(file) {
  const item = document.createElement("li");
  const button = document.createElement("button");
  button.className = "file-button";
  button.type = "button";
  button.innerHTML = `<span>${escapeHtml(file.name)}</span><small>${escapeHtml(file.directory || ".")}</small>`;
  button.onclick = () => previewFile(file.path);
  item.appendChild(button);
  return item;
}

function renderSearchResults(query) {
  const list = $("searchResults");
  const normalized = query.trim().toLowerCase();
  list.innerHTML = "";
  if (!normalized) {
    list.innerHTML = '<li class="empty">Введите часть пути или имени файла.</li>';
    return;
  }
  const matches = state.files.filter((file) => file.path.toLowerCase().includes(normalized)).slice(0, 80);
  if (!matches.length) {
    list.innerHTML = '<li class="empty">Совпадений нет.</li>';
    return;
  }
  for (const file of matches) {
    list.appendChild(fileListItem(file));
  }
}

async function previewFile(path) {
  setBusy(true, "Открывается preview...");
  try {
    const data = await api(`/api/files/preview?path=${encodeURIComponent(path)}`);
    $("terminalOutput").textContent = `Preview: ${data.path}\n\n${data.content}${data.truncated ? "\n\n... файл обрезан" : ""}`;
    activateWorkbenchTab("terminalPanel");
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function loadTools() {
  const data = await api("/api/tools");
  state.tools = data.tools || [];
  renderToolChips();
}

function renderToolChips() {
  const enabled = $("enabledTools");
  const technical = $("technicalTools");
  enabled.innerHTML = "";
  technical.innerHTML = "";
  for (const tool of state.tools) {
    const chip = document.createElement("span");
    chip.className = `tool-chip ${tool.status}`;
    chip.textContent = `${tool.name} · ${labels.toolStatus[tool.status] || tool.status}`;
    if (tool.status === "enabled") enabled.appendChild(chip);
    else technical.appendChild(chip);
  }
  if (!enabled.children.length) enabled.innerHTML = '<span class="muted">Нет активных инструментов.</span>';
  if (!technical.children.length) technical.innerHTML = '<span class="muted">Нет технических инструментов.</span>';
}

function renderChanges(changes) {
  const list = $("workspaceChanges");
  list.innerHTML = "";
  if (!changes.length) {
    list.innerHTML = '<li class="empty">Изменений пока нет.</li>';
    return;
  }
  for (const change of changes) {
    const item = document.createElement("li");
    item.innerHTML = `<span>${escapeHtml(change.path)}</span><strong>${escapeHtml(labels.fileStatus[change.status] || change.status)}</strong>`;
    list.appendChild(item);
  }
}

async function loadGlobalDiff() {
  const data = await api("/api/git/diff");
  state.lastDiff = data.diff || "";
  renderDiff(state.lastDiff);
  renderChanges(data.changed_files || []);
}

function renderDiff(diff) {
  const box = $("diffView");
  box.innerHTML = "";
  if (!diff) {
    box.textContent = "Изменений пока нет.";
    return;
  }
  for (const line of diff.split("\n")) {
    const row = document.createElement("div");
    row.className = "diff-line";
    if (line.startsWith("+") && !line.startsWith("+++")) row.classList.add("added");
    else if (line.startsWith("-") && !line.startsWith("---")) row.classList.add("deleted");
    else if (line.startsWith("@@") || line.startsWith("diff ")) row.classList.add("meta");
    row.textContent = line || " ";
    box.appendChild(row);
  }
}

function renderPlan(plan) {
  const box = $("planCards");
  box.innerHTML = "";
  if (!plan || !plan.steps || !plan.steps.length) {
    box.innerHTML = '<p class="empty">План ещё не составлен.</p>';
    return;
  }
  for (const [index, step] of plan.steps.entries()) {
    const card = document.createElement("article");
    card.className = "step-card";
    const status = labels.stepStatus[step.status] || "Ожидает";
    const risk = labels.risk[step.risk_level] || step.risk_level;
    card.innerHTML = `
      <div class="step-header">
        <span class="step-index">${index + 1}</span>
        <div>
          <strong>${escapeHtml(step.type || "Шаг")}</strong>
          <p>${escapeHtml(step.description)}</p>
        </div>
      </div>
      <div class="step-meta">
        <span class="status-pill neutral">${escapeHtml(step.required_tool)}</span>
        <span class="status-pill ${riskClass(step.risk_level)}">${escapeHtml(risk)}</span>
        <span class="status-pill neutral">${escapeHtml(status)}</span>
        ${step.approval_required ? '<span class="status-pill warning">Требует подтверждение</span>' : ""}
      </div>
    `;
    box.appendChild(card);
  }
  $("currentStep").textContent = plan.steps[0]?.description || "Шаг не выбран.";
  renderRisks(plan.risks || []);
}

function renderRisks(risks) {
  const box = $("riskList");
  box.innerHTML = "";
  if (!risks.length) {
    box.innerHTML = '<span class="status-pill success">Явных рисков нет</span>';
    return;
  }
  for (const risk of risks) {
    const item = document.createElement("span");
    item.className = "status-pill warning";
    item.textContent = risk;
    box.appendChild(item);
  }
}

function riskClass(risk) {
  if (risk === "high" || risk === "critical") return "danger";
  if (risk === "medium") return "warning";
  return "success";
}

function renderApprovals(approvals) {
  const box = $("approvals");
  state.pendingApprovals = approvals || [];
  box.innerHTML = "";
  $("approveLowRiskBtn").disabled = !approvals?.some((approval) => approval.risk === "low");
  if (!approvals || !approvals.length) {
    box.innerHTML = '<p class="empty">Нет действий, ожидающих подтверждения.</p>';
    return;
  }
  for (const approval of approvals) {
    const card = document.createElement("article");
    card.className = "approval-card";
    card.innerHTML = `
      <strong>${escapeHtml(approval.action)}</strong>
      <p>${escapeHtml(approval.description)}</p>
      <span class="status-pill ${riskClass(approval.risk)}">Риск: ${escapeHtml(labels.risk[approval.risk] || approval.risk)}</span>
    `;
    const actions = document.createElement("div");
    actions.className = "approval-actions";
    const approve = document.createElement("button");
    approve.className = "btn success";
    approve.type = "button";
    approve.textContent = "Подтвердить";
    approve.onclick = () => approveStep(approval);
    const reject = document.createElement("button");
    reject.className = "btn danger";
    reject.type = "button";
    reject.textContent = "Отклонить";
    reject.onclick = () => rejectStep(approval);
    actions.appendChild(approve);
    actions.appendChild(reject);
    card.appendChild(actions);
    box.appendChild(card);
  }
}

function renderChecks(data) {
  const errors = data.errors || [];
  const warnings = data.warnings || [];
  $("checksView").innerHTML = `
    <p><strong>Состояние:</strong> ${escapeHtml(translateTaskState(data.status))}</p>
    <p><strong>Ошибки:</strong> ${errors.length ? escapeHtml(errors.join("; ")) : "нет"}</p>
    <p><strong>Предупреждения:</strong> ${warnings.length ? escapeHtml(warnings.join("; ")) : "нет"}</p>
  `;
}

function renderJournal(events) {
  const list = $("journal");
  list.innerHTML = "";
  if (!events || !events.length) {
    list.innerHTML = '<li class="empty">Журнал пуст.</li>';
    return;
  }
  for (const event of events) {
    const item = document.createElement("li");
    item.textContent = `${event.title || translateEvent(event.type)}${event.action ? ` · ${event.action}` : ""}`;
    list.appendChild(item);
  }
}

function translateEvent(type) {
  const map = {
    task_status: "Состояние задачи",
    pending_approval: "Ожидается подтверждение",
    approval_granted: "Действие подтверждено",
    approval_rejected: "Действие отклонено",
    task_started: "Задача запущена",
    task_finished: "Задача завершена",
    step_started: "Шаг запущен",
    step_finished: "Шаг завершён",
    tool_called: "Инструмент вызван",
    tool_finished: "Инструмент завершён",
  };
  return map[type] || type;
}

async function renderTask(data) {
  state.taskId = data.task_id;
  $("taskSummary").textContent = data.plan?.goal || data.task_id || "Текущая задача";
  $("resultSummary").textContent = translateTaskState(data.status);
  renderPlan(data.plan);
  renderApprovals(data.pending_approvals || []);
  renderChecks(data);
  if (data.pending_approvals?.length) setUiState("waiting_approval");
  else if (data.status === "completed") setUiState("completed");
  else if (data.status === "failed") setUiState("failed");
  else if (data.status === "planned") setUiState("planned");
  await loadTimeline();
}

async function sendChat() {
  const message = $("taskInput").value.trim();
  if (!message) return;
  setBusy(true, "Агент готовит ответ...");
  setUiState("draft");
  renderMessage("user", message);
  try {
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, mode: $("mode").value, session_id: state.sessionId }),
    });
    state.sessionId = data.session_id;
    state.taskId = data.task_id;
    renderPlan(data.plan);
    setUiState("planned");
    renderMessage("assistant", data.assistant_response || "План готов.");
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function createPlan(taskOverride = "") {
  const task = taskOverride || $("taskInput").value.trim();
  if (!task) return;
  setBusy(true, "План составляется...");
  setUiState("planning");
  if (!taskOverride) renderMessage("user", task);
  try {
    const data = await api("/api/tasks/plan", {
      method: "POST",
      body: JSON.stringify({ task, mode: $("mode").value }),
    });
    await renderTask(data);
    renderMessage("assistant", `План готов: ${data.plan.steps.length} шаг(ов).`);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function runTask() {
  if (!state.taskId) return;
  setBusy(true, "Выполнение идёт...");
  setUiState("running");
  try {
    const data = await api(`/api/tasks/${state.taskId}/run`, { method: "POST" });
    await renderTask(data);
    await loadReportAndDiff();
    await loadWorkspace();
    if (data.pending_approvals?.length) {
      renderMessage("system", "Есть действия, ожидающие подтверждения.");
    } else {
      renderMessage("assistant", "Выполнение завершено. Проверьте Diff, проверки и отчёт.");
    }
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function approveStep(approval) {
  if (!state.taskId) return;
  setBusy(true, "Подтверждение действия...");
  try {
    const data = await api(`/api/tasks/${state.taskId}/approve`, {
      method: "POST",
      body: JSON.stringify({ step_id: approval.step_id, action: approval.action }),
    });
    await renderTask(data);
    renderMessage("system", `Действие ${approval.action} подтверждено.`);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function rejectStep(approval) {
  if (!state.taskId) return;
  setBusy(true, "Отклонение действия...");
  try {
    const data = await api(`/api/tasks/${state.taskId}/reject`, {
      method: "POST",
      body: JSON.stringify({ step_id: approval.step_id, action: approval.action }),
    });
    await renderTask(data);
    renderMessage("system", `Действие ${approval.action} отклонено.`);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function approveLowRisk() {
  if (!state.taskId) return;
  const lowRisk = state.pendingApprovals.filter((approval) => approval.risk === "low");
  if (!lowRisk.length) return;
  setBusy(true, "Подтверждение низкорисковых действий...");
  try {
    let latest = null;
    for (const approval of lowRisk) {
      latest = await api(`/api/tasks/${state.taskId}/approve`, {
        method: "POST",
        body: JSON.stringify({ step_id: approval.step_id, action: approval.action }),
      });
    }
    if (latest) await renderTask(latest);
    renderMessage("system", `Подтверждено низкорисковых действий: ${lowRisk.length}.`);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function loadTimeline() {
  if (!state.taskId) return;
  const data = await api(`/api/tasks/${state.taskId}/timeline`);
  renderJournal(data.events || []);
}

async function loadReportAndDiff() {
  if (!state.taskId) return;
  const [report, diff] = await Promise.all([
    api(`/api/tasks/${state.taskId}/report`),
    api(`/api/tasks/${state.taskId}/diff`),
  ]);
  state.lastReport = report.report || "";
  state.lastDiff = diff.diff || state.lastDiff || "";
  $("reportView").textContent = state.lastReport || "Отчёт пока не создан.";
  renderDiff(state.lastDiff);
  syncButtons();
}

function handleError(error) {
  const message = error instanceof Error ? error.message : String(error);
  showToast(message);
  renderMessage("system", `Ошибка: ${message}`, "ошибка");
  setUiState("failed");
}

function setupEvents() {
  document.querySelectorAll(".side-tab").forEach((tab) => {
    tab.addEventListener("click", () => activateSideTab(tab.dataset.sideTab));
  });
  document.querySelectorAll(".workbench-tab").forEach((tab) => {
    tab.addEventListener("click", () => activateWorkbenchTab(tab.dataset.workbenchTab));
  });
  $("taskInput").addEventListener("input", () => {
    if (!state.taskId && $("taskInput").value.trim()) setUiState("draft");
    if (!state.taskId && !$("taskInput").value.trim()) setUiState("idle");
    syncButtons();
  });
  $("fileSearchInput").addEventListener("input", (event) => renderSearchResults(event.target.value));
  $("sendBtn").onclick = sendChat;
  $("planBtn").onclick = () => createPlan();
  $("runBtn").onclick = runTask;
  $("refreshBtn").onclick = () => initialize().catch(handleError);
  $("auditBtn").onclick = () => createPlan("Audit this project");
  $("showDiffBtn").onclick = () => activateWorkbenchTab("diffPanel");
  $("openReportBtn").onclick = () => activateWorkbenchTab("reportPanel");
  $("approveLowRiskBtn").onclick = approveLowRisk;
}

async function initialize() {
  setBusy(true, "Загрузка workspace...");
  try {
    await loadWorkspace();
    setUiState(state.taskId ? state.uiState : "idle");
  } finally {
    setBusy(false);
  }
}

setupEvents();
initialize().catch(handleError);
