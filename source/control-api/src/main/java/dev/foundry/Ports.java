package dev.foundry;

import com.google.gson.JsonObject;
import java.io.IOException;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;

final class Ports {
  interface Journal {
    JsonObject last() throws IOException;

    JsonObject find(String id) throws IOException;

    JsonObject append(String id, JsonObject event) throws IOException;

    boolean healthy();
  }

  interface Matcher {
    JsonObject solve(JsonObject input) throws IOException;

    default boolean healthy() {
      return true;
    }
  }

  static final class Ledger implements Journal, AutoCloseable {
    private final NativeWorker worker;

    Ledger(Path binary, Path file, Path log) throws IOException {
      worker = new NativeWorker(List.of(binary.toString(), "serve", file.toString()), log);
    }

    public JsonObject last() throws IOException {
      return record(worker.exchange(Json.obj("op", "status"), Duration.ofSeconds(5)).get("last"));
    }

    public JsonObject find(String id) throws IOException {
      return record(
          worker.exchange(Json.obj("op", "lookup", "id", id), Duration.ofSeconds(3)).get("record"));
    }

    public JsonObject append(String id, JsonObject event) throws IOException {
      return worker
          .exchange(Json.obj("op", "append", "id", id, "event", event), Duration.ofSeconds(5))
          .getAsJsonObject("record");
    }

    public boolean healthy() {
      return worker.alive();
    }

    private static JsonObject record(com.google.gson.JsonElement e) {
      return e == null || e.isJsonNull() ? null : e.getAsJsonObject();
    }

    public void close() {
      worker.close();
    }
  }

  static final class Solver implements Matcher, AutoCloseable {
    private final NativeWorker worker;

    Solver(Path binary, Path log) throws IOException {
      worker = new NativeWorker(List.of(binary.toString(), "--serve"), log);
    }

    public JsonObject solve(JsonObject input) throws IOException {
      return worker.exchange(input, Duration.ofSeconds(5));
    }

    public boolean healthy() {
      return worker.alive();
    }

    public void close() {
      worker.close();
    }
  }
}
