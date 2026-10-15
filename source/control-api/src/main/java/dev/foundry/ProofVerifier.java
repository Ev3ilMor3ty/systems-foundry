package dev.foundry;

import com.google.gson.*;
import java.util.*;

/** Linear-time verifier for the optimizer's primal, cut and dual witnesses. */
final class ProofVerifier {
  private static long number(JsonElement v, long min, long max) {
    return Json.integer(Json.obj("v", v), "v", min, max);
  }

  static void verify(JsonObject input, JsonObject response) {
    int workers = (int) Json.integer(input, "workers", 0, 256),
        tasks = (int) Json.integer(input, "tasks", 0, 256);
    int source = workers + tasks, sink = source + 1, n = sink + 1;
    var edges = new HashMap<Integer, Long>();
    for (var raw : input.getAsJsonArray("edges")) {
      var e = raw.getAsJsonObject();
      int w = (int) Json.integer(e, "worker", 0, workers - 1),
          t = (int) Json.integer(e, "task", 0, tasks - 1);
      long cost = Json.integer(e, "cost", 0, 1_000_000_000);
      if (edges.put(w * 256 + t, cost) != null)
        throw new IllegalArgumentException("Duplicate problem edge");
    }
    var result = response.getAsJsonObject("optimal");
    var pairs = result.getAsJsonArray("pairs");
    var ws = new HashSet<Integer>();
    var ts = new HashSet<Integer>();
    var chosen = new HashSet<Integer>();
    long cost = 0;
    for (var raw : pairs) {
      var e = raw.getAsJsonObject();
      int w = (int) Json.integer(e, "worker", 0, workers - 1),
          t = (int) Json.integer(e, "task", 0, tasks - 1);
      long c = Json.integer(e, "cost", 0, 1_000_000_000);
      if (!ws.add(w) || !ts.add(t) || !Objects.equals(edges.get(w * 256 + t), c))
        throw new IllegalArgumentException("Infeasible matching witness");
      chosen.add(w * 256 + t);
      cost += c;
    }
    if (Json.integer(result, "cardinality", 0, 256) != pairs.size()
        || Json.integer(result, "cost", 0, 256_000_000_000L) != cost)
      throw new IllegalArgumentException("Incorrect matching totals");
    var certificate = response.getAsJsonObject("certificate");
    Json.integer(certificate, "schema", 1, 1);
    var rawPotential = certificate.getAsJsonArray("potential");
    if (rawPotential.size() != n) throw new IllegalArgumentException("Wrong potential dimension");
    long[] p = new long[n];
    for (int i = 0; i < n; i++)
      p[i] = number(rawPotential.get(i), -1_000_000_000_000_000L, 1_000_000_000_000_000L);
    boolean[] side = new boolean[n];
    for (var v : certificate.getAsJsonArray("source_side")) {
      int vertex = (int) number(v, 0, n - 1);
      if (side[vertex]) throw new IllegalArgumentException("Repeated cut vertex");
      side[vertex] = true;
    }
    if (!side[source] || side[sink])
      throw new IllegalArgumentException("Cut does not separate source and sink");
    int cut = 0;
    for (int w = 0; w < workers; w++) cut += arc(source, w, 0, ws.contains(w), side, p);
    for (var edge : edges.entrySet()) {
      int w = edge.getKey() / 256, t = edge.getKey() % 256;
      cut += arc(w, workers + t, edge.getValue(), chosen.contains(edge.getKey()), side, p);
    }
    for (int t = 0; t < tasks; t++) cut += arc(workers + t, sink, 0, ts.contains(t), side, p);
    if (cut != pairs.size() || Json.integer(certificate, "cut_capacity", 0, 256) != cut)
      throw new IllegalArgumentException("Cut does not prove maximum cardinality");
  }

  private static int arc(int a, int b, long cost, boolean used, boolean[] side, long[] potential) {
    int cut = side[a] && !side[b] ? 1 : 0;
    if (used) {
      int old = a;
      a = b;
      b = old;
      cost = -cost;
    }
    if (side[a] && !side[b]) throw new IllegalArgumentException("Residual path crosses cut");
    if (cost + potential[a] - potential[b] < 0)
      throw new IllegalArgumentException("Dual potential does not prove minimum cost");
    return cut;
  }
}
