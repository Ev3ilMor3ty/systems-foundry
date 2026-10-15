// SPDX-License-Identifier: MIT
#include "matching.hpp"
#include "proof.hpp"
#include <cstdlib>
#include <iostream>
#include <random>
#include <set>
#define CHECK(condition)                                                                           \
  do {                                                                                             \
    if (!(condition)) {                                                                            \
      std::cerr << "failed at line " << __LINE__ << ": " << #condition << '\n';                    \
      std::exit(1);                                                                                \
    }                                                                                              \
  } while (false)
using foundry::Choice;
static std::pair<int, std::int64_t> brute(int workers, int tasks,
                                          const std::vector<Choice> &edges) {
  std::pair<int, std::int64_t> best = {0, 0};
  std::function<void(int, int, int, std::int64_t)> visit = [&](int w, int used, int count,
                                                               std::int64_t cost) {
    if (w == workers) {
      if (count > best.first || (count == best.first && cost < best.second))
        best = {count, cost};
      return;
    }
    visit(w + 1, used, count, cost);
    for (auto e : edges)
      if (e.worker == w && !(used & (1 << e.task)))
        visit(w + 1, used | (1 << e.task), count + 1, cost + e.cost);
  };
  (void)tasks;
  visit(0, 0, 0, 0);
  return best;
}
int main() {
  std::mt19937 rng(0xF01D123);
  std::size_t cases = 0;
  // Enumerate every topology for a 3x3 graph with varied deterministic costs.
  for (int mask = 0; mask < (1 << 9); ++mask) {
    std::vector<Choice> e;
    for (int i = 0; i < 9; ++i)
      if (mask & (1 << i))
        e.push_back({i / 3, i % 3, (i * 13 + mask) % 19});
    auto r = foundry::solve(3, 3, e);
    auto b = brute(3, 3, e);
    CHECK(r.cardinality == b.first && r.cost == b.second);
    CHECK(foundry::certify(3, 3, e, r).cut_capacity == r.cardinality);
    ++cases;
  }
  for (int i = 0; i < 1800; ++i) {
    int w = static_cast<int>(rng() % 7), t = static_cast<int>(rng() % 7);
    std::vector<Choice> e;
    for (int a = 0; a < w; ++a)
      for (int b = 0; b < t; ++b)
        if (rng() % 4)
          e.push_back({a, b, static_cast<std::int64_t>(rng() % 100)});
    auto r = foundry::solve(w, t, e);
    auto b = brute(w, t, e);
    CHECK(r.cardinality == b.first && r.cost == b.second);
    CHECK(foundry::certify(w, t, e, r).cut_capacity == r.cardinality);
    std::set<int> ws, ts;
    std::int64_t sum = 0;
    for (auto x : r.pairs) {
      CHECK(ws.insert(x.worker).second);
      CHECK(ts.insert(x.task).second);
      sum += x.cost;
    }
    CHECK(sum == r.cost);
    CHECK(static_cast<int>(r.pairs.size()) == r.cardinality);
    ++cases;
  }
  auto r = foundry::solve(2, 2, {{0, 0, 1}, {0, 1, 2}, {1, 0, 2}});
  CHECK(r.cardinality == 2 && r.cost == 4);
  std::vector<Choice> big;
  for (int i = 0; i < 256; ++i)
    big.push_back({i, i, 1'000'000'000});
  CHECK(foundry::solve(256, 256, big).cost == 256'000'000'000LL);
  for (auto invalid : std::vector<std::vector<Choice>>{
           {{0, 0, -1}}, {{2, 0, 0}}, {{0, 0, 1}, {0, 0, 2}}, {{0, 0, 1'000'000'001}}}) {
    bool rejected = false;
    try {
      foundry::solve(2, 2, invalid);
    } catch (const std::invalid_argument &) {
      rejected = true;
    }
    CHECK(rejected);
  }
  bool rejected = false;
  try {
    foundry::certify(2, 2, {{0, 0, 1}, {0, 1, 2}, {1, 0, 2}},
                     foundry::greedy(2, 2, {{0, 0, 1}, {0, 1, 2}, {1, 0, 2}}));
  } catch (const std::invalid_argument &) {
    rejected = true;
  }
  CHECK(rejected);
  rejected = false;
  try {
    foundry::certify(2, 2, {{0, 0, 1}, {0, 1, 5}, {1, 0, 5}, {1, 1, 1}},
                     foundry::Matching{2, 10, {{0, 1, 5}, {1, 0, 5}}});
  } catch (const std::invalid_argument &) {
    rejected = true;
  }
  CHECK(rejected);
  std::cout << "PASS " << cases
            << " brute-force cross-checks, rematching, bounds and 64-bit cost\n";
}
