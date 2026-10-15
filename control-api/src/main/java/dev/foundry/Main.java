package dev.foundry;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.CountDownLatch;

public final class Main {
  public static void main(String[] args) throws Exception {
    var options = new HashMap<String, String>();
    for (int i = 0; i < args.length; i += 2) {
      if (i + 1 == args.length
          || !Set.of("--root", "--data", "--port", "--chronicle", "--dispatch").contains(args[i]))
        throw new IllegalArgumentException(
            "Options: --root PATH --data PATH --port 8090 --chronicle BINARY --dispatch BINARY");
      options.put(args[i], args[i + 1]);
    }
    Path root = Path.of(options.getOrDefault("--root", ".")).toAbsolutePath().normalize();
    Path data =
        Path.of(options.getOrDefault("--data", root.resolve(".run").toString()))
            .toAbsolutePath()
            .normalize();
    Files.createDirectories(data);
    String executableSuffix = System.getProperty("os.name").startsWith("Windows") ? ".exe" : "";
    Path chronicle =
        Path.of(
            options.getOrDefault(
                "--chronicle",
                root.resolve("chronicle/target/release/foundry-chronicle" + executableSuffix).toString()));
    Path dispatch =
        Path.of(
            options.getOrDefault(
                "--dispatch", root.resolve("dispatch/build/foundry-dispatch" + executableSuffix).toString()));
    int port = Integer.parseInt(options.getOrDefault("--port", "8090"));
    if (port < 0 || port > 65535) throw new IllegalArgumentException("Invalid port");
    System.setProperty("sun.net.httpserver.maxReqTime", "15");
    System.setProperty("sun.net.httpserver.idleInterval", "20");
    try (var ledger =
            new Ports.Ledger(
                chronicle, data.resolve("events.jsonl"), data.resolve("chronicle.log"));
        var solver = new Ports.Solver(dispatch, data.resolve("dispatch.log"))) {
      var hub = new EventHub();
      var service = new FoundryService(ledger, solver, hub::publish);
      try (var server = new ControlServer(port, service, hub, root.resolve("control-room"))) {
        server.start();
        var done = new CountDownLatch(1);
        Runtime.getRuntime()
            .addShutdownHook(
                new Thread(
                    () -> {
                      server.close();
                      done.countDown();
                    },
                    "foundry-shutdown"));
        System.out.println("Systems Foundry listening at http://127.0.0.1:" + server.port());
        done.await();
      }
    }
  }
}
