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

$$('.ranking-toggle button').forEach((button) => button.addEventListener('click', () => {
  $$('.ranking-toggle button').forEach((item) => {
    const active = item === button;
    item.classList.toggle('is-active', active);
    item.setAttribute('aria-pressed', String(active));
  });
  $$('[data-ranking-view-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.rankingViewPanel !== button.dataset.rankingView;
  });
}));

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
