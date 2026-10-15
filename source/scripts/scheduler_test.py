#!/usr/bin/env python3
"""Regression for Java 21 carrier starvation across real HTTP/native boundaries."""
import concurrent.futures, json, pathlib, subprocess, sys, tempfile, time
from harness import ROOT, Server, freeze

sys.path.insert(0, str(ROOT / "dispatch/tools"))
from check_certificate import verify


def main():
    with tempfile.TemporaryDirectory(prefix="foundry single carrier ") as temp:
        temp = pathlib.Path(temp)
        binaries = temp / "binaries"
        identity = freeze(ROOT, binaries)
        with Server(
            binaries,
            temp / "state",
            java_options=[
                "-Djdk.virtualThreadScheduler.parallelism=1",
                "-Djdk.virtualThreadScheduler.maxPoolSize=1",
            ],
        ) as server:
            start = time.monotonic()
            status, response = server.post(
                "advance",
                {"commandId": "one-carrier", "expectedRevision": 0, "ticks": 1},
            )
            assert status == 200, (status, response)
            first_ms = (time.monotonic() - start) * 1000
            for batch in range(5):
                before = server.get()
                revision = before["revision"]

                def mutate(i):
                    return server.post(
                        "advance",
                        {
                            "commandId": f"parallel:{batch}:{i}",
                            "expectedRevision": revision,
                            "ticks": 1,
                        },
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                    results = list(pool.map(mutate, range(8)))
                assert sorted(code for code, _ in results) == [200] + [409] * 7, results
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                    snapshots = list(pool.map(lambda _: server.get(), range(16)))
                assert all(s["revision"] == revision + 1 for s in snapshots)
            result = server.command("plan", "single-carrier-plan")
            plan = result["state"]["latestPlan"]
            verify(plan["problem"], plan)
            final = server.get()
            server.stop()
            checked = subprocess.run(
                [
                    binaries / "chronicle",
                    "verify",
                    server.data / "events.jsonl",
                    final["audit"]["head"],
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            report = {
                "ok": True,
                "scheduler_parallelism": 1,
                "scheduler_max_pool_size": 1,
                "first_command_ms": round(first_ms, 3),
                "concurrent_write_batches": 5,
                "writes_per_batch": 8,
                "concurrent_snapshots": 80,
                "binary_sha256": identity,
                "final_ledger": json.loads(checked.stdout),
            }
    output = ROOT / "docs/evidence/single-carrier-regression.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
