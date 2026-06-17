const state = {
  taskId: null,
  sessionId: null,
  status: "idle",
  proposedDiff: "",
  proposedFiles: [],
  pendingApprovals: [],
  report: "",
  verificationOutput: "",
  workspace: null,
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

function setStatus(status) {
  state.status = status;
  $("envProgress").textContent = translateStatus(status);
}

function translateStatus(status) {
  const map = {
    idle: "Нет задачи",
    planning: "Планирование",
    planned: "План готов",
    proposing_changes: "Предлагаются изменения",
    waiting_approval: "Ожидается подтверждение",
    approved: "Подтверждено",
    applying_patch: "Применяется patch",
    verifying: "Проверка",
    completed: "Готово",
    failed: "Ошибка",
    rejected: "Отклонено",
  };
  return map[status] || status;
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

function renderUserMessage(text) {
  addFeedCard(
    "user-card",
    `<div class="card-label">Вы</div><p>${escapeHtml(text)}</p>`
  );
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
  addFeedCard(
    "plan-card",
    `
      <div class="card-label">Агент</div>
      <h3>План выполнения</h3>
      <ol class="plan-list">${steps}</ol>
      <button id="proposeBtn" class="card-action" type="button">Предложить изменения</button>
    `
  );
  $("proposeBtn").onclick = proposeChanges;
}

function renderDiffCard(data) {
  state.proposedDiff = data.proposed_diff || "";
  state.proposedFiles = data.proposed_files || [];
  const files = state.proposedFiles.map((file) => `<li>${escapeHtml(file)}</li>`).join("");
  addFeedCard(
    "diff-card",
    `
      <div class="card-label">Предложены изменения</div>
      <h3>Proposed diff</h3>
      <p>${escapeHtml(data.proposed_summary || "Patch готов к проверке.")}</p>
      <ul class="changed-files">${files}</ul>
      <details>
        <summary>Показать diff</summary>
        <pre class="diff-code">${renderDiffLines(state.proposedDiff)}</pre>
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

function renderDiffLines(diff) {
  if (!diff) return "Изменений пока нет.";
  return escapeHtml(diff);
}

function renderRunResult(data) {
  const files = (data.proposed_files || data.changed_files || [])
    .map((file) => `<li>${escapeHtml(file)}</li>`)
    .join("");
  const verification = data.verification_output || "Проверка не запускалась.";
  addFeedCard(
    "result-card",
    `
      <div class="card-label">Готово</div>
      <h3>${data.status === "completed" ? "Задача выполнена" : "Есть ошибка"}</h3>
      <h4>Изменённые файлы</h4>
      <ul class="changed-files">${files || "<li>Нет</li>"}</ul>
      <details open>
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

async function loadStatus() {
  const [status, workspace] = await Promise.all([api("/api/status"), api("/api/workspace")]);
  state.workspace = workspace;
  $("projectPath").textContent = workspace.project_root;
  $("envBranch").textContent = workspace.git_branch || "нет ветки";
  $("envChanges").textContent = `${workspace.changed_files.length} файлов`;
  $("envProvider").textContent = status.llm_provider || "deterministic";
  $("envModel").textContent = status.ollama_model ? `Ollama · ${status.ollama_model}` : "deterministic";
  $("envModelStatus").textContent = status.ollama_reachable
    ? "Подключено"
    : "Ollama недоступен · deterministic fallback";
  $("envSources").innerHTML = (workspace.files || [])
    .slice(0, 4)
    .map((file) => `<li>${escapeHtml(file.path)}</li>`)
    .join("") || "<li>Источников пока нет</li>";
}

async function submitTask(taskOverride = "") {
  const task = taskOverride || $("taskInput").value.trim();
  if (!task) return;
  $("taskInput").value = "";
  $("sendBtn").disabled = true;
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
  }
}

async function proposeChanges() {
  if (!state.taskId) return;
  setStatus("proposing_changes");
  try {
    const data = await api(`/api/tasks/${state.taskId}/propose`, { method: "POST" });
    setStatus(data.status);
    if (data.status === "failed") {
      renderSystemEvent((data.events || []).at(-1)?.detail || "Не удалось предложить изменения.");
      return;
    }
    renderDiffCard(data);
    renderApprovalCard(data);
  } catch (error) {
    handleError(error);
  }
}

async function approve(approval) {
  if (!state.taskId) return;
  try {
    const data = await api(`/api/tasks/${state.taskId}/approve`, {
      method: "POST",
      body: JSON.stringify({ step_id: approval.step_id, action: approval.action }),
    });
    setStatus(data.status);
    renderSystemEvent("Изменение подтверждено. Запускаю применение patch и self-test.");
    await runTask();
  } catch (error) {
    handleError(error);
  }
}

async function reject(approval) {
  if (!state.taskId) return;
  try {
    const data = await api(`/api/tasks/${state.taskId}/reject`, {
      method: "POST",
      body: JSON.stringify({ step_id: approval.step_id, action: approval.action }),
    });
    setStatus(data.status);
    renderSystemEvent("Изменение отклонено. Файлы не изменены.");
  } catch (error) {
    handleError(error);
  }
}

async function runTask() {
  if (!state.taskId) return;
  setStatus("applying_patch");
  try {
    const data = await api(`/api/tasks/${state.taskId}/run`, { method: "POST" });
    setStatus(data.status);
    renderRunResult(data);
    await loadStatus();
  } catch (error) {
    handleError(error);
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
    $("sendBtn").disabled = !$("taskInput").value.trim();
  });
  $("taskInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitTask();
    }
  });
  $("sendBtn").onclick = () => submitTask();
  $("newChatBtn").onclick = () => window.location.reload();
  $("refreshBtn").onclick = () => loadStatus().catch(handleError);
  $("envCheckBtn").onclick = () => submitTask("Проведи аудит проекта");
  $("envDiffBtn").onclick = () => {
    if (state.proposedDiff) {
      addFeedCard("diff-card", `<h3>Diff</h3><pre class="diff-code">${renderDiffLines(state.proposedDiff)}</pre>`);
    } else {
      renderSystemEvent("Diff пока не создан.");
    }
  };
  document.querySelectorAll(".quick-prompts button").forEach((button) => {
    button.onclick = () => submitTask(button.textContent || "");
  });
}

setupEvents();
loadStatus().catch(handleError);
