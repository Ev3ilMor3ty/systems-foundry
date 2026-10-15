import {
  metrics,
  canDispatch,
  formatTick,
  routePoints,
  pointAlong,
  visibleTasks,
  acceptSnapshot,
} from "./ui-model.mjs";
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
let state = null,
  filter = "queued",
  busy = false,
  autoplay = false,
  autoTimer = null,
  toastTimer = null;
let observed = [];
const names = { cargo: "Cargo", cold: "Cold chain", fragile: "Fragile" };
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}
function svg(tag, attrs = {}, text) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
}
function status(connected) {
  const n = $("connection");
  n.replaceChildren(
    el("i", `dot ${connected ? "cyan-dot" : "amber-dot"}`),
    document.createTextNode(connected ? "Connected" : "Reconnecting"),
  );
}
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), 4200);
}
function showError(message) {
  $("error-banner").textContent = message;
  $("error-banner").hidden = !message;
}
function setBusy(value) {
  busy = value;
  for (const id of ["optimize", "step", "reset", "new-request"])
    $(id).disabled = value || !state;
}
function renderMap(s) {
  const routes = $("routes"),
    sites = $("sites"),
    carriers = $("carriers");
  routes.replaceChildren();
  sites.replaceChildren();
  carriers.replaceChildren();
  for (const task of s.tasks.filter((t) => t.status === "active")) {
    const pts = routePoints(s, task);
    const d = pts.map((p, i) => `${i ? "L" : "M"}${p.x} ${p.y}`).join(" ");
    routes.append(svg("path", { d, class: `route-path ${task.skill}` }));
  }
  for (const site of s.sites) {
    const x = site.x * 10,
      y = site.y * 5.8,
      g = svg("g", { transform: `translate(${x} ${y})` });
    g.append(
      svg("circle", { r: 14, class: "site-ring" }),
      svg("rect", {
        x: -3,
        y: -3,
        width: 6,
        height: 6,
        rx: 1,
        class: "site-core",
      }),
      svg(
        "text",
        { x: 0, y: 31, "text-anchor": "middle", class: "site-label" },
        site.label,
      ),
      svg(
        "text",
        { x: 0, y: 44, "text-anchor": "middle", class: "site-id" },
        site.id.toUpperCase(),
      ),
    );
    sites.append(g);
  }
  for (const [i, r] of s.resources.entries()) {
    let p;
    const task = s.tasks.find((t) => t.id === r.taskId);
    if (task)
      p = pointAlong(routePoints(s, task), 1 - task.remaining / task.duration);
    else {
      const site = s.sites.find((site) => site.id === r.site);
      p = {
        x: site.x * 10 + 21 + (i % 2) * 9,
        y: site.y * 5.8 - 15 - (i % 3) * 5,
      };
    }
    const g = svg("g", { transform: `translate(${p.x} ${p.y})` });
    g.append(
      svg("circle", { r: 12, class: "carrier-halo" }),
      svg("circle", { r: 5, class: "carrier-dot" }),
      svg("text", { x: 11, y: 3, class: "carrier-code" }, r.id),
    );
    carriers.append(g);
  }
  const strip = $("carrier-strip");
  strip.replaceChildren();
  for (const r of s.resources) {
    const card = el("div", "carrier-card"),
      row = el("div");
    row.append(
      el("span", "", r.name),
      el("i", `dot ${r.taskId ? "cyan-dot" : "muted"}`),
    );
    card.append(
      row,
      el("small", "", r.taskId ? `↗ ${r.taskId}` : "Available"),
    );
    strip.append(card);
  }
}
function renderTable(s) {
  const rows = $("request-rows");
  rows.replaceChildren();
  const tasks = visibleTasks(s, filter);
  const siteName = (id) => s.sites.find((x) => x.id === id)?.label ?? id;
  for (const t of tasks) {
    const tr = el("tr"),
      label = el("td", "", t.label);
    label.append(el("small", "", t.id));
    const route = el("td");
    route.append(
      document.createTextNode(siteName(t.from)),
      el("span", "route-arrow", "→"),
      document.createTextNode(siteName(t.to)),
    );
    const capability = el("td");
    capability.append(el("span", `skill-badge ${t.skill}`, names[t.skill]));
    const priority = el("td"),
      p = el("span", `priority ${t.priority === 3 ? "urgent" : ""}`);
    p.append(
      el("i"),
      document.createTextNode(
        ["", "Standard", "Elevated", "Urgent"][t.priority],
      ),
    );
    priority.append(p);
    const status = el("td");
    status.append(
      el(
        "span",
        `status-tag ${t.status}`,
        t.status === "active"
          ? `${t.remaining} ticks left`
          : t.status === "done"
            ? "Delivered"
            : "Waiting",
      ),
    );
    tr.append(label, route, capability, priority, status);
    rows.append(tr);
  }
  $("empty-queue").hidden = tasks.length > 0;
  $("table-summary").textContent =
    `${tasks.length} ${filter} / ${s.tasks.length} total requests`;
  $("queue-badge").textContent = s.tasks.length;
}
function render(s) {
  if (!acceptSnapshot(state, s)) return;
  if (state && s.tick < state.tick) observed = [];
  state = s;
  showError("");
  const m = metrics(s);
  $("queued-count").textContent = m.queued;
  $("active-count").textContent = m.active;
  $("done-count").textContent = m.done;
  $("urgent-count").textContent = `${m.urgent} urgent · ready for dispatch`;
  $("carrier-availability").textContent =
    `${m.idle} of ${s.resources.length} carriers available`;
  $("clock").textContent = formatTick(s.tick);
  $("revision").textContent = `Revision ${s.revision} · durable events`;
  const previous = observed.at(-1);
  if (!previous || previous[0] !== s.revision) {
    observed.push([s.revision, m.done]);
    if (observed.length > 24) observed.shift();
  }
  const max = Math.max(1, ...observed.map((x) => x[1]));
  $("throughput").firstElementChild.setAttribute(
    "d",
    observed
      .map(
        (x, i) =>
          `${i ? "L" : "M"}${(i * 100) / Math.max(1, observed.length - 1)} ${27 - (x[1] * 22) / max}`,
      )
      .join(" "),
  );
  renderMap(s);
  renderTable(s);
  const plan = s.latestPlan;
  $("export-proof").disabled = !plan;
  $("plan-count").textContent = plan
    ? `${plan.optimal.cardinality} / ${plan.greedy.cardinality}`
    : "— / —";
  $("plan-cost").textContent = plan
    ? `${plan.optimal.cost.toLocaleString()} / ${plan.greedy.cost.toLocaleString()}`
    : "— / —";
  $("solve-time").textContent = plan
    ? `${plan.solve_us.toLocaleString()} μs`
    : "—";
  $("ledger-status").textContent = s.audit.healthy
    ? "Chain consistent"
    : "Ledger unavailable";
  $("event-count").textContent = s.audit.records;
  $("chain-head").textContent = s.audit.head;
  $("event-timeline").replaceChildren(
    ...s.history
      .slice(-4)
      .reverse()
      .map((h) => {
        const li = el("li");
        li.append(el("span", "", h.message), el("time", "", `T+${h.tick}`));
        return li;
      }),
  );
  if (!$("from-site").options.length) {
    for (const site of s.sites) {
      $("from-site").add(new Option(site.label, site.id));
      $("to-site").add(new Option(site.label, site.id));
    }
    $("to-site").selectedIndex = 1;
  }
  setBusy(busy);
}
async function command(op, extra = {}) {
  if (busy || !state) return false;
  setBusy(true);
  try {
    const response = await fetch(`/api/${op}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commandId: crypto.randomUUID(),
        expectedRevision: state.revision,
        ...extra,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      if (data.state) render(data.state);
      throw new Error(data.error ?? `HTTP ${response.status}`);
    }
    render(data.state);
    return true;
  } catch (error) {
    showError(error.message);
    if (autoplay) stopAuto();
    return false;
  } finally {
    setBusy(false);
  }
}
function stopAuto() {
  autoplay = false;
  clearTimeout(autoTimer);
  $("autoplay").setAttribute("aria-pressed", "false");
  $("autoplay").textContent = "▶ Auto run";
  $("simulation-status").textContent = "Manual mode";
}
async function autoCycle() {
  if (!autoplay) return;
  if (!busy) {
    await command("advance", { ticks: 5 });
    if (autoplay && canDispatch(state)) await command("plan");
  }
  if (autoplay && metrics(state).active === 0 && metrics(state).queued === 0) {
    stopAuto();
    toast("All requests delivered. The ledger has the full trail.");
    return;
  }
  if (autoplay) autoTimer = setTimeout(autoCycle, 3500);
}
$("optimize").addEventListener("click", () =>
  command("plan").then((ok) => {
    if (ok) toast("Optimal assignments committed to the ledger.");
  }),
);
$("step").addEventListener("click", () => command("advance", { ticks: 5 }));
$("reset").addEventListener("click", () => {
  stopAuto();
  command("reset");
});
$("autoplay").addEventListener("click", () => {
  if (autoplay) {
    stopAuto();
    return;
  }
  if (!state) return;
  autoplay = true;
  $("autoplay").setAttribute("aria-pressed", "true");
  $("autoplay").textContent = "Ⅱ Pause";
  $("simulation-status").textContent = "Auto · 5 ticks / step";
  autoCycle();
});
$("new-request").addEventListener("click", () => {
  $("request-dialog").showModal();
  $("request-form").elements.label.focus();
});
$("close-dialog").addEventListener("click", () => $("request-dialog").close());
$("request-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const request = Object.fromEntries(form);
  request.priority = Number(request.priority);
  if (request.from === request.to) {
    toast("Choose a different destination.");
    return;
  }
  if (await command("task", request)) {
    $("request-dialog").close();
    $("request-form").elements.label.value = "";
    toast("Request created and recorded.");
  }
});
for (const b of document.querySelectorAll("[data-filter]"))
  b.addEventListener("click", () => {
    filter = b.dataset.filter;
    for (const tab of document.querySelectorAll("[data-filter]"))
      tab.setAttribute("aria-pressed", String(tab === b));
    if (state) renderTable(state);
  });
$("export-proof").addEventListener("click", () => {
  if (!state?.latestPlan) return;
  const p = state.latestPlan;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify({ problem: p.problem, response: p }, null, 2)], {
      type: "application/json",
    }),
  );
  const a = el("a");
  a.href = url;
  a.download = `foundry-proof-revision-${state.revision}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("copy-head").addEventListener("click", async () => {
  if (!state) return;
  try {
    await navigator.clipboard.writeText(state.audit.head);
    toast(
      "Full chain head copied. Store it independently to anchor the ledger.",
    );
  } catch {
    toast("Clipboard unavailable. Select the chain head to copy it.");
  }
});
setBusy(false);
fetch("/api/state")
  .then(async (r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    render(await r.json());
  })
  .catch((e) => showError(`Could not load the workspace: ${e.message}`));
const events = new EventSource("/api/events");
events.addEventListener("snapshot", (event) => {
  try {
    render(JSON.parse(event.data));
    status(true);
  } catch {
    showError("Invalid state received from the server.");
  }
});
events.onopen = () => status(true);
events.onerror = () => status(false);
window.addEventListener("pagehide", () => {
  events.close();
  stopAuto();
});
