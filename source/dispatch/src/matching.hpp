// SPDX-License-Identifier: MIT
#pragma once
#include <algorithm>
#include <cstdint>
#include <functional>
#include <limits>
#include <queue>
#include <stdexcept>
#include <tuple>
#include <utility>
#include <vector>

namespace foundry {
struct Choice {
  int worker, task;
  std::int64_t cost;
};
struct Matching {
  int cardinality = 0;
  std::int64_t cost = 0;
  std::vector<Choice> pairs;
};

inline void validate(int workers, int tasks, const std::vector<Choice> &choices) {
  if (workers < 0 || workers > 256 || tasks < 0 || tasks > 256)
    throw std::invalid_argument("workers and tasks must be in 0..256");
  if (choices.size() > static_cast<std::size_t>(workers) * tasks)
    throw std::invalid_argument("too many edges");
  std::vector<bool> seen(static_cast<std::size_t>(workers) * tasks, false);
  for (auto e : choices) {
    if (e.worker < 0 || e.worker >= workers || e.task < 0 || e.task >= tasks || e.cost < 0 ||
        e.cost > 1'000'000'000)
      throw std::invalid_argument("edge index or cost outside bounds");
    auto i = static_cast<std::size_t>(e.worker) * tasks + e.task;
    if (seen[i])
      throw std::invalid_argument("duplicate worker/task edge");
    seen[i] = true;
  }
}

// Successive shortest augmenting paths with reduced-cost potentials.
// Objective is lexicographic: maximum assignments, then minimum total cost.
// Complexity O(F * E log V), F <= min(workers,tasks), all capacities one.
inline Matching solve(int workers, int tasks, const std::vector<Choice> &choices) {
  validate(workers, tasks, choices);
  struct Edge {
    int to, reverse, capacity;
    std::int64_t cost;
  };
  const int source = workers + tasks, sink = source + 1, n = sink + 1;
  std::vector<std::vector<Edge>> graph(n);
  auto add = [&](int a, int b, std::int64_t cost) {
    int ia = static_cast<int>(graph[a].size()), ib = static_cast<int>(graph[b].size());
    graph[a].push_back({b, ib, 1, cost});
    graph[b].push_back({a, ia, 0, -cost});
  };
  for (int w = 0; w < workers; ++w)
    add(source, w, 0);
  for (int t = 0; t < tasks; ++t)
    add(workers + t, sink, 0);
  // Stable edge ordering makes ties deterministic for a given graph.
  auto ordered = choices;
  std::sort(ordered.begin(), ordered.end(),
            [](auto a, auto b) { return std::tie(a.worker, a.task) < std::tie(b.worker, b.task); });
  for (auto e : ordered)
    add(e.worker, workers + e.task, e.cost);
  std::vector<std::int64_t> potential(n, 0), distance(n);
  std::vector<int> parent(n), edge_index(n);
  constexpr std::int64_t infinity = std::numeric_limits<std::int64_t>::max() / 4;
  Matching result;
  for (;;) {
    std::fill(distance.begin(), distance.end(), infinity);
    std::fill(parent.begin(), parent.end(), -1);
    using Node = std::pair<std::int64_t, int>;
    std::priority_queue<Node, std::vector<Node>, std::greater<Node>> queue;
    distance[source] = 0;
    queue.push({0, source});
    while (!queue.empty()) {
      auto [d, u] = queue.top();
      queue.pop();
      if (d != distance[u])
        continue;
      for (int i = 0; i < static_cast<int>(graph[u].size()); ++i) {
        const auto &e = graph[u][i];
        if (!e.capacity)
          continue;
        const auto reduced = e.cost + potential[u] - potential[e.to];
        if (reduced < 0)
          throw std::logic_error("negative reduced cost invariant");
        if (d + reduced < distance[e.to]) {
          distance[e.to] = d + reduced;
          parent[e.to] = u;
          edge_index[e.to] = i;
          queue.push({distance[e.to], e.to});
        }
      }
    }
    if (parent[sink] < 0)
      break;
    for (int v = 0; v < n; ++v)
      if (distance[v] != infinity)
        potential[v] += distance[v];
    for (int v = sink; v != source; v = parent[v]) {
      auto &e = graph[parent[v]][edge_index[v]];
      result.cost += e.cost;
      --e.capacity;
      ++graph[v][e.reverse].capacity;
    }
    ++result.cardinality;
  }
  for (int w = 0; w < workers; ++w)
    for (const auto &e : graph[w])
      if (e.to >= workers && e.to < workers + tasks && e.capacity == 0)
        result.pairs.push_back({w, e.to - workers, e.cost});
  return result;
}

inline Matching greedy(int workers, int tasks, std::vector<Choice> edges) {
  validate(workers, tasks, edges);
  std::sort(edges.begin(), edges.end(), [](auto a, auto b) {
    return std::tie(a.cost, a.worker, a.task) < std::tie(b.cost, b.worker, b.task);
  });
  std::vector<bool> ws(workers), ts(tasks);
  Matching m;
  for (auto e : edges)
    if (!ws[e.worker] && !ts[e.task]) {
      ws[e.worker] = ts[e.task] = true;
      m.pairs.push_back(e);
      ++m.cardinality;
      m.cost += e.cost;
    }
  return m;
}
} // namespace foundry
