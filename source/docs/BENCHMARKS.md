# Benchmarks

## Initial callback-parser build

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

## Depth-checking parser improvement

Profiling the 256×256 dense input found that the DOM callback parsing path dominated end-to-end time. A SAX syntax/depth pass followed by normal DOM parsing preserves bounded-depth validation and avoids that slow path. The matching algorithm and objective are unchanged.

On three interleaved, identical-input pairs (65,536 edges each), the initial CLI took 1.852–2.183 seconds and the SAX candidate 0.246–0.264 seconds: approximately 7.9× lower median end-to-end latency in this small shared-host sample. Every result had the same optimum cost as its paired baseline and its certificate passed independent verification. This does not establish an 8× gain for every input or machine. Small inputs also pay for two parsing passes.

[Paired inputs, timings and binary identities](evidence/parser-paired-comparison.json) preserve this comparison. A buffered-stream-only hypothesis showed no improvement in its first probe and was not adopted.

## Current SAX-parser build

All 36 original seeded inputs were rerun and independently certified. Counts and optimum costs match the original cases. These timings are from a later shared-host run, so use the interleaved comparison above for the narrow paired speedup claim.

| Vertices per side | Density | Median matching (ms) | Median full CLI (ms) |
| --- | --- | --- | --- |
| 32 | 8% | 0.158 | 2.078 |
| 32 | 50% | 0.350 | 2.995 |
| 32 | 100% | 0.502 | 5.849 |
| 64 | 8% | 1.004 | 3.732 |
| 64 | 50% | 1.929 | 8.696 |
| 64 | 100% | 2.432 | 13.182 |
| 128 | 8% | 5.350 | 10.673 |
| 128 | 50% | 9.956 | 30.978 |
| 128 | 100% | 13.977 | 57.454 |
| 256 | 8% | 28.691 | 46.317 |
| 256 | 50% | 58.080 | 150.201 |
| 256 | 100% | 140.914 | 389.599 |

[Current raw measurements and exact binary identity](evidence/dispatch-benchmark-current.json).
