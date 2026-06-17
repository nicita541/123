const state = {
  taskId: null,
  sessionId: null,
  uiState: "idle",
  lastReport: "",
  lastDiff: "",
  isBusy: false,
  tools: [],
};

const $ = (id) => document.getElementById(id);

const labels = {
  mode: { plan: "Планирование", review: "Обзор", dev: "Разработка" },
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
};

const workflowMap = {
  idle: "wfIdle",
  message_sent: "wfIdle",
  planned: "wfPlanned",
  running: "wfRun",
  waiting_approval: "wfApproval",
  completed: "wfDone",
  failed: "wfDone",
};

function nowTime() {
  return new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return map[char];
  });
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

function setBusy(isBusy, message = "") {
  state.isBusy = isBusy;
  $("backendStatus").textContent = isBusy ? message || "Выполняется..." : "Подключено";
  $("backendStatus").className = isBusy ? "status-warn" : "status-ok";
  syncButtons();
}

function setUiState(nextState) {
  state.uiState = nextState;
  for (const item of document.querySelectorAll(".workflow-step")) item.classList.remove("active");
  const active = $(workflowMap[nextState] || "wfIdle");
  if (active) active.classList.add("active");
  syncButtons();
}

function syncButtons() {
  const hasText = $("taskInput").value.trim().length > 0;
  const hasPlan = Boolean(state.taskId);
  $("sendBtn").disabled = state.isBusy || !hasText;
  $("planBtn").disabled = state.isBusy || !hasText;
  $("runBtn").disabled = state.isBusy || !hasPlan || state.uiState === "running";
  $("abortBtn").disabled = state.uiState !== "running";
  $("openReportBtn").disabled = !state.lastReport;
}

function renderMessage(role, content, status = "") {
  const row = document.createElement("div");
  row.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  const header = document.createElement("div");
  header.className = "message-head";
  const roleText = role === "user" ? "Вы" : role === "assistant" ? "Агент" : "Система";
  header.innerHTML = `<span class="message-role">${roleText}</span><span>${status || nowTime()}</span>`;
  const body = document.createElement("p");
  body.textContent = content;
  bubble.appendChild(header);
  bubble.appendChild(body);
  row.appendChild(bubble);
  $("messages").appendChild(row);
  $("messages").scrollTop = $("messages").scrollHeight;
}

function renderPlan(plan) {
  const box = $("plan");
  box.innerHTML = "";
  if (!plan || !plan.steps || plan.steps.length === 0) {
    box.innerHTML = '<p class="empty">План ещё не создан.</p>';
    return;
  }
  plan.steps.forEach((step, index) => {
    const card = document.createElement("article");
    card.className = "step-card";
    const status = labels.stepStatus[step.status] || "Ожидает";
    const risk = labels.risk[step.risk_level] || step.risk_level;
    card.innerHTML = `
      <div class="step-top">
        <span class="step-number">${index + 1}</span>
        <div>
          <strong>${escapeHtml(step.type || "Шаг")}</strong>
          <p>${escapeHtml(step.description)}</p>
        </div>
      </div>
      <div class="step-meta">
        <span class="chip">${escapeHtml(step.required_tool)}</span>
        <span class="badge neutral">${escapeHtml(status)}</span>
        <span class="badge ${riskClass(step.risk_level)}">Риск: ${escapeHtml(risk)}</span>
        ${step.approval_required ? '<span class="badge warn">Требует подтверждения</span>' : ""}
      </div>
    `;
    box.appendChild(card);
  });
}

function riskClass(risk) {
  if (risk === "high" || risk === "critical") return "danger";
  if (risk === "medium") return "warn";
  return "success";
}

function renderApprovals(items) {
  const box = $("approvals");
  box.innerHTML = "";
  if (!items || items.length === 0) {
    box.innerHTML = '<p class="empty">Нет действий, ожидающих подтверждения.</p>';
    return;
  }
  for (const approval of items) {
    const card = document.createElement("article");
    card.className = "approval-card";
    card.innerHTML = `
      <div>
        <strong>${escapeHtml(approval.action)}</strong>
        <p>${escapeHtml(approval.description)}</p>
        <span class="badge ${riskClass(approval.risk)}">Риск: ${escapeHtml(labels.risk[approval.risk] || approval.risk)}</span>
      </div>
    `;
    const actions = document.createElement("div");
    actions.className = "approval-actions";
    const approve = document.createElement("button");
    approve.className = "btn success";
    approve.textContent = "Подтвердить";
    approve.disabled = state.uiState !== "waiting_approval";
    approve.onclick = () => approveStep(approval);
    const reject = document.createElement("button");
    reject.className = "btn danger";
    reject.textContent = "Отклонить";
    reject.disabled = state.uiState !== "waiting_approval";
    reject.onclick = () => rejectStep(approval);
    actions.appendChild(approve);
    actions.appendChild(reject);
    card.appendChild(actions);
    box.appendChild(card);
  }
}

