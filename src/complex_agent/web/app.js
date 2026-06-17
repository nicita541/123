const state = {
  currentProjectRoot: "",
  taskId: null,
  sessionId: null,
  status: "idle",
  proposedDiff: "",
  proposedFiles: [],
  pendingApprovals: [],
  report: "",
  verificationOutput: "",
  workspace: null,
  busy: false,
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
    throw new Error(`${response.status}: ${await response.text()}`);
  }
  return response.json();
}

function toast(message, type = "error") {
  const box = $("toast");
  box.textContent = message;
  box.className = `toast ${type}`;
  box.hidden = false;
  window.setTimeout(() => {
    box.hidden = true;
  }, 4200);
}

function setBusy(busy) {
  state.busy = busy;
  $("sendBtn").disabled = busy || !$("taskInput").value.trim();
  document.querySelectorAll(".card-action, .mini-button, .env-actions button").forEach((button) => {
    if (button.id === "selectProjectBtn" || button.id === "cancelProjectBtn") return;
    if (button.hasAttribute("data-always-enabled")) return;
    button.disabled = busy || button.hasAttribute("data-disabled");
  });
}

function setStatus(status) {
  state.status = status;
  $("envProgress").textContent = translateStatus(status);
}

function translateStatus(status) {
  const map = {
    idle: "Нет задачи",
    planning: "План составляется",
    planned: "План готов",
    proposing_changes: "Предлагаются изменения",
    waiting_approval: "Ожидается подтверждение",
    approved: "Подтверждено",
    running_to_goal: "Выполнение к цели",
    applying_patch: "Применяется patch",
    verifying: "Проверка",
    completed: "Выполнено",
    failed: "Ошибка",
    rejected: "Отклонено",
    pending_approval: "Ожидается подтверждение",
  };
  return map[status] || status;
}

function projectName(path) {
  const normalized = String(path || "").replaceAll("\\", "/").replace(/\/$/, "");
  return normalized.split("/").pop() || "проект";
}

function addHistory(title) {
  const list = $("taskHistory");
  if (list.textContent.includes("Задач пока нет")) list.innerHTML = "";
  const item = document.createElement("li");
  item.innerHTML = `<span>${escapeHtml(title)}</span><small>сейчас</small>`;
  list.prepend(item);
}

function addFeedCard(className, html) {
  $("emptyState").hidden = true;
  const card = document.createElement("article");
  card.className = `feed-card ${className}`;
  card.innerHTML = html;
  $("feed").appendChild(card);
  card.scrollIntoView({ behavior: "smooth", block: "end" });
  return card;
}

function resetChat() {
  state.taskId = null;
  state.sessionId = null;
  state.status = "idle";
  state.proposedDiff = "";
  state.proposedFiles = [];
  state.pendingApprovals = [];
  state.report = "";
  state.verificationOutput = "";
  $("feed").innerHTML = "";
  $("emptyState").hidden = false;
  $("taskInput").value = "";
  setStatus("idle");
  setBusy(false);
}

function renderUserMessage(text) {
  addFeedCard("user-card", `<div class="card-label">Вы</div><p>${escapeHtml(text)}</p>`);
}

function renderSystemEvent(text) {
  addFeedCard("system-card", `<p>${escapeHtml(text)}</p>`);
}

function renderPlan(data) {
  const steps = data.plan.steps
    .map(
      (step, index) => `
        <li>
          <span>${index + 1}</span>
          <div>
            <strong>${escapeHtml(step.description)}</strong>
            <small>${escapeHtml(step.required_tool)} · ${escapeHtml(step.risk_level)} · ${escapeHtml(step.status)}</small>
          </div>
        </li>`
    )
    .join("");
  const risks = (data.plan.risks || [])
    .map((risk) => `<li>${escapeHtml(risk)}</li>`)
    .join("");
  addFeedCard(
    "plan-card",
    `
      <div class="card-label">Агент</div>
      <h3>План выполнения</h3>
      <ol class="plan-list">${steps}</ol>
      ${risks ? `<details><summary>Риски</summary><ul>${risks}</ul></details>` : ""}
      <div class="approval-actions">
        <button id="proposeBtn" class="card-action" type="button">Предложить изменения</button>
        <button id="runGoalBtn" class="card-action secondary" type="button">Запустить цель</button>
      </div>
    `
  );
  $("proposeBtn").onclick = proposeChanges;
  $("runGoalBtn").onclick = runGoal;
}

