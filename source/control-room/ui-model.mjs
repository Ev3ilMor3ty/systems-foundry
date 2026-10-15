export function metrics(state) {
  const tasks = state.tasks ?? [];
  return {
    queued: tasks.filter((t) => t.status === "queued").length,
    active: tasks.filter((t) => t.status === "active").length,
    done: tasks.filter((t) => t.status === "done").length,
    urgent: tasks.filter((t) => t.status === "queued" && t.priority === 3)
      .length,
    idle: (state.resources ?? []).filter((r) => !r.taskId).length,
  };
}
export function formatTick(tick) {
  return `${String(Math.floor(tick / 60)).padStart(2, "0")}:${String(tick % 60).padStart(2, "0")}`;
}
export function routePoints(state, task) {
  const point = (id) => {
    const s = state.sites.find((s) => s.id === id);
    if (!s) throw new Error("Unknown site");
    return { x: s.x * 10, y: s.y * 5.8 };
  };
  const a = point(task.startSite),
    b = point(task.from),
    c = point(task.to);
  return [a, { x: b.x, y: a.y }, b, { x: c.x, y: b.y }, c];
}
export function pointAlong(points, fraction) {
  if (!points.length) throw new Error("Route is empty");
  const lengths = points
    .slice(1)
    .map((p, i) => Math.hypot(p.x - points[i].x, p.y - points[i].y));
  let distance =
    lengths.reduce((a, b) => a + b, 0) * Math.max(0, Math.min(1, fraction));
  for (let i = 0; i < lengths.length; i++) {
    if (lengths[i] > 0 && distance <= lengths[i]) {
      const f = distance / lengths[i];
      return {
        x: points[i].x + (points[i + 1].x - points[i].x) * f,
        y: points[i].y + (points[i + 1].y - points[i].y) * f,
      };
    }
    distance -= lengths[i];
  }
  return points.at(-1);
}
export function visibleTasks(state, filter) {
  return state.tasks
    .filter((t) => t.status === filter)
    .sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
}
export function acceptSnapshot(current, incoming) {
  return !current || incoming.revision >= current.revision;
}

export function canDispatch(state) {
  return state.resources.some(
    (r) =>
      !r.taskId &&
      state.tasks.some(
        (t) => t.status === "queued" && r.skills.includes(t.skill),
      ),
  );
}
