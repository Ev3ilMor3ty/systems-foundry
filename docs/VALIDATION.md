# Validation and limits

The repository records finite checks rather than claims of production readiness. Binary identities accompany integration and browser results. Long-running jobs are scoped separately and are not called passed until they finish.

## Completed checks

| Area | Evidence |
| --- | --- |
| C++ exactness | 512 exhaustive 3×3 graph topologies plus 1,800 seeded random small instances, compared with brute force |
| Independent proofs | 350 seeded larger random inputs checked by Python, plus Java certificate checks on the live API boundary |
| C++ safety/protocol | Address/undefined-behavior sanitizer runs on both the matching library and JSON CLI; rematching, 64-bit totals, bounds, malformed requests, nesting limits and pretty-printed CLI input |
| Rust ledger | Four integration-style Rust tests covering reopen/idempotency, locks, corruption, reordering, truncation, limits and multi-record replay |
| Real filesystem faults | Writer SIGKILL after acknowledgements, cross-process locks, actual partial write/EFBIG, retained corrupt tail, incomplete protocol input and oversized file rejection |
| Java | 17 JUnit tests across state/concurrency/storage behavior, real HTTP, native peer faults and proof verification |
| Live integration | Actual Java → C++/Rust flow; all initial requests delivered; restart with exact state/head; eight crash timings with exactly-once retries; killed dependencies cannot commit partial changes |
| Browser | Real API, proof download independently verified, text safely rendered, filters and controls, visible failure/recovery, widths 320/390/768/1024/1440 with no document overflow |
| Automated accessibility | Zero axe WCAG 2 A/AA and 2.1 AA violations in the tested desktop state; this is not full conformance certification |
| Auto workflow | All 12 requests delivered and carriers released through real API calls, using an accelerated browser timer; separate from elapsed-time endurance |
| UI model | Six Node tests covering metrics, routes, bounds, stale revisions, ordering and dispatch eligibility |
| Endurance smoke | Corrected workload completed 853 operations, 238 proof checks, four restarts including one crash retry, and final trusted-head ledger verification |

See [integration evidence](evidence/integration.json), [browser evidence](evidence/ui/result.json) and [accessibility details](evidence/ui/accessibility.json). The companion kernel repository preserves its own module/VM evidence.

## Endurance jobs

A separately frozen application run was launched for 4.5 hours at a modest five-second command cadence, with idempotent retries, independent proof checks, validation failures, SSE reconnects, periodic restarts, crash injection, memory sampling and final anchored ledger verification. The kernel repository has a separate four-hour VM lifecycle soak.

**The application run did not complete:** its retry assertion failed after 2,100 completed operations, 585 checked proofs and 12 restarts (four involving crash injection), at about 2 hours 55 minutes. Its preserved ledger and [incomplete checkpoint summary](evidence/endurance-incomplete.json) are under investigation. It is not a passed 4.5-hour run. The separate kernel soak completed four hours successfully. A changed application configuration does not inherit either result.

The first application smoke exposed a driver that repeatedly asked for a plan when the idle carrier lacked the queued capability. The corrected driver advances time in that case, and dashboard Auto run uses the same eligibility condition. The earlier smoke is preserved separately and is not evidence that the corrected full workflow was exercised.

## What these checks do not establish

- General vehicle-routing optimality, realistic travel prediction or real logistics performance.
- A cryptographically authenticated ledger without an independent trusted head.
- Power-loss guarantees beyond the filesystem/storage's sync contract.
- Unbounded throughput, unlimited history or zero defects.
- Complete accessibility, platform or browser compatibility from one automated suite.
- Windows scenarios beyond the native CI build and portable checks that passed in [run 38737102319](https://github.com/Ev3ilMor3ty/systems-foundry/actions/runs/38737102319).

See [benchmark methodology](BENCHMARKS.md) for the distinction between algorithm timing and end-to-end process latency. Local compilation and VM testing used a two-core quota on a shared Linux development host.

## Carrier-starvation fix

The old build deterministically returned HTTP 503 after about three seconds when the Java 21 virtual-thread scheduler was restricted to one carrier. It waited for another virtual IPC task while holding intrinsic monitors. The corrected build uses ReentrantLock guards and dedicated platform threads for blocking pipe I/O. The single-carrier regression now completes a real command, five eight-way competing-write batches, 80 concurrent snapshots, an exact dispatch and final anchored verification.

See [before/after evidence](evidence/carrier-starvation-comparison.json). This reproduces and fixes a starvation path consistent with the overnight timeout timing. The old soak did not retain the failed response or Java cause, so the exact original cause is not proven. The failed run remains incomplete. New failures now record the retry response and native exception type instead of discarding that context.

The initial Linux browser CI failure came from waiting for network idle on a page with a live event stream. The harness now waits for DOM content and the actual application-ready state; it does not weaken the page's content security policy.

The fixed build also completed a fresh one-carrier smoke: 616 operations, 172 proof checks and three restarts including a crash retry. A new separately frozen 4.5-hour one-carrier run is in progress; it has no completed endurance result yet.

The adopted parser candidate is tested separately from the still-running carrier-fix endurance job. That job keeps its original frozen C++ binary; its result must not be relabeled as a full endurance result for a changed native binary.
