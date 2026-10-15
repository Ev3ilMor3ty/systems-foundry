package dev.foundry;

import com.google.gson.*;
import java.util.*;

/** Pure simulation transitions. Coordinates and travel ticks are fictional. */
final class Domain {
  static final Set<String> SKILLS = Set.of("cargo", "cold", "fragile");

  static JsonObject initial() {
    var sites = new JsonArray();
    Object[][] places = {
      {"dock", "North dock", 18, 20},
      {"glass", "Glassworks", 50, 17},
      {"cold", "Cold store", 80, 24},
      {"hub", "Transfer hub", 48, 49},
      {"forge", "South forge", 20, 78},
      {"lab", "Materials lab", 78, 76}
    };
    for (var p : places) sites.add(Json.obj("id", p[0], "label", p[1], "x", p[2], "y", p[3]));
    var resources = new JsonArray();
    String[][] units = {
      {"V01", "Kestrel", "dock", "cargo", "fragile"},
      {"V02", "Mistral", "cold", "cargo", "cold"},
      {"V03", "Atlas", "forge", "cargo"},
      {"V04", "Echo", "lab", "cargo", "fragile", "cold"},
      {"V05", "Cinder", "glass", "cargo", "fragile"},
      {"V06", "Tern", "hub", "cargo", "cold"}
    };
    for (var unit : units)
      resources.add(
          Json.obj(
              "id",
              unit[0],
              "name",
              unit[1],
              "site",
              unit[2],
              "skills",
              Arrays.copyOfRange(unit, 3, unit.length),
              "taskId",
              null));
    var state =
        Json.obj(
            "schema",
            1,
            "revision",
            0,
            "tick",
            0,
            "sites",
            sites,
            "resources",
            resources,
            "tasks",
            new JsonArray(),
            "history",
            new JsonArray(),
            "latestPlan",
            null);
    String[][] jobs = {
      {"Precision glass", "glass", "lab", "fragile"},
      {"Chilled samples", "cold", "lab", "cold"},
      {"Alloy shipment", "dock", "forge", "cargo"},
      {"Optics transfer", "lab", "glass", "fragile"},
      {"Cooling cells", "forge", "cold", "cold"},
      {"Dock replenishment", "hub", "dock", "cargo"},
      {"Instrument crate", "glass", "hub", "fragile"},
      {"Resin supply", "dock", "lab", "cargo"},
      {"Thermal pack", "cold", "hub", "cold"},
      {"Steel spool", "forge", "glass", "cargo"},
      {"Sensor rack", "lab", "forge", "fragile"},
      {"Assembly kit", "hub", "glass", "cargo"}
    };
    for (int i = 0; i < jobs.length; ++i)
      add(
          state,
          Json.obj(
              "label",
              jobs[i][0],
              "from",
              jobs[i][1],
              "to",
              jobs[i][2],
              "skill",
              jobs[i][3],
              "priority",
              1 + i % 3));
    history(state, "Scenario loaded · six carriers, twelve requests");
    return state;
  }

  static List<JsonObject> objects(JsonArray values) {
    var result = new ArrayList<JsonObject>();
    values.forEach(v -> result.add(v.getAsJsonObject()));
    return result;
  }

  static JsonObject site(JsonObject state, String id) {
    return objects(state.getAsJsonArray("sites")).stream()
        .filter(s -> s.get("id").getAsString().equals(id))
        .findFirst()
        .orElseThrow(() -> new IllegalArgumentException("Unknown site: " + id));
  }

  static int distance(JsonObject s, String a, String b) {
    var x = site(s, a);
    var y = site(s, b);
    return Math.abs(x.get("x").getAsInt() - y.get("x").getAsInt())
        + Math.abs(x.get("y").getAsInt() - y.get("y").getAsInt());
  }

  static void add(JsonObject s, JsonObject request) {
    if (s.getAsJsonArray("tasks").size() >= 160)
      throw new IllegalArgumentException(
          "Scenario limit: 160 requests; reset to start another run");
    String label = Json.text(request, "label", 60),
        from = Json.text(request, "from", 24),
        to = Json.text(request, "to", 24),
        skill = Json.text(request, "skill", 12);
    site(s, from);
    site(s, to);
    if (from.equals(to)) throw new IllegalArgumentException("Pickup and destination must differ");
    if (!SKILLS.contains(skill)) throw new IllegalArgumentException("Unknown capability");
    int priority = (int) Json.integer(request, "priority", 1, 3);
    s.getAsJsonArray("tasks")
        .add(
            Json.obj(
                "id",
                String.format("R%03d", s.getAsJsonArray("tasks").size() + 1),
                "label",
                label,
                "from",
                from,
                "to",
                to,
                "skill",
                skill,
                "priority",
                priority,
                "status",
                "queued",
                "resourceId",
                null,
                "duration",
                0,
                "remaining",
                0,
                "createdTick",
                s.get("tick").getAsInt()));
  }

  static List<JsonObject> idle(JsonObject s) {
    return objects(s.getAsJsonArray("resources")).stream()
        .filter(r -> r.get("taskId").isJsonNull())
        .toList();
  }

