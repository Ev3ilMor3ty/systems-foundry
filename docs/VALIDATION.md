# Validation and limits

The repository records finite checks rather than claims of production readiness. Binary identities accompany integration and browser results. Long-running jobs are scoped separately and are not called passed until they finish.

## Completed checks

| Area | Evidence |
| --- | --- |
| C++ exactness | 512 exhaustive 3×3 graph topologies plus 1,800 seeded random small instances, compared with brute force |
| Independent proofs | 350 seeded larger random inputs checked by Python, plus Java certificate checks on the live API boundary |
| C++ safety/protocol | Address/undefined-behavior sanitizer run; rematching, 64-bit totals, bounds, malformed requests, nesting limits and pretty-printed CLI input |
| Rust ledger | Four integration-style Rust tests covering reopen/idempotency, locks, corruption, reordering, truncation, limits and multi-record replay |
| Real filesystem faults | Writer SIGKILL after acknowledgements, cross-process locks, actual partial write/EFBIG, retained corrupt tail, incomplete protocol input and oversized file rejection |
| Java | 16 JUnit tests across state/concurrency/storage behavior, real HTTP, native peer faults and proof verification |
| Live integration | Actual Java → C++/Rust flow; all initial requests delivered; restart with exact state/head; eight crash timings with exactly-once retries; killed dependencies cannot commit partial changes |
| Browser | Real API, proof download independently verified, text safely rendered, filters and controls, visible failure/recovery, widths 320/390/768/1024/1440 with no document overflow |
| Automated accessibility | Zero axe WCAG 2 A/AA and 2.1 AA violations in the tested desktop state; this is not full conformance certification |
| UI model | Six Node tests covering metrics, routes, bounds, stale revisions, ordering and dispatch eligibility |
| Endurance smoke | Corrected workload completed 853 operations, 238 proof checks, four restarts including one crash retry, and final trusted-head ledger verification |

See [integration evidence](evidence/integration.json), [browser evidence](evidence/ui/result.json) and [accessibility details](evidence/ui/accessibility.json). The companion kernel repository preserves its own module/VM evidence.

## Endurance jobs

A separately frozen application run was launched for 4.5 hours at a modest five-second command cadence, with idempotent retries, independent proof checks, validation failures, SSE reconnects, periodic restarts, crash injection, memory sampling and final anchored ledger verification. The kernel repository has a separate four-hour VM lifecycle soak.

**Launched is not completed.** A final run must have `complete: true` and a completed phase. Interrupted, failed or still-running jobs are not presented as passes. Results apply to their recorded binaries and options, not automatically to a later configuration.

The first application smoke exposed a driver that repeatedly asked for a plan when the idle carrier lacked the queued capability. The corrected driver advances time in that case, and dashboard Auto run uses the same eligibility condition. The earlier smoke is preserved separately and is not evidence that the corrected full workflow was exercised.

## What these checks do not establish

- General vehicle-routing optimality, realistic travel prediction or real logistics performance.
- A cryptographically authenticated ledger without an independent trusted head.
- Power-loss guarantees beyond the filesystem/storage's sync contract.
- Unbounded throughput, unlimited history or zero defects.
- Complete accessibility, platform or browser compatibility from one automated suite.
- Native Windows support until the Windows CI build and portable checks actually pass.

See [benchmark methodology](BENCHMARKS.md) for the distinction between algorithm timing and end-to-end process latency. Local compilation and VM testing used a two-core quota on a shared Linux development host.
