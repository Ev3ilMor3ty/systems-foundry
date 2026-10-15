package dev.foundry;

import com.google.gson.*;
import java.io.IOException;
import java.util.function.Consumer;

/** Serializes transitions; an acknowledged mutation is already durable. */
final class FoundryService {
  static final class Conflict extends RuntimeException {
    Conflict(String m) {
      super(m);
    }
  }

  private final Ports.Journal journal;
  private final Ports.Matcher matcher;
  private final Consumer<JsonObject> publish;
  private JsonObject state;
  private String head;
  private long records;
  private boolean degraded;

  FoundryService(Ports.Journal journal, Ports.Matcher matcher, Consumer<JsonObject> publish)
      throws IOException {
    this.journal = journal;
    this.matcher = matcher;
    this.publish = publish;
    var last = journal.last();
    if (last == null) {
      var initial = Domain.initial();
      last =
          journal.append(
              "bootstrap-v1",
              Json.obj(
                  "schema",
                  1,
                  "operation",
                  "bootstrap",
                  "request",
                  new JsonObject(),
                  "state",
                  initial));
    }
    state = last.getAsJsonObject("event").getAsJsonObject("state").deepCopy();
    Domain.validateRestored(state);
    head = last.get("hash").getAsString();
    records = last.get("seq").getAsLong();
  }

  synchronized JsonObject snapshot() {
    var result = state.deepCopy();
    result.add(
        "audit",
        Json.obj(
            "head",
            head,
            "records",
            records,
            "internalChainVerified",
            true,
            "externallyAnchored",
            false,
            "healthy",
            !degraded && journal.healthy(),
            "verification",
            "startup-and-owned-appends"));
    result.add(
        "dependencies",
        Json.obj("ledger", !degraded && journal.healthy(), "optimizer", matcher.healthy()));
    return result;
  }

  synchronized JsonObject command(String operation, JsonObject request) throws IOException {
    if (degraded || !journal.healthy())
      throw new IOException("Ledger unavailable; restart and verify before making changes");
    var allowed = new java.util.HashSet<>(java.util.Set.of("commandId", "expectedRevision"));
    switch (operation) {
      case "advance" -> allowed.add("ticks");
      case "task" -> allowed.addAll(java.util.Set.of("label", "from", "to", "skill", "priority"));
      default -> {}
    }
    if (!allowed.containsAll(request.keySet()))
      throw new IllegalArgumentException("Unknown request field");
    String id = Json.text(request, "commandId", 128);
    if (!id.matches("[A-Za-z0-9_.:-]{1,128}") || id.equals("bootstrap-v1"))
      throw new IllegalArgumentException("Invalid commandId");
    try {
      var existing = journal.find(id);
      if (existing != null) {
        var event = existing.getAsJsonObject("event");
        if (!event.get("operation").getAsString().equals(operation)
            || !event.get("request").equals(request))
          throw new Conflict("commandId was already used for a different request");
        return Json.obj(
            "ok",
            true,
            "replayed",
            true,
            "committedRevision",
            event.getAsJsonObject("state").get("revision"),
            "state",
            snapshot());
      }
    } catch (IOException e) {
      degraded = true;
      throw e;
    }
    long expected = Json.integer(request, "expectedRevision", 0, Long.MAX_VALUE);
    if (expected != state.get("revision").getAsLong())
      throw new Conflict("State changed; refresh and retry with a new commandId");
    var next = state.deepCopy();
    switch (operation) {
      case "plan" -> {
        var problem = Domain.problem(next);
        var solution = matcher.solve(problem);
        ProofVerifier.verify(problem, solution);
        solution.add("problem", problem);
        solution.add(
            "workerIds",
            Json.GSON.toJsonTree(
                Domain.idle(next).stream().map(w -> w.get("id").getAsString()).toList()));
        solution.add(
            "taskIds",
            Json.GSON.toJsonTree(
                Domain.queued(next).stream().map(t -> t.get("id").getAsString()).toList()));
        Domain.assign(next, solution);
      }
      case "advance" -> {
        int ticks = (int) Json.integer(request, "ticks", 1, 30);
        if (next.get("tick").getAsInt() + ticks > 1_000_000)
          throw new IllegalArgumentException("Simulation tick limit reached");
        Domain.advance(next, ticks);
      }
      case "task" -> {
        Domain.add(next, request);
        Domain.history(next, "Request added · " + Json.text(request, "label", 60));
      }
      case "reset" -> next = Domain.initial();
      default -> throw new IllegalArgumentException("Unknown operation");
    }
    next.addProperty("revision", Math.addExact(state.get("revision").getAsLong(), 1));
    var event = Json.obj("schema", 1, "operation", operation, "request", request, "state", next);
    JsonObject committed;
    try {
      committed = journal.append(id, event);
    } catch (IOException e) {
      degraded = true;
      throw e;
    }
    state = next;
    head = committed.get("hash").getAsString();
    records = committed.get("seq").getAsLong();
    var snapshot = snapshot();
    publish.accept(snapshot.deepCopy());
    return Json.obj(
        "ok",
        true,
        "replayed",
        false,
        "committedRevision",
        state.get("revision"),
        "state",
        snapshot);
  }
}