  static List<JsonObject> queued(JsonObject s) {
    return objects(s.getAsJsonArray("tasks")).stream()
        .filter(t -> t.get("status").getAsString().equals("queued"))
        .toList();
  }

  static JsonObject problem(JsonObject s) {
    var workers = idle(s);
    var tasks = queued(s);
    var edges = new JsonArray();
    for (int w = 0; w < workers.size(); ++w)
      for (int t = 0; t < tasks.size(); ++t) {
        var worker = workers.get(w);
        var task = tasks.get(t);
        if (worker.getAsJsonArray("skills").contains(task.get("skill"))) {
          int travel =
              distance(s, worker.get("site").getAsString(), task.get("from").getAsString());
          int delivery = distance(s, task.get("from").getAsString(), task.get("to").getAsString());
          int age = s.get("tick").getAsInt() - task.get("createdTick").getAsInt();
          int priorityPenalty =
              Math.max(0, (3 - task.get("priority").getAsInt()) * 240 - Math.min(age, 120) * 2);
          edges.add(
              Json.obj(
                  "worker", w, "task", t, "cost", travel * 10 + delivery * 3 + priorityPenalty));
        }
      }
    return Json.obj("workers", workers.size(), "tasks", tasks.size(), "edges", edges);
  }

  static void assign(JsonObject s, JsonObject plan) {
    var workers = idle(s);
    var tasks = queued(s);
    var usedWorkers = new HashSet<Integer>();
    var usedTasks = new HashSet<Integer>();
    var pairs = plan.getAsJsonObject("optimal").getAsJsonArray("pairs");
    for (var value : pairs) {
      var pair = value.getAsJsonObject();
      int wi = (int) Json.integer(pair, "worker", 0, workers.size() - 1),
          ti = (int) Json.integer(pair, "task", 0, tasks.size() - 1);
      if (!usedWorkers.add(wi) || !usedTasks.add(ti))
        throw new IllegalArgumentException("Solver returned conflicting assignments");
      var w = workers.get(wi);
      var t = tasks.get(ti);
      if (!w.getAsJsonArray("skills").contains(t.get("skill")))
        throw new IllegalArgumentException("Solver returned ineligible assignment");
      int duration =
          2
              + (distance(s, w.get("site").getAsString(), t.get("from").getAsString())
                      + distance(s, t.get("from").getAsString(), t.get("to").getAsString())
                      + 5)
                  / 6;
      t.addProperty("status", "active");
      t.addProperty("resourceId", w.get("id").getAsString());
      t.addProperty("startSite", w.get("site").getAsString());
      t.addProperty("duration", duration);
      t.addProperty("remaining", duration);
      w.addProperty("taskId", t.get("id").getAsString());
    }
    var summary = plan.deepCopy();
    summary.addProperty("tick", s.get("tick").getAsInt());
    s.add("latestPlan", summary);
    history(
        s, "Optimizer dispatched " + pairs.size() + " request" + (pairs.size() == 1 ? "" : "s"));
  }

  static void advance(JsonObject s, int ticks) {
    s.addProperty("tick", Math.addExact(s.get("tick").getAsInt(), ticks));
    int completed = 0;
    for (var t : objects(s.getAsJsonArray("tasks")))
      if (t.get("status").getAsString().equals("active")) {
        int remaining = Math.max(0, t.get("remaining").getAsInt() - ticks);
        t.addProperty("remaining", remaining);
        if (remaining == 0) {
          t.addProperty("status", "done");
          t.addProperty("completedTick", s.get("tick").getAsInt());
          ++completed;
          var worker =
              objects(s.getAsJsonArray("resources")).stream()
                  .filter(w -> w.get("id").equals(t.get("resourceId")))
                  .findFirst()
                  .orElseThrow();
          worker.add("taskId", JsonNull.INSTANCE);
          worker.add("site", t.get("to").deepCopy());
        }
      }
    history(s, "Advanced " + ticks + " ticks · " + completed + " completed");
  }

  static void history(JsonObject s, String message) {
    var a = s.getAsJsonArray("history");
    a.add(Json.obj("tick", s.get("tick"), "message", message));
    while (a.size() > 24) a.remove(0);
  }

  static void validateRestored(JsonObject s) {
    if (Json.integer(s, "schema", 1, 1) != 1)
      throw new IllegalArgumentException("Unknown state schema");
    Json.integer(s, "revision", 0, Long.MAX_VALUE);
    Json.integer(s, "tick", 0, 1_000_000);
    if (s.getAsJsonArray("resources").size() != 6
        || s.getAsJsonArray("sites").size() != 6
        || s.getAsJsonArray("tasks").size() > 160)
      throw new IllegalArgumentException("Invalid restored scenario bounds");
    var ids = new HashSet<String>();
    for (var task : objects(s.getAsJsonArray("tasks"))) {
      if (!ids.add(Json.text(task, "id", 16)))
        throw new IllegalArgumentException("Duplicate restored request");
      if (!Set.of("queued", "active", "done").contains(Json.text(task, "status", 12)))
        throw new IllegalArgumentException("Invalid restored status");
      site(s, Json.text(task, "from", 24));
      site(s, Json.text(task, "to", 24));
    }
  }
}
