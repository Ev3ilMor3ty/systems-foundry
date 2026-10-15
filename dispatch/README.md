# Dispatch

An exact C++20 solver for maximum-cardinality, minimum-cost bipartite matching. A separate certificate builder reconstructs the residual network and emits independently checkable optimality witnesses.

```bash
make
./build/foundry-dispatch < examples/rematching.json
make test
make sanitize
```

The example has edges `(0,0)=1`, `(0,1)=2`, `(1,0)=2`. Cheapest-edge-first greedy takes only one assignment. The exact solution rematches and assigns both pairs for total cost 4.

## JSON interface

A single CLI invocation accepts a complete JSON document, including pretty-printed input. `--serve` accepts one document per line and recovers after an invalid request.

```json
{"workers":2,"tasks":2,"edges":[{"worker":0,"task":0,"cost":1},{"worker":0,"task":1,"cost":2},{"worker":1,"task":0,"cost":2}]}
```

The response contains `optimal`, `greedy`, `certificate`, `solve_us` and `algorithm`. `solve_us` covers the matching algorithm only; it excludes parsing, certificate construction, output and process startup. Greedy is a deterministic reference heuristic, not another exact solver.

Dimensions are 0..256, costs are nonnegative integers up to one billion, and each worker/task edge must be unique. Costs use checked model bounds and 64-bit arithmetic. Input is bounded to 8 MiB and nesting to 32 levels. Negative, fractional, repeated or out-of-range edges fail with an explicit error.

## Verify without optimizing

Save a request and response, then run:

```bash
python3 tools/check_certificate.py request.json response.json
```

The same tool accepts the single proof bundle downloaded from Control Room. It checks matching feasibility, totals, the saturated cut and every reduced-cost inequality. Validation remains enabled under Python's optimized mode.

See [the proof argument and vertex numbering](../docs/ARCHITECTURE.md#optimizer-boundary).

## Evidence

Tests enumerate all 512 graph topologies of a 3×3 problem and compare 1,800 seeded random small problems with a brute-force search. Another 350 larger random problems have their certificates checked by the Python implementation. Sanitizer runs exercise matching, rematching, 64-bit totals and invalid bounds. Larger benchmark instances are also certificate-checked; timing is reported with its environment and scope.

The project uses nlohmann/json 3.12.0 for parsing and serialization, with its MIT notice preserved under `vendor/`. The optimizer and verifier code are MIT.
