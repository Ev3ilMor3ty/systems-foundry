package dev.foundry;

import static org.junit.jupiter.api.Assertions.*;

import java.net.URI;
import java.net.http.*;
import java.nio.file.Path;
import java.time.Duration;
import org.junit.jupiter.api.*;

class HttpTest {
  private ControlServer server;
  private HttpClient client;
  private String base;

  @BeforeEach
  void start() throws Exception {
    var hub = new EventHub();
    var service =
        new FoundryService(
            new ServiceTest.MemoryJournal(), ServiceTest.noAssignments, hub::publish);
    server = new ControlServer(0, service, hub, Path.of("../control-room"));
    server.start();
    base = "http://127.0.0.1:" + server.port();
    client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
  }

  @AfterEach
  void stop() {
    server.close();
    client.close();
  }

  private HttpResponse<String> post(String path, String body, String contentType) throws Exception {
    return client.send(
        HttpRequest.newBuilder(URI.create(base + path))
            .header("Content-Type", contentType)
            .timeout(Duration.ofSeconds(3))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build(),
        HttpResponse.BodyHandlers.ofString());
  }

  @Test
  void headersAndStaticPage() throws Exception {
    var r =
        client.send(
            HttpRequest.newBuilder(URI.create(base + "/")).GET().build(),
            HttpResponse.BodyHandlers.ofString());
    assertEquals(200, r.statusCode());
    assertTrue(r.body().contains("Network control"));
    assertEquals("nosniff", r.headers().firstValue("X-Content-Type-Options").orElseThrow());
    assertTrue(
        r.headers()
            .firstValue("Content-Security-Policy")
            .orElseThrow()
            .contains("frame-ancestors 'none'"));
  }

  @Test
  void rejectsCrossOriginAndNonJsonPosts() throws Exception {
    var bad =
        HttpRequest.newBuilder(URI.create(base + "/api/advance"))
            .header("Origin", "https://elsewhere.example")
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString("{}"));
    assertEquals(403, client.send(bad.build(), HttpResponse.BodyHandlers.ofString()).statusCode());
    assertEquals(415, post("/api/advance", "{}", "text/plain").statusCode());
  }

  @Test
  void strictJsonAndBoundedBodies() throws Exception {
    for (String invalid :
        new String[] {
          "{commandId:'x'}", "{\"a\":NaN}", "{} trailing", "null", "[]", "{\"a\":1,}", ""
        })
      assertEquals(400, post("/api/advance", invalid, "application/json").statusCode(), invalid);
    assertEquals(413, post("/api/advance", "x".repeat(32769), "application/json").statusCode());
  }

  @Test
  void realHttpConflictAndIdempotency() throws Exception {
    String body = "{\"commandId\":\"http-1\",\"expectedRevision\":0,\"ticks\":5}";
    assertEquals(200, post("/api/advance", body, "application/json").statusCode());
    assertTrue(post("/api/advance", body, "application/json").body().contains("\"replayed\":true"));
    assertEquals(
        409,
        post("/api/advance", body.replace("http-1", "http-2"), "application/json").statusCode());
    assertEquals(
        400,
        post(
                "/api/advance",
                "{\"commandId\":\"x\",\"expectedRevision\":1,\"ticks\":1,\"surprise\":2}",
                "application/json")
            .statusCode());
  }

  @Test
  void streamsAnInitialFullSnapshot() throws Exception {
    var response =
        client.send(
            HttpRequest.newBuilder(URI.create(base + "/api/events"))
                .timeout(Duration.ofSeconds(3))
                .GET()
                .build(),
            HttpResponse.BodyHandlers.ofInputStream());
    assertEquals(200, response.statusCode());
    try (var input = new java.io.BufferedReader(new java.io.InputStreamReader(response.body()))) {
      assertEquals("id: 0", input.readLine());
      assertEquals("event: snapshot", input.readLine());
      assertTrue(input.readLine().startsWith("data: {"));
    }
  }
}
