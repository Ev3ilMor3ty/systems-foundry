package dev.foundry;

import com.google.gson.JsonObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.*;

/** Bounded JSON-line IPC. A timed-out worker is killed and never reused. */
final class NativeWorker implements AutoCloseable {
  private final Process process;
  private final BufferedReader reader;
  private final BufferedWriter writer;
  private final ExecutorService io =
      Executors.newSingleThreadExecutor(Thread.ofVirtual().name("native-ipc-", 0).factory());
  private boolean failed;

  NativeWorker(List<String> command, Path errorLog) throws IOException {
    process =
        new ProcessBuilder(command)
            .redirectError(ProcessBuilder.Redirect.appendTo(errorLog.toFile()))
            .start();
    reader =
        new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8));
    writer =
        new BufferedWriter(
            new OutputStreamWriter(process.getOutputStream(), StandardCharsets.UTF_8));
  }

  synchronized JsonObject exchange(JsonObject request, Duration timeout) throws IOException {
    if (failed) throw new IOException("Native worker unavailable; restart required");
    var future =
        io.submit(
            () -> {
              String input = Json.GSON.toJson(request);
              if (input.getBytes(StandardCharsets.UTF_8).length > 900_000)
                throw new IOException("IPC request exceeds limit");
              writer.write(input);
              writer.newLine();
              writer.flush();
              var line = new StringBuilder();
              int c;
                for (; (c = reader.read()) != -1 && c != '\n'; ) {
                if (line.length() >= 2 * 1024 * 1024)
                  throw new IOException("IPC response exceeds limit");
                line.append((char) c);
              }
              if (c == -1) throw new IOException("Incomplete IPC response");
                if (line.isEmpty()) throw new IOException("Native worker closed its output");
              JsonObject response = Json.object(line.toString());
              if (!response.has("ok") || !response.get("ok").isJsonPrimitive() || !response.get("ok").getAsJsonPrimitive().isBoolean() || !response.get("ok").getAsBoolean())
                throw new IOException("Native worker rejected request: " + response.get("error"));
              return response;
            });
    try {
      return future.get(timeout.toMillis(), TimeUnit.MILLISECONDS);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      fail();
      throw new IOException("Interrupted native operation; outcome uncertain", e);
    } catch (ExecutionException | TimeoutException e) {
      future.cancel(true);
      fail();
      throw new IOException("Native operation failed; outcome uncertain", e);
    }
  }

  boolean alive() {
    return !failed && process.isAlive();
  }

  long pid() {
    return process.pid();
  }

  private void fail() {
    failed = true;
    process.destroyForcibly();
    io.shutdownNow();
  }

  @Override
  public synchronized void close() {
    failed = true;
    process.destroy();
    try {
      if (!process.waitFor(1, TimeUnit.SECONDS)) process.destroyForcibly();
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      process.destroyForcibly();
    }
    io.shutdownNow();
    try {
      reader.close();
      writer.close();
    } catch (IOException ignored) {
    }
  }
}
