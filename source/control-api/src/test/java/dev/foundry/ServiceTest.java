package dev.foundry;

import static org.junit.jupiter.api.Assertions.*;

import com.google.gson.*;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;

class ServiceTest {
  static class MemoryJournal implements Ports.Journal {
    final LinkedHashMap<String, JsonObject> records = new LinkedHashMap<>();
    boolean fail;

    public JsonObject last() {
      return records.isEmpty() ? null : new ArrayList<>(records.values()).getLast().deepCopy();
    }

    public JsonObject find(String id) {
      return records.containsKey(id) ? records.get(id).deepCopy() : null;
    }

    public JsonObject append(String id, JsonObject event) throws IOException {
      if (fail) throw new IOException("simulated storage failure");
      var r =
          Json.obj(
              "seq", records.size() + 1, "hash", "head-" + (records.size() + 1), "event", event);
      records.put(id, r.deepCopy());
      return r;
    }

    public boolean healthy() {
      return true;
    }
  }

  static Ports.Matcher noAssignments =
      input ->
          Json.obj(
              "ok",
              true,
              "optimal",
              Json.obj("pairs", new JsonArray(), "cardinality", 0, "cost", 0),
              "greedy",
              Json.obj("cardinality", 0, "cost", 0));

  @Test
  void restartAndReplayWithoutDuplicateCommits() throws Exception {
    var j = new MemoryJournal();
    var s = new FoundryService(j, noAssignments, x -> {});
    var request = Json.obj("commandId", "c1", "expectedRevision", 0, "ticks", 5);
    var first = s.command("advance", request);
    assertEquals(1, first.get("committedRevision").getAsInt());
    assertTrue(s.command("advance", request).get("replayed").getAsBoolean());
    assertEquals(2, j.records.size());
    var restored = new FoundryService(j, noAssignments, x -> {});
    assertEquals(5, restored.snapshot().get("tick").getAsInt());
    assertTrue(restored.command("advance", request).get("replayed").getAsBoolean());
    assertThrows(
        FoundryService.Conflict.class,
        () ->
            restored.command(
                "advance", Json.obj("commandId", "c1", "expectedRevision", 0, "ticks", 6)));
  }

  @Test
  void failedDurabilityDoesNotPublishAndStopsFurtherWrites() throws Exception {
    var j = new MemoryJournal();
    var events = new ArrayList<JsonObject>();
    var s = new FoundryService(j, noAssignments, events::add);
    j.fail = true;
    assertThrows(
        IOException.class,
        () ->
            s.command("advance", Json.obj("commandId", "bad", "expectedRevision", 0, "ticks", 1)));
    assertEquals(0, s.snapshot().get("revision").getAsInt());
    assertTrue(events.isEmpty());
    assertFalse(s.snapshot().getAsJsonObject("audit").get("healthy").getAsBoolean());
    j.fail = false;
    assertThrows(
        IOException.class,
        () ->
            s.command(
                "advance", Json.obj("commandId", "retry", "expectedRevision", 0, "ticks", 1)));
  }

  @Test
  void concurrentStaleEditsHaveExactlyOneWinner() throws Exception {
    var j = new MemoryJournal();
    var s = new FoundryService(j, noAssignments, x -> {});
    var start = new CountDownLatch(1);
    var outcomes = new ArrayList<Future<Boolean>>();
    try (var pool = Executors.newVirtualThreadPerTaskExecutor()) {
      for (int i = 0; i < 20; i++) {
        int id = i;
        outcomes.add(
            pool.submit(
                () -> {
                  start.await();
                  try {
                    s.command(
                        "advance",
                        Json.obj("commandId", "parallel-" + id, "expectedRevision", 0, "ticks", 1));
                    return true;
                  } catch (FoundryService.Conflict e) {
                    return false;
                  }
                }));
      }
      start.countDown();
      int wins = 0;
      for (var o : outcomes) if (o.get()) ++wins;
      assertEquals(1, wins);
    }
    assertEquals(1, s.snapshot().get("revision").getAsInt());
    assertEquals(2, j.records.size());
  }

  @Test
  void invalidInputLeavesLedgerUntouched() throws Exception {
    var j = new MemoryJournal();
    var s = new FoundryService(j, noAssignments, x -> {});
    assertThrows(
        IllegalArgumentException.class,
        () ->
            s.command("advance", Json.obj("commandId", "a", "expectedRevision", 0, "ticks", 1.1)));
    assertThrows(
        IllegalArgumentException.class,
        () ->
            s.command(
                "task",
                Json.obj(
                    "commandId",
                    "b",
                    "expectedRevision",
                    0,
                    "label",
                    "x",
                    "from",
                    "dock",
                    "to",
                    "dock",
                    "skill",
                    "cargo",
                    "priority",
                    1)));
    assertEquals(1, j.records.size());
  }

  @Test
  void transitionsCompleteAndReleaseResources() {
    var state = Domain.initial();
    var pairs = new JsonArray();
    pairs.add(Json.obj("worker", 0, "task", 0));
    Domain.assign(state, Json.obj("optimal", Json.obj("pairs", pairs)));
    var task = state.getAsJsonArray("tasks").get(0).getAsJsonObject();
    assertEquals("active", task.get("status").getAsString());
    Domain.advance(state, 100);
    assertEquals("done", task.get("status").getAsString());
    assertTrue(
        state.getAsJsonArray("resources").get(0).getAsJsonObject().get("taskId").isJsonNull());
    assertEquals(
        "lab",
        state.getAsJsonArray("resources").get(0).getAsJsonObject().get("site").getAsString());
  }

  @Test
  void subscribersRemainBoundedAndReceiveLatestSnapshot() {
    var hub = new EventHub();
    var q = hub.subscribe();
    for (int i = 0; i < 100; i++) hub.publish(Json.obj("revision", i));
    assertTrue(q.size() <= 4);
    String last = "";
    while (!q.isEmpty()) last = q.poll();
    assertTrue(last.contains("id: 99"));
    for (int i = 0; i < 7; i++) hub.subscribe();
    assertThrows(IllegalStateException.class, hub::subscribe);
    hub.remove(q);
    assertEquals(7, hub.size());
  }
}
