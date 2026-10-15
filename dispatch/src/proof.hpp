// SPDX-License-Identifier: MIT
#pragma once
#include "matching.hpp"
#include <set>
namespace foundry {
struct Certificate {
  std::vector<std::int64_t> potential;
  std::vector<int> source_side;
  int cut_capacity;
};
// Independent reconstruction from a claimed matching; does not use the
// optimizer's residual graph or shortest-path implementation.
inline Certificate certify(int workers, int tasks, const std::vector<Choice> &choices,
                           const Matching &matching) {
  validate(workers, tasks, choices);
  const int source = workers + tasks, sink = source + 1, n = sink + 1;
  std::set<std::pair<int, int>> chosen;
  std::set<int> ws, ts;
  std::int64_t cost = 0;
  for (auto pair : matching.pairs) {
    if (!ws.insert(pair.worker).second || !ts.insert(pair.task).second)
      throw std::invalid_argument("matching repeats a vertex");
    auto edge = std::find_if(choices.begin(), choices.end(), [&](auto e) {
      return e.worker == pair.worker && e.task == pair.task && e.cost == pair.cost;
    });
    if (edge == choices.end())
      throw std::invalid_argument("matching contains an unavailable edge");
    chosen.insert({pair.worker, pair.task});
    cost += pair.cost;
  }
  if (matching.cardinality != static_cast<int>(chosen.size()) || matching.cost != cost)
    throw std::invalid_argument("claimed cardinality/cost mismatch");
  struct Arc {
    int a, b;
    std::int64_t cost;
  };
  std::vector<Arc> original, residual;
  auto add = [&](int a, int b, std::int64_t c, bool used) {
    original.push_back({a, b, c});
    residual.push_back(used ? Arc{b, a, -c} : Arc{a, b, c});
  };
  for (int w = 0; w < workers; ++w)
    add(source, w, 0, ws.contains(w));
  for (auto e : choices)
    add(e.worker, workers + e.task, e.cost, chosen.contains({e.worker, e.task}));
  for (int t = 0; t < tasks; ++t)
    add(workers + t, sink, 0, ts.contains(t));
  // Reachability supplies a saturated cut witnessing maximum cardinality.
  std::vector<bool> reachable(n, false);
  reachable[source] = true;
  for (int i = 0; i < n; ++i) {
    bool changed = false;
    for (auto e : residual)
      if (reachable[e.a] && !reachable[e.b]) {
        reachable[e.b] = true;
        changed = true;
      }
    if (!changed)
      break;
  }
  if (reachable[sink])
    throw std::invalid_argument("matching is not maximum cardinality");
  int cut = 0;
  for (auto e : original)
    if (reachable[e.a] && !reachable[e.b])
      ++cut;
  if (cut != matching.cardinality)
    throw std::logic_error("cut witness mismatch");
  // Bellman-Ford from an implicit zero-cost super-source. Feasible node
  // potentials make every residual reduced cost nonnegative, excluding
  // all cost-improving cycles and proving minimum cost at this flow value.
  std::vector<std::int64_t> potential(n, 0);
  for (int i = 0; i < n; ++i) {
    bool changed = false;
    for (auto e : residual)
      if (potential[e.b] > potential[e.a] + e.cost) {
        potential[e.b] = potential[e.a] + e.cost;
        changed = true;
      }
    if (!changed)
      break;
    if (i == n - 1)
      throw std::invalid_argument("matching has a cost-improving residual cycle");
  }
  std::vector<int> side;
  for (int i = 0; i < n; ++i)
    if (reachable[i])
      side.push_back(i);
  return {potential, side, cut};
}
} // namespace foundry
