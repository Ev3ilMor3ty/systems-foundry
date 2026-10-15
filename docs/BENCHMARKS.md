# Benchmarks

These seeded observations describe this build on a shared Linux development host with a two-core quota. A low-duty QEMU soak was also running. They are illustrative measurements, not a controlled cross-machine performance comparison.

Every benchmark result was independently checked using the Python primal/dual certificate verifier. There are 36 cases: four square problem sizes, three edge densities and three trials per combination. Seed: `0xF01D2026`.

| Vertices per side | Density | Median solver time (ms) | Median whole CLI time (ms) |
| --- | --- | --- | --- |
| 32 | 8% | 0.197 | 7.722 |
| 32 | 50% | 0.425 | 9.747 |
| 32 | 100% | 0.583 | 11.682 |
| 64 | 8% | 1.015 | 4.246 |
| 64 | 50% | 2.189 | 12.218 |
| 64 | 100% | 3.152 | 31.439 |
| 128 | 8% | 5.457 | 11.636 |
| 128 | 50% | 10.487 | 69.068 |
| 128 | 100% | 16.443 | 172.509 |
| 256 | 8% | 27.205 | 55.178 |
| 256 | 50% | 62.949 | 570.739 |
| 256 | 100% | 97.298 | 2149.124 |

`solve_us` covers matching only. Whole CLI time includes process startup, parsing, certificate construction, serialization and exit. It excludes the separate Python verification. Costs and timings are scoped to the generated inputs; greedy comparisons are meaningful lexicographically (assignment count first, then cost at equal cardinality).

Raw cases, edge counts, input hashes, costs, timings, environment and exact binary identity are in [the benchmark JSON](evidence/dispatch-benchmark.json).

Reproduce:

```bash
make -C dispatch
python3 dispatch/tools/benchmark.py
```

The native executables may depend on the compiler/runtime used to build them. Rebuild locally to measure your own environment.