function renderDiffCard(data) {
  state.proposedDiff = data.proposed_diff || "";
  state.proposedFiles = data.proposed_files || [];
  const files = state.proposedFiles.map((file) => `<li>${escapeHtml(file)}</li>`).join("");
  addFeedCard(
    "diff-card",
    `
      <div class="card-label">Предложены изменения</div>
      <h3>Diff готов к проверке</h3>
      <p>${escapeHtml(data.proposed_summary || "Patch готов к проверке.")}</p>
      <p class="muted">Изменено ${state.proposedFiles.length} файл(ов)</p>
      <ul class="changed-files">${files}</ul>
      <details>
        <summary>Показать Diff</summary>
        <pre class="diff-code">${escapeHtml(state.proposedDiff || "Изменений пока нет.")}</pre>
      </details>
    `
  );
}

function renderApprovalCard(data) {
  state.pendingApprovals = data.pending_approvals || [];
  if (!state.pendingApprovals.length) return;
  const approval = state.pendingApprovals[0];
  addFeedCard(
    "approval-card",
    `
      <div class="card-label">Подтверждение</div>
      <h3>Разрешить изменение файлов?</h3>
      <p>${escapeHtml(approval.description)}</p>
      <p class="muted">Цель: ${escapeHtml(approval.target || state.proposedFiles.join(", "))}</p>
      <div class="approval-actions">
        <button id="approveBtn" class="card-action" type="button">Подтвердить</button>
        <button id="rejectBtn" class="card-action secondary" type="button">Отклонить</button>
      </div>
    `
  );
  $("approveBtn").onclick = () => approve(approval);
  $("rejectBtn").onclick = () => reject(approval);
}

function renderRunResult(data) {
  const files = (data.proposed_files || data.changed_files || [])
    .map((file) => `<li>${escapeHtml(file)}</li>`)
    .join("");
  const verification = data.verification_output || "Проверка не запускалась.";
  addFeedCard(
    "result-card",
    `
      <div class="card-label">${data.status === "completed" ? "Готово" : "Ошибка"}</div>
      <h3>${data.status === "completed" ? "Задача выполнена" : "Есть ошибка"}</h3>
      <p>${data.status === "completed" ? "✓ Patch применён · ✓ Проверка прошла" : "Проверьте детали ниже"}</p>
      <h4>Изменённые файлы</h4>
      <ul class="changed-files">${files || "<li>Нет</li>"}</ul>
      <details>
        <summary>Логи команд</summary>
        <pre>${escapeHtml(verification)}</pre>
      </details>
      <details open>
        <summary>Финальный отчёт</summary>
        <pre>${escapeHtml(data.final_report || "Отчёт пока не создан.")}</pre>
      </details>
    `
  );
}

function renderFailure(data) {
  const detail = (data.events || []).at(-1)?.detail || "Для этой задачи нужна локальная модель Ollama. Сейчас она недоступна.";
  addFeedCard(
    "system-card",
    `
      <div class="card-label">Не удалось продолжить</div>
      <p>${escapeHtml(detail)}</p>
    `
  );
}

async function loadStatus() {
  const [project, status, workspace] = await Promise.all([
    api("/api/project"),
    api("/api/status"),
    api("/api/workspace"),
  ]);
  state.currentProjectRoot = project.project_root;
  state.workspace = workspace;
  $("projectPath").textContent = project.project_root;
  $("projectInput").value = project.project_root;
  $("projectName").textContent = projectName(project.project_root);
  $("envProject").textContent = project.project_root;
  $("envBranch").textContent = workspace.git_branch || "нет ветки";
  $("envChanges").textContent = `${workspace.changed_files.length} файлов`;
  $("envProvider").textContent = status.llm_provider === "ollama" ? "Ollama" : status.llm_provider || "deterministic";
  $("envModel").textContent = status.ollama_model ? status.ollama_model : "deterministic fallback";
  if (status.ollama_reachable && status.ollama_generation_check) {
    $("envModelStatus").textContent = "Подключено";
  } else if (status.ollama_reachable) {
    $("envModelStatus").textContent = "Ollama отвечает · generation_check failed";
  } else {
    $("envModelStatus").textContent = "Ollama недоступен · deterministic fallback";
  }
  const models = status.ollama_models || [];
  if (status.ollama_reachable && models.length) {
    $("agentSelector").innerHTML = models
      .map((model) => {
        const selected = model === status.ollama_model ? " selected" : "";
        return `<option${selected}>Ollama · ${escapeHtml(model)}</option>`;
      })
      .join("");
  } else {
    $("agentSelector").innerHTML = "<option>Локальный агент</option>";
  }
  $("envSources").innerHTML =
    (workspace.files || [])
      .slice(0, 4)
      .map((file) => `<li>${escapeHtml(file.path)}</li>`)
      .join("") || "<li>Источников пока нет</li>";
}

