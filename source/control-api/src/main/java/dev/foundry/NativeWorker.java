package dev.foundry;

import com.google.gson.JsonObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.locks.ReentrantLock;

/** Bounded JSON-line IPC. A timed-out worker is killed and never reused. */
final class NativeWorker implements AutoCloseable {
  private final ReentrantLock exchangeLock = new ReentrantLock();
  private final Process process;
  private final BufferedReader reader;
  private final BufferedWriter writer;
  private final ExecutorService io =
      Executors.newSingleThreadExecutor(
          Thread.ofPlatform().daemon(true).name("native-ipc-", 0).factory());
  private volatile boolean failed;

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

  JsonObject exchange(JsonObject request, Duration timeout) throws IOException {
    exchangeLock.lock();
    try {
      return exchangeLocked(request, timeout);
    } finally {
      exchangeLock.unlock();
    }
  }

  private JsonObject exchangeLocked(JsonObject request, Duration timeout) throws IOException {
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
              if (!response.has("ok")
                  || !response.get("ok").isJsonPrimitive()
                  || !response.get("ok").getAsJsonPrimitive().isBoolean()
                  || !response.get("ok").getAsBoolean())
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
      Throwable cause = e instanceof ExecutionException && e.getCause() != null ? e.getCause() : e;
      System.err.printf(
          "native worker failure pid=%d operation=%s type=%s%n",
          process.pid(),
          request.has("op") ? request.get("op").getAsString() : "solve",
          cause.getClass().getSimpleName());
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
  public void close() {
    exchangeLock.lock();
    try {
      closeLocked();
    } finally {
      exchangeLock.unlock();
    }
  }

  private void closeLocked() {
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
