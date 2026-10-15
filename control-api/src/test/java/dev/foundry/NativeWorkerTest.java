package dev.foundry;

import static org.junit.jupiter.api.Assertions.*;

import java.io.IOException;
import java.nio.file.*;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

/** Real subprocess failures; Python is used only as a deliberately broken peer. */
class NativeWorkerTest {
  @TempDir Path dir;

  private NativeWorker peer(String script) throws Exception {
    var source = dir.resolve("peer.py");
    Files.writeString(source, script);
    return new NativeWorker(List.of("python3", "-u", source.toString()), dir.resolve("peer.log"));
  }

  @Test
  void boundsAStalledPeerAndDoesNotReuseIt() throws Exception {
    try (var worker = peer("import sys,time\nsys.stdin.readline()\ntime.sleep(30)\n")) {
      long start = System.nanoTime();
      assertThrows(
          IOException.class, () -> worker.exchange(Json.obj("hello", 1), Duration.ofMillis(150)));
      assertTrue(Duration.ofNanos(System.nanoTime() - start).toMillis() < 3000);
      assertFalse(worker.alive());
      assertThrows(
          IOException.class, () -> worker.exchange(Json.obj("hello", 2), Duration.ofSeconds(1)));
    }
  }

  @Test
  void malformedResponseAndEarlyExitFailClosed() throws Exception {
    for (String script :
        new String[] {
          "import sys\nsys.stdin.readline()\nprint('not-json',flush=True)\n",
          "raise SystemExit(0)\n", "import sys\nsys.stdin.readline()\nsys.stdout.write('{\"ok\":true}');sys.stdout.flush()\n"
        })
      try (var worker = peer(script)) {
        assertThrows(
            IOException.class, () -> worker.exchange(Json.obj("x", 1), Duration.ofSeconds(2)));
        assertFalse(worker.alive());
      }
  }

  @Test
  void successfulPeerExchangesMoreThanOnce() throws Exception {
    try (var worker =
        peer(
            "import sys,json\n"
                + "for line in sys.stdin:\n"
                + " r=json.loads(line);print(json.dumps({'ok':True,'echo':r}),flush=True)\n")) {
      for (int i = 0; i < 5; i++)
        assertEquals(
            i,
            worker
                .exchange(Json.obj("i", i), Duration.ofSeconds(2))
                .getAsJsonObject("echo")
                .get("i")
                .getAsInt());
    }
  }
}
