const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  setTimeout(() => element.classList.remove("show"), 2200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options,
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Request failed");
  return body;
}

$$('.tab').forEach((button) => button.addEventListener('click', () => {
  $$('.tab').forEach((item) => item.classList.toggle('is-active', item === button));
  $$('.panel').forEach((panel) => panel.classList.toggle('is-active', panel.dataset.panel === button.dataset.tab));
  history.replaceState(null, '', `#${button.dataset.tab}`);
}));

const initialTab = location.hash.slice(1);
if (["today", "time", "money"].includes(initialTab)) $(`.tab[data-tab="${initialTab}"]`).click();

$("#show-task-form").addEventListener("click", () => {
  const form = $("#task-form");
  form.hidden = !form.hidden;
  if (!form.hidden) form.title.focus();
});

$("#task-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  const payload = Object.fromEntries(data.entries());
  if (!payload.estimated_minutes) delete payload.estimated_minutes;
  try {
    await api("/api/v1/tasks", {method: "POST", body: JSON.stringify(payload)});
    location.reload();
  } catch (error) { toast(error.message); }
});

$("#task-list").addEventListener("click", async (event) => {
  const button = event.target.closest(".task-check");
  if (!button) return;
  const row = button.closest("li[data-task-id]");
  try {
    await api(`/api/v1/tasks/${row.dataset.taskId}`, {method: "PATCH", body: JSON.stringify({status: "done"})});
    row.remove();
    toast("Action completed");
  } catch (error) { toast(error.message); }
});

const dialog = $("#focus-dialog");
$("#edit-focus").addEventListener("click", () => dialog.showModal());
$("#save-focus").addEventListener("click", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData($("#focus-form")).entries());
  try {
    await api(`/api/v1/today/${window.LIFEOS_DATE}`, {method: "PUT", body: JSON.stringify(data)});
    location.reload();
  } catch (error) { toast(error.message); }
});

$$('.commit-proposal').forEach((button) => button.addEventListener('click', async () => {
  button.disabled = true;
  button.textContent = "Committing…";
  try {
    await api(`/api/v1/${button.dataset.kind}/proposals/${button.dataset.id}/commit`, {method: "POST", body: "{}"});
    location.reload();
  } catch (error) {
    button.disabled = false;
    button.textContent = "Confirm & commit";
    toast(error.message);
  }
}));
