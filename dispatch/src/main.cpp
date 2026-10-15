// SPDX-License-Identifier: MIT
#include "json.hpp"
#include "matching.hpp"
#include "proof.hpp"
#include <chrono>
#include <iostream>
#include <string>
using nlohmann::json;

// Validate syntax and depth without the slower DOM callback path.
class DepthGuard final : public nlohmann::json_sax<json> {
  std::size_t depth = 0;

public:
  bool null() override { return true; }
  bool boolean(bool) override { return true; }
  bool number_integer(json::number_integer_t) override { return true; }
  bool number_unsigned(json::number_unsigned_t) override { return true; }
  bool number_float(json::number_float_t, const json::string_t &) override { return true; }
  bool string(json::string_t &) override { return true; }
  bool binary(json::binary_t &) override { return true; }
  bool start_object(std::size_t) override { return ++depth <= 32; }
  bool key(json::string_t &) override { return true; }
  bool end_object() override {
    --depth;
    return true;
  }
  bool start_array(std::size_t) override { return ++depth <= 32; }
  bool end_array() override {
    --depth;
    return true;
  }
  bool parse_error(std::size_t, const std::string &, const json::exception &) override {
    return false;
  }
};

static int integer(const json &value) {
  if (!value.is_number_integer() || value < 0 || value > 256)
    throw std::invalid_argument("expected integer in 0..256");
  return value.get<int>();
}
static json result_json(const foundry::Matching &r) {
  json pairs = json::array();
  for (auto e : r.pairs)
    pairs.push_back({{"worker", e.worker}, {"task", e.task}, {"cost", e.cost}});
  return {{"cardinality", r.cardinality}, {"cost", r.cost}, {"pairs", pairs}};
}
static json run(const std::string &line) {
  DepthGuard guard;
  if (!json::sax_parse(line, &guard))
    throw std::invalid_argument("Invalid JSON or nesting exceeds 32 levels");
  auto request = json::parse(line);
  if (!request.is_object())
    throw std::invalid_argument("request must be an object");
  int workers = integer(request.at("workers")), tasks = integer(request.at("tasks"));
  const auto &list = request.at("edges");
  if (!list.is_array() || list.size() > 65536)
    throw std::invalid_argument("invalid edges array");
  std::vector<foundry::Choice> choices;
  for (const auto &e : list) {
    if (!e.at("cost").is_number_integer() || e.at("cost") < 0 || e.at("cost") > 1'000'000'000)
      throw std::invalid_argument("cost must be an integer in 0..1000000000");
    choices.push_back(
        {integer(e.at("worker")), integer(e.at("task")), e.at("cost").get<std::int64_t>()});
  }
  auto start = std::chrono::steady_clock::now();
  auto result = foundry::solve(workers, tasks, choices);
  auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
                     std::chrono::steady_clock::now() - start)
                     .count();
  auto proof = foundry::certify(workers, tasks, choices, result);
  return {{"certificate",
           {{"schema", 1},
            {"potential", proof.potential},
            {"source_side", proof.source_side},
            {"cut_capacity", proof.cut_capacity}}},
          {"ok", true},
          {"optimal", result_json(result)},
          {"greedy", result_json(foundry::greedy(workers, tasks, choices))},
          {"solve_us", elapsed},
          {"algorithm", "min-cost-max-flow/potentials"}};
}
int main(int argc, char **argv) {
  bool serve = argc == 2 && std::string(argv[1]) == "--serve";
  if (argc > 1 && !serve) {
    std::cerr << "usage: foundry-dispatch [--serve] < request.json\n";
    return 2;
  }
  do {
    std::string line;
    char c;
    bool oversized = false;
    while (std::cin.get(c)) {
      if (serve && c == '\n')
        break;
      if (line.size() < 8 * 1024 * 1024)
        line.push_back(c);
      else
        oversized = true;
    }
    if (line.empty() && !std::cin)
      break;
    try {
      if (oversized)
        throw std::invalid_argument("input exceeds 8 MiB");
      std::cout << run(line).dump() << '\n' << std::flush;
    } catch (const std::exception &e) {
      std::cout << json({{"ok", false}, {"error", e.what()}}).dump() << '\n' << std::flush;
      if (!serve)
        return 1;
    }
  } while (serve && std::cin);
}