function renderEvents(items) {
  const list = $("events");
  list.innerHTML = "";
  if (!items || items.length === 0) {
    list.innerHTML = '<li class="empty">Событий пока нет.</li>';
    return;
  }
  for (const event of items) {
    const item = document.createElement("li");
    const type = translateEvent(event.type || "event");
    const details = event.step_id ? `, шаг ${event.step_id}` : "";
    item.textContent = `${type}${details}`;
    list.appendChild(item);
  }
}

function translateEvent(type) {
  const map = {
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

function renderChecks(data) {
  const box = $("verifier");
  const errors = data.errors || [];
  const warnings = data.warnings || [];
  const status = translateState(data.status);
  box.innerHTML = `
    <p><strong>Статус:</strong> ${escapeHtml(status)}</p>
    <p><strong>Ошибки:</strong> ${errors.length ? escapeHtml(errors.join("; ")) : "нет"}</p>
    <p><strong>Предупреждения:</strong> ${warnings.length ? escapeHtml(warnings.join("; ")) : "нет"}</p>
  `;
}

function renderChangedFiles(files) {
  const list = $("changedFiles");
  list.innerHTML = "";
  if (!files || files.length === 0) {
    list.innerHTML = '<li class="empty">Изменённых файлов пока нет.</li>';
    return;
  }
  for (const file of files) {
    const item = document.createElement("li");
    item.textContent = file;
    list.appendChild(item);
  }
}

function translateState(status) {
  const map = {
    idle: "Нет задачи",
    message_sent: "Сообщение отправлено",
    planned: "План создан",
    running: "Выполняется",
    pending_approval: "Ожидает подтверждения",
    waiting_approval: "Ожидает подтверждения",
    completed: "Выполнение завершено",
    failed: "Есть ошибки",
    rejected: "Отклонено",
  };
  return map[status] || status || "Нет задачи";
}

function renderTask(data) {
  state.taskId = data.task_id;
  renderPlan(data.plan);
  renderApprovals(data.pending_approvals);
  renderEvents(data.events);
  renderChecks(data);
  renderChangedFiles(data.changed_files);
  $("taskStatusBadge").textContent = translateState(data.status);
  $("resultSummary").textContent = translateState(data.status);
  $("lastTask").textContent = data.plan?.goal || data.task_id || "Нет";
  if (data.pending_approvals && data.pending_approvals.length > 0) setUiState("waiting_approval");
  else if (data.status === "completed") setUiState("completed");
  else if (data.status === "failed") setUiState("failed");
  else if (data.status === "planned") setUiState("planned");
  syncButtons();
}

async function loadStatus() {
  const status = await api("/api/status");
  $("projectPath").textContent = status.project_root;
  $("projectPathShort").textContent = status.project_root;
  $("toolCount").textContent = `${status.tool_count} активных`;
  $("backendStatus").textContent = "Подключено";
  $("backendStatus").className = "status-ok";
  if (status.latest_run) $("lastTask").textContent = status.latest_run.goal || "Есть завершённая задача";
}

async function loadTools() {
  const data = await api("/api/tools");
  state.tools = data.tools || [];
  const enabled = state.tools.filter((tool) => tool.status === "enabled");
  const technical = state.tools.filter((tool) => tool.status !== "enabled");
  renderToolChips("enabledTools", enabled);
  renderToolChips("technicalTools", technical);
}

function renderToolChips(id, tools) {
  const box = $(id);
  box.innerHTML = "";
  if (tools.length === 0) {
    box.innerHTML = '<span class="chip muted">Нет</span>';
    return;
  }
  for (const tool of tools) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = `${tool.name} · ${labels.toolStatus[tool.status] || tool.status}`;
    box.appendChild(chip);
  }
}

async function createPlan() {
  const task = $("taskInput").value.trim();
  if (!task) return;
  setBusy(true, "Агент составляет план...");
  setUiState("message_sent");
  renderMessage("user", task);
  try {
    const data = await api("/api/tasks/plan", {
      method: "POST",
      body: JSON.stringify({ task, mode: $("mode").value }),
    });
    renderTask(data);
    renderMessage("assistant", `План создан: ${data.plan.steps.length} шаг(ов).`);
    addTaskLink(data.task_id, data.plan.goal);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function sendChat() {
  const message = $("taskInput").value.trim();
  if (!message) return;
  setBusy(true, "Агент готовит ответ...");
  setUiState("message_sent");
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
    addTaskLink(data.task_id, data.plan.goal);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function runTask() {
  if (!state.taskId) return;
  setBusy(true, "Агент выполняет шаги...");
  setUiState("running");
  try {
    const data = await api(`/api/tasks/${state.taskId}/run`, { method: "POST" });
    renderTask(data);
    await loadReportAndDiff();
    if (data.pending_approvals && data.pending_approvals.length > 0) {
      renderMessage("system", "Есть действия, ожидающие подтверждения.");
    } else {
      renderMessage("assistant", "Выполнение завершено. Проверьте отчёт и различия.");
    }
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function approveStep(approval) {
  setBusy(true, "Подтверждение действия...");
  try {
    const data = await api(`/api/tasks/${state.taskId}/approve`, {
      method: "POST",
      body: JSON.stringify({ step_id: approval.step_id, action: approval.action }),
    });
    renderTask(data);
    renderMessage("system", `Действие ${approval.action} подтверждено.`);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function rejectStep(approval) {
  setBusy(true, "Отклонение действия...");
  try {
    const data = await api(`/api/tasks/${state.taskId}/reject`, {
      method: "POST",
      body: JSON.stringify({ step_id: approval.step_id, action: approval.action }),
    });
    renderTask(data);
    renderMessage("system", `Действие ${approval.action} отклонено.`);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function loadReportAndDiff() {
  if (!state.taskId) return;
  const report = await api(`/api/tasks/${state.taskId}/report`);
  const diff = await api(`/api/tasks/${state.taskId}/diff`);
  state.lastReport = report.report || "";
  state.lastDiff = diff.diff || "";
  $("report").textContent = state.lastReport || "Итоговый отчёт пока не создан.";
  $("diff").textContent = state.lastDiff || "Изменений пока нет.";
  syncButtons();
}

function addTaskLink(taskId, title) {
  const list = $("tasks");
  if (list.querySelector(".empty")) list.innerHTML = "";
  const item = document.createElement("li");
  item.textContent = `${title || "Задача"} · ${taskId.slice(0, 12)}`;
  list.prepend(item);
}

function handleError(error) {
  const message = error instanceof Error ? error.message : String(error);
  showToast(message);
  renderMessage("system", `Ошибка: ${message}`, "ошибка");
  setUiState("failed");
}

function setupTabs() {
  for (const tab of document.querySelectorAll(".tab")) {
    tab.addEventListener("click", () => {
      for (const item of document.querySelectorAll(".tab")) item.classList.remove("active");
      for (const content of document.querySelectorAll(".tab-content")) content.classList.remove("active");
      tab.classList.add("active");
      $(tab.dataset.tab).classList.add("active");
    });
  }
}

function setupToggles() {
  $("toolsToggle").onclick = () => {
    const body = $("toolsBody");
    body.hidden = !body.hidden;
    $("toolsToggleText").textContent = body.hidden ? "показать" : "скрыть";
  };
  $("technicalToggle").onclick = () => {
    const box = $("technicalTools");
    box.hidden = !box.hidden;
    $("technicalToggle").textContent = box.hidden ? "Показать технические" : "Скрыть технические";
  };
  $("openReportBtn").onclick = () => {
    document.querySelector('[data-tab="reportTab"]').click();
    document.getElementById("reportTab").scrollIntoView({ behavior: "smooth" });
  };
  $("refreshBtn").onclick = () => initialize().catch(handleError);
  $("taskInput").addEventListener("input", syncButtons);
}

async function initialize() {
  setUiState(state.taskId ? state.uiState : "idle");
  await loadStatus();
  await loadTools();
  syncButtons();
}

$("sendBtn").onclick = sendChat;
$("planBtn").onclick = createPlan;
$("runBtn").onclick = runTask;

setupTabs();
setupToggles();
initialize().catch(handleError);
