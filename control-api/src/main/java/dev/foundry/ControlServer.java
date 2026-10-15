package dev.foundry;

import com.google.gson.*;
import com.sun.net.httpserver.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.LongAdder;

final class ControlServer implements AutoCloseable {
  private final HttpServer server;
  private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();
  private final FoundryService service;
  private final EventHub hub;
  private final Path webRoot;
  private final Semaphore requests = new Semaphore(48);
  private final LongAdder count = new LongAdder();
  private final LongAdder errors = new LongAdder();
  private static final int BODY_LIMIT = 32_768;
  private static final Map<String, String> FILES =
      Map.of(
          "/",
          "index.html",
          "/style.css",
          "style.css",
          "/app.js",
          "app.js",
          "/ui-model.mjs",
          "ui-model.mjs",
          "/kernel-trace.json",
          "kernel-trace.json");

  ControlServer(int port, FoundryService service, EventHub hub, Path webRoot) throws IOException {
    this.service = service;
    this.hub = hub;
    this.webRoot = webRoot;
    server = HttpServer.create(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), port), 32);
    server.createContext("/", this::handle);
    server.setExecutor(executor);
  }

  void start() {
    server.start();
  }

  int port() {
    return server.getAddress().getPort();
  }

  private void handle(HttpExchange x) throws IOException {
    if (!requests.tryAcquire()) {
      reply(x, 503, Json.obj("error", "Server busy"));
      return;
    }
    count.increment();
    try {
      headers(x);
      if (!allowedHost(x)) {
        reply(x, 403, Json.obj("error", "Local host/origin check failed"));
        return;
      }
      String path = x.getRequestURI().getPath(), method = x.getRequestMethod();
      if (method.equals("GET") && path.equals("/api/events")) {
        stream(x);
        return;
      }
      if (method.equals("GET") && path.equals("/api/state")) {
        reply(x, 200, service.snapshot());
        return;
      }
      if (method.equals("GET") && path.equals("/api/health")) {
        var state = service.snapshot();
        boolean healthy =
            state.getAsJsonObject("dependencies").get("ledger").getAsBoolean()
                && state.getAsJsonObject("dependencies").get("optimizer").getAsBoolean();
        reply(
            x,
            healthy ? 200 : 503,
            Json.obj(
                "ok",
                healthy,
                "revision",
                state.get("revision"),
                "requests",
                count.sum(),
                "errors",
                errors.sum(),
                "liveClients",
                hub.size(),
                "mode",
                "local-fictional-simulation"));
        return;
      }
      if (method.equals("POST")
          && Set.of("/api/plan", "/api/advance", "/api/task", "/api/reset").contains(path)) {
        String contentType = x.getRequestHeaders().getFirst("Content-Type");
        if (contentType == null
            || !contentType.split(";", 2)[0].trim().equalsIgnoreCase("application/json")) {
          reply(x, 415, Json.obj("error", "Content-Type must be application/json"));
          return;
        }
        byte[] bytes = x.getRequestBody().readNBytes(BODY_LIMIT + 1);
        if (bytes.length > BODY_LIMIT) {
          reply(x, 413, Json.obj("error", "Request body limit is 32 KiB"));
          return;
        }
        var request = Json.object(new String(bytes, StandardCharsets.UTF_8));
        reply(x, 200, service.command(path.substring(5), request));
        return;
      }
      if (method.equals("GET") && FILES.containsKey(path)) {
        Path file = webRoot.resolve(FILES.get(path));
        if (!Files.isRegularFile(file)) {
          reply(x, 404, Json.obj("error", "Asset not installed"));
          return;
        }
        String type =
            path.endsWith(".css")
                ? "text/css"
                : path.endsWith(".js") || path.endsWith(".mjs")
                    ? "text/javascript"
                    : path.endsWith(".json") ? "application/json" : "text/html";
        x.getResponseHeaders().set("Content-Type", type + "; charset=utf-8");
        x.getResponseHeaders().set("Cache-Control", "no-cache");
        byte[] data = Files.readAllBytes(file);
        x.sendResponseHeaders(200, data.length);
        x.getResponseBody().write(data);
        x.close();
        return;
      }
      reply(
          x,
          path.startsWith("/api/") ? 405 : 404,
          Json.obj("error", "Route or method not available"));
    } catch (FoundryService.Conflict e) {
      errors.increment();
      reply(x, 409, Json.obj("error", e.getMessage(), "state", service.snapshot()));
    } catch (JsonParseException | IllegalArgumentException e) {
      errors.increment();
      reply(x, 400, Json.obj("error", e.getMessage()));
    } catch (IllegalStateException e) {
      errors.increment();
      reply(x, 429, Json.obj("error", e.getMessage()));
    } catch (IOException e) {
      errors.increment();
      try {
        reply(
            x,
            503,
            Json.obj(
                "error",
                "Dependency unavailable or durability outcome uncertain; restart and verify"));
      } catch (IOException ignored) {
        x.close();
      }
    } catch (Exception e) {
      errors.increment();
      System.err.println("request failed: " + e.getClass().getSimpleName());
      try {
        reply(x, 500, Json.obj("error", "Internal request failure"));
      } catch (IOException ignored) {
        x.close();
      }
    } finally {
      requests.release();
    }
  }

  private boolean allowedHost(HttpExchange x) {
    String host = x.getRequestHeaders().getFirst("Host");
    if (host == null
        || !Set.of("127.0.0.1:" + port(), "localhost:" + port())
            .contains(host.toLowerCase(Locale.ROOT))) return false;
    String origin = x.getRequestHeaders().getFirst("Origin");
    return origin == null || origin.equals("http://" + host.toLowerCase(Locale.ROOT));
  }

  private void headers(HttpExchange x) {
    var h = x.getResponseHeaders();
    h.set("X-Content-Type-Options", "nosniff");
    h.set("Referrer-Policy", "no-referrer");
    h.set(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src"
            + " 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
    h.set("Cache-Control", "no-store");
  }

  private void stream(HttpExchange x) throws IOException {
    var q = hub.subscribe();
    try {
      x.getResponseHeaders().set("Content-Type", "text/event-stream; charset=utf-8");
      x.getResponseHeaders().set("X-Accel-Buffering", "no");
      x.sendResponseHeaders(200, 0);
      var out = x.getResponseBody();
      out.write(EventHub.frame(service.snapshot()).getBytes(StandardCharsets.UTF_8));
      out.flush();
      while (!Thread.currentThread().isInterrupted()) {
        String event = q.poll(10, TimeUnit.SECONDS);
        out.write((event == null ? ": heartbeat\n\n" : event).getBytes(StandardCharsets.UTF_8));
        out.flush();
      }
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
    } finally {
      hub.remove(q);
      x.close();
    }
  }

  private static void reply(HttpExchange x, int status, JsonObject body) throws IOException {
    byte[] bytes = Json.GSON.toJson(body).getBytes(StandardCharsets.UTF_8);
    x.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
    x.sendResponseHeaders(status, bytes.length);
    x.getResponseBody().write(bytes);
    x.close();
  }

  public void close() {
    server.stop(0);
    executor.shutdownNow();
  }
}