async function selectProject(event) {
  event.preventDefault();
  const path = $("projectInput").value.trim();
  if (!path) return;
  setBusy(true);
  try {
    await api("/api/project/select", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
    $("projectForm").hidden = true;
    resetChat();
    await loadStatus();
    toast("Рабочая папка выбрана", "success");
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function submitTask(taskOverride = "") {
  const task = taskOverride || $("taskInput").value.trim();
  if (!task) return;
  $("taskInput").value = "";
  setBusy(true);
  setStatus("planning");
  renderUserMessage(task);
  addHistory(task);
  try {
    const data = await api("/api/tasks/plan", {
      method: "POST",
      body: JSON.stringify({ task, mode: $("mode").value }),
    });
    state.taskId = data.task_id;
    setStatus(data.status);
    renderPlan(data);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function proposeChanges() {
  if (!state.taskId) return;
  setBusy(true);
  setStatus("proposing_changes");
  try {
    const data = await api(`/api/tasks/${state.taskId}/propose`, { method: "POST" });
    setStatus(data.status);
    if (data.status === "failed") {
      renderFailure(data);
      return;
    }
    renderDiffCard(data);
    renderApprovalCard(data);
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function runGoal() {
  if (!state.taskId) {
    await submitTask();
    return;
  }
  if (state.status === "planned") {
    await proposeChanges();
    return;
  }
  if (state.status === "waiting_approval") {
    renderSystemEvent("Нужно подтвердить предложенный Diff перед записью файлов.");
    return;
  }
  await runTask();
}

async function approve(approval) {
  if (!state.taskId) return;
  setBusy(true);
  try {
    const data = await api(`/api/tasks/${state.taskId}/approve`, {
      method: "POST",
      body: JSON.stringify({ step_id: approval.step_id, action: approval.action }),
    });
    setStatus(data.status);
    renderSystemEvent("Изменение подтверждено. Запускаю применение patch и проверку.");
    await runTask();
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function reject(approval) {
  if (!state.taskId) return;
  setBusy(true);
  try {
    const data = await api(`/api/tasks/${state.taskId}/reject`, {
      method: "POST",
      body: JSON.stringify({ step_id: approval.step_id, action: approval.action }),
    });
    setStatus(data.status);
    renderSystemEvent("Изменение отклонено. Файлы не изменены.");
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function runTask() {
  if (!state.taskId) return;
  setStatus("running_to_goal");
  try {
    const data = await api(`/api/tasks/${state.taskId}/run`, { method: "POST" });
    setStatus(data.status);
    if (data.pending_approvals && data.pending_approvals.length) {
      renderApprovalCard(data);
      return;
    }
    renderRunResult(data);
    await loadStatus();
  } catch (error) {
    handleError(error);
  }
}

function showCurrentDiff() {
  if (state.proposedDiff) {
    addFeedCard("diff-card", `<h3>Diff</h3><pre class="diff-code">${escapeHtml(state.proposedDiff)}</pre>`);
  } else {
    renderSystemEvent("Diff пока не создан.");
  }
}

function handleError(error) {
  const message = error instanceof Error ? error.message : String(error);
  toast(message);
  setStatus("failed");
  renderSystemEvent(`Ошибка: ${message}`);
}

function setupEvents() {
  $("taskInput").addEventListener("input", () => {
    $("sendBtn").disabled = state.busy || !$("taskInput").value.trim();
  });
  $("taskInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitTask();
    }
  });
  $("sendBtn").onclick = () => submitTask();
  $("newChatBtn").onclick = resetChat;
  $("refreshBtn").onclick = () => loadStatus().catch(handleError);
  $("envCheckBtn").onclick = () => submitTask("Проведи аудит проекта");
  $("envDiffBtn").onclick = showCurrentDiff;
  $("commitBtn").onclick = () => renderSystemEvent("Создание commit отключено в MVP.");
  $("chooseProjectBtn").onclick = () => {
    $("projectForm").hidden = false;
    $("projectInput").focus();
  };
  $("projectForm").onsubmit = selectProject;
  $("cancelProjectBtn").onclick = () => {
    $("projectForm").hidden = true;
  };
  $("settingsBtn").onclick = () => renderSystemEvent("Настройки пока ограничены выбором рабочей папки и режима доступа.");
  document.querySelectorAll(".quick-prompts button").forEach((button) => {
    button.onclick = () => submitTask(button.textContent || "");
  });
}

setupEvents();
setStatus("idle");
loadStatus().catch(handleError);
