package dev.foundry;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.*;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** The IPC task must make progress when only one virtual-thread carrier exists. */
class CarrierStarvationTest {
  @TempDir Path directory;

  @Test
  void nativeIoDoesNotNeedAnotherVirtualCarrier() throws Exception {
    Path peer = directory.resolve("peer.py");
    Files.writeString(
        peer,
        "import sys,json\n"
            + "for line in sys.stdin:\n"
            + " print(json.dumps({'ok':True,'echo':json.loads(line)}),flush=True)\n");
    String javaExecutable = Path.of(System.getProperty("java.home"), "bin", "java").toString();
    String classpath =
        System.getProperty("surefire.test.class.path", System.getProperty("java.class.path"));
    var process =
        new ProcessBuilder(
                javaExecutable,
                "-Djdk.virtualThreadScheduler.parallelism=1",
                "-Djdk.virtualThreadScheduler.maxPoolSize=1",
                "-cp",
                classpath,
                Probe.class.getName(),
                peer.toString(),
                directory.resolve("peer.log").toString())
            .redirectErrorStream(true)
            .start();
    boolean finished = process.waitFor(8, TimeUnit.SECONDS);
    if (!finished) {
      process.destroyForcibly();
      process.waitFor(3, TimeUnit.SECONDS);
    }
    assertTrue(finished, "constrained carrier probe stalled");
    String output =
        new String(
            process.getInputStream().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
    assertEquals(0, process.exitValue(), output);
    assertTrue(output.contains("carrier-probe:ok"), output);
  }

  public static final class Probe {
    public static void main(String[] args) throws Exception {
      try (var worker = new NativeWorker(List.of("python3", "-u", args[0]), Path.of(args[1]));
          var callers = Executors.newVirtualThreadPerTaskExecutor()) {
        for (int i = 0; i < 10; i++) {
          int sequence = i;
          var response =
              callers
                  .submit(
                      () -> worker.exchange(Json.obj("sequence", sequence), Duration.ofSeconds(1)))
                  .get(3, TimeUnit.SECONDS);
          if (response.getAsJsonObject("echo").get("sequence").getAsInt() != sequence)
            throw new IllegalStateException("wrong response");
        }
      }
      System.out.println("carrier-probe:ok");
    }
  }
}
