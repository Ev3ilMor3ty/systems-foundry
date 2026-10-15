import test from "node:test";
import assert from "node:assert/strict";
import {
  metrics,
  canDispatch,
  formatTick,
  pointAlong,
  routePoints,
  visibleTasks,
  acceptSnapshot,
} from "./ui-model.mjs";
test("metrics count separate workflow states", () =>
  assert.deepEqual(
    metrics({
      tasks: [
        { status: "queued", priority: 3 },
        { status: "active" },
        { status: "done" },
      ],
      resources: [{ taskId: null }, { taskId: "r" }],
    }),
    { queued: 1, active: 1, done: 1, urgent: 1, idle: 1 },
  ));
test("route interpolation clamps boundaries and skips zero-length segments", () => {
  const p = [
    { x: 0, y: 0 },
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 10, y: 10 },
  ];
  assert.deepEqual(pointAlong(p, -1), p[0]);
  assert.deepEqual(pointAlong(p, 0.75), { x: 10, y: 5 });
  assert.deepEqual(pointAlong(p, 2), p.at(-1));
  assert.throws(() => pointAlong([], 0));
});
test("stale event snapshots cannot roll back state", () => {
  assert.ok(!acceptSnapshot({ revision: 10 }, { revision: 9 }));
  assert.ok(acceptSnapshot({ revision: 10 }, { revision: 10 }));
  assert.ok(acceptSnapshot(null, { revision: 0 }));
});
test("time and priority filters are deterministic", () => {
  assert.equal(formatTick(125), "02:05");
  const tasks = [
    { id: "b", status: "queued", priority: 1 },
    { id: "a", status: "queued", priority: 3 },
    { id: "c", status: "done", priority: 3 },
  ];
  assert.deepEqual(
    visibleTasks({ tasks }, "queued").map((t) => t.id),
    ["a", "b"],
  );
  assert.equal(tasks[0].id, "b");
});
test("missing sites fail explicitly", () =>
  assert.throws(
    () => routePoints({ sites: [] }, { startSite: "x", from: "y", to: "z" }),
    /Unknown site/,
  ));

test("dispatch waits for a compatible idle carrier", () => {
  const state = {
    resources: [
      { taskId: null, skills: ["cargo"] },
      { taskId: "active", skills: ["cold"] },
    ],
    tasks: [{ status: "queued", skill: "cold" }],
  };
  assert.equal(canDispatch(state), false);
  state.resources[1].taskId = null;
  assert.equal(canDispatch(state), true);
});
