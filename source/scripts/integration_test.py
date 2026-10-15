#!/usr/bin/env python3
"""Exercise real Java -> C++/Rust boundaries, restart and crash recovery."""
import concurrent.futures, json, pathlib, subprocess, sys, tempfile, time
from harness import ROOT, Server, freeze

sys.path.insert(0, str(ROOT / "dispatch/tools"))
from check_certificate import verify


def run(output):
    results = []
    with tempfile.TemporaryDirectory(prefix="foundry integration with spaces ") as temp:
        temp = pathlib.Path(temp)
        binaries = temp / "frozen binaries"
        identities = freeze(ROOT, binaries)
        server = Server(binaries, temp / "workspace state").start()
        try:
            assert len(server.get()["tasks"]) == 12
            planned = server.command("plan", "integration-plan")["state"]
            plan = planned["latestPlan"]
            assert verify(plan["problem"], plan)["ok"]
            assert sum(t["status"] == "active" for t in planned["tasks"]) == 6
            results.append("real optimizer dispatch and independent proof")
            for i in range(8):
                server.command("advance", f"complete-{i}", ticks=30)
                state = server.get()
                if all(t["status"] == "done" for t in state["tasks"]):
                    break
                server.command("plan", f"plan-{i}")
            assert all(t["status"] == "done" for t in server.get()["tasks"])
            results.append("all twelve tasks complete and carriers released")
            before = server.get()
            server.stop()
            server.start()
            after = server.get()
            assert before == after
            results.append("graceful restart preserves state and exact chain head")
            # Acknowledgement can be lost around a crash. Retrying the same
            # request must lead to one, and only one, durable transition.
            for i, delay in enumerate(
                [0, 0.0005, 0.001, 0.003, 0.006, 0.01, 0.02, 0.04]
            ):
                before = server.get()
                request = {
                    "commandId": f"crash-{i}",
                    "expectedRevision": before["revision"],
                    "ticks": 1,
                }
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    pending = pool.submit(server.post, "advance", request)
                    time.sleep(delay)
                    server.stop(crash=True)
                    try:
                        pending.result(timeout=10)
                    except Exception:
                        pass  # Connection loss is the fault being injected.
                server.start()
                status, response = server.post("advance", request)
                assert status == 200, (status, response)
                current = server.get()
                assert current["revision"] == before["revision"] + 1
                assert current["tick"] == before["tick"] + 1
                status, replay = server.post("advance", request)
                assert status == 200 and replay["replayed"]
                assert server.get()["revision"] == current["revision"]
            results.append("eight crash timings with exactly-once idempotent retries")
            revision = server.get()["revision"]
            server.kill_child("dispatch")
            time.sleep(0.05)
            status, _ = server.post(
                "plan", {"commandId": "dead-solver", "expectedRevision": revision}
            )
            assert status == 503 and server.get()["revision"] == revision
            assert not server.get()["dependencies"]["optimizer"]
            results.append("optimizer death cannot commit a partial plan")
            server.stop()
            server.start()
            revision = server.get()["revision"]
            server.kill_child("chronicle")
            time.sleep(0.05)
            status, _ = server.post(
                "advance",
                {"commandId": "dead-ledger", "expectedRevision": revision, "ticks": 1},
            )
            assert status == 503 and server.get()["revision"] == revision
            assert not server.get()["audit"]["healthy"]
            results.append("ledger death fails writes closed")
            server.stop()
            verified = subprocess.run(
                [binaries / "chronicle", "verify", server.data / "events.jsonl"],
                capture_output=True,
                text=True,
                check=True,
            )
            summary = json.loads(verified.stdout)
            assert summary["ok"]
            results.append("final ledger independently reverified after all faults")
        finally:
            server.stop()
    report = {
        "ok": True,
        "checks": results,
        "binary_sha256": identities,
        "final_ledger": summary,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    run(
        pathlib.Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "docs/evidence/integration.json"
    )
