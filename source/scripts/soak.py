#!/usr/bin/env python3
"""Bounded, checkpointed real-API endurance run with restarts and fault injection.

Inputs are copied into an isolated frozen directory. No assistant continuations,
remote deployment, external messages or automatic Git pushes are created.
"""
import argparse, concurrent.futures, fcntl, hashlib, json, os, pathlib, signal, subprocess, sys, time, urllib.request
from harness import ROOT, Server, freeze


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    os.replace(temporary, path)


def rss(pid):
    try:
        for line in pathlib.Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except FileNotFoundError:
        pass
    return None


def main():
    if not __debug__:
        raise RuntimeError("Endurance validation requires assertions; run without -O")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=16200)
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--scheduler-parallelism", type=int, choices=range(1, 9))
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--binaries", type=pathlib.Path)
    parser.add_argument("--web-root", type=pathlib.Path, default=ROOT)
    args = parser.parse_args()
    if not 60 <= args.seconds <= 86400 or not 0.1 <= args.interval <= 60:
        parser.error("duration 60..86400 seconds; interval .1..60 seconds")
    args.output.mkdir(parents=True, exist_ok=True)
    lock = open(args.output / "run.lock", "a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (args.output / "checkpoint.json").exists():
        raise SystemExit("Existing run found; use a new output directory")
    binaries = args.binaries or args.output / "binaries"
    identity = (
        json.loads((binaries / "identity.json").read_text())
        if args.binaries
        else freeze(ROOT, binaries)
    )
    for name, digest in identity.items():
        if hashlib.sha256((binaries / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Frozen binary changed: " + name)
    sys.path.insert(0, str(args.web_root / "dispatch/tools"))
    from check_certificate import verify

    checkpoint = {
        "phase": "preparing",
        "complete": False,
        "requested_seconds": args.seconds,
        "interval_seconds": args.interval,
        "started_epoch": time.time(),
        "operations": 0,
        "restarts": 0,
        "crash_retries": 0,
        "proofs_checked": 0,
        "binary_sha256": identity,
        "scheduler_parallelism": args.scheduler_parallelism,
        "high_water_rss_kib": {},
    }
    save(args.output / "checkpoint.json", checkpoint)
    server = Server(
        binaries,
        args.output / "state",
        args.web_root,
        java_options=["-Xms32m", "-Xmx256m"]
        + (
            [
                f"-Djdk.virtualThreadScheduler.parallelism={args.scheduler_parallelism}",
                f"-Djdk.virtualThreadScheduler.maxPoolSize={args.scheduler_parallelism}",
            ]
            if args.scheduler_parallelism
            else []
        ),
    )
    start = time.monotonic()
    previous = None

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        server.start()
        checkpoint["phase"] = "running"
        checkpoint["runner_pid"] = os.getpid()
        print(
            json.dumps(
                {
                    "phase": "running",
                    "pid": os.getpid(),
                    "api_pid": server.process.pid,
                    "output": str(args.output),
                }
            ),
            flush=True,
        )
        with open(args.output / "metrics.jsonl", "w", buffering=1) as metrics:
            while time.monotonic() - start < args.seconds:
                i = checkpoint["operations"]
                state = server.get()
                tasks = state["tasks"]
                idle = any(
                    not r["taskId"]
                    and any(
                        t["status"] == "queued" and t["skill"] in r["skills"]
                        for t in tasks
                    )
                    for r in state["resources"]
                )
                queued = any(t["status"] == "queued" for t in tasks)
                operation = (
                    "reset"
                    if all(t["status"] == "done" for t in tasks)
                    else "plan" if idle and queued else "advance"
                )
                extra = {"ticks": 5} if operation == "advance" else {}
                request = {
                    "commandId": f"endurance:{i}",
                    "expectedRevision": state["revision"],
                    **extra,
                }
                tick = time.monotonic()
                if i > 0 and i % 480 == 0:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        pending = pool.submit(server.post, operation, request)
                        time.sleep([0, 0.001, 0.006, 0.02][(i // 480) % 4])
                        server.stop(crash=True)
                        try:
                            pending.result(timeout=10)
                        except Exception:
                            pass
                    server.start()
                    checkpoint["restarts"] += 1
                    checkpoint["crash_retries"] += 1
                status, response = server.post(operation, request)
                assert status == 200, (status, response)
                current = response["state"]
                assert current["revision"] == state["revision"] + 1
                if operation == "plan":
                    plan = current["latestPlan"]
                    verify(plan["problem"], plan)
                    checkpoint["proofs_checked"] += 1
                replay_status, replayed = server.post(operation, request)
                assert (
                    replay_status == 200
                    and replayed["replayed"]
                    and replayed["state"]["revision"] == current["revision"]
                ), {
                    "phase": "idempotent-retry",
                    "status": replay_status,
                    "response": replayed,
                    "expected_revision": current["revision"],
                }
                checkpoint["operations"] += 1
                if i % 40 == 0:
                    code, _ = server.post(
                        "advance",
                        {
                            "commandId": f"invalid:{i}",
                            "expectedRevision": current["revision"],
                            "ticks": 1.5,
                        },
                    )
                    assert code == 400
                    code, _ = server.post(
                        "advance",
                        {
                            "commandId": f"stale:{i}",
                            "expectedRevision": current["revision"] - 1,
                            "ticks": 1,
                        },
                    )
                    assert code == 409
                    assert server.get()["revision"] == current["revision"]
                if i > 0 and i % 120 == 0:

                    def read_snapshot(_):
                        with urllib.request.urlopen(
                            server.base + "/api/events", timeout=8
                        ) as stream:
                            assert stream.readline().startswith(b"id: ")
                            assert stream.readline().startswith(b"event: snapshot")
                            assert stream.readline().startswith(b"data: ")

                    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                        list(pool.map(read_snapshot, range(6)))
                if i > 0 and i % 240 == 0:
                    before = server.get()
                    server.stop()
                    result = subprocess.run(
                        [
                            binaries / "chronicle",
                            "verify",
                            server.data / "events.jsonl",
                            before["audit"]["head"],
                        ],
                        text=True,
                        capture_output=True,
                        check=True,
                        timeout=20,
                    )
                    assert json.loads(result.stdout)["ok"]
                    server.start()
                    assert server.get() == before
                    checkpoint["restarts"] += 1
                processes = {"api": server.process.pid, **server.children()}
                memory = {name: rss(pid) for name, pid in processes.items()}
                for name, value in memory.items():
                    if value is not None:
                        checkpoint["high_water_rss_kib"][name] = max(
                            checkpoint["high_water_rss_kib"].get(name, 0), value
                        )
                record = {
                    "elapsed_seconds": round(time.monotonic() - start, 3),
                    "operation": operation,
                    "latency_ms": round((time.monotonic() - tick) * 1000, 3),
                    "revision": current["revision"],
                    "ledger_records": current["audit"]["records"],
                    "ledger_bytes": (server.data / "events.jsonl").stat().st_size,
                    "rss_kib": memory,
                }
                metrics.write(json.dumps(record) + "\n")
                checkpoint.update(
                    phase="running",
                    elapsed_seconds=record["elapsed_seconds"],
                    last_operation=record,
                    api_pid=server.process.pid,
                    last_head=current["audit"]["head"],
                )
                save(args.output / "checkpoint.json", checkpoint)
                # Cadence models a modest interactive workload; the long run
                # targets cumulative resource/recovery behavior, not peak QPS.
                time.sleep(max(0, args.interval - (time.monotonic() - tick)))
        final = server.get()
        server.stop()
        result = subprocess.run(
            [
                binaries / "chronicle",
                "verify",
                server.data / "events.jsonl",
                final["audit"]["head"],
            ],
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        checkpoint.update(
            phase="completed",
            complete=True,
            elapsed_seconds=round(time.monotonic() - start, 3),
            finished_epoch=time.time(),
            final_ledger=json.loads(result.stdout),
        )
    except BaseException as error:
        checkpoint.update(
            phase="incomplete",
            complete=False,
            error=f"{type(error).__name__}: {error}",
            elapsed_seconds=round(time.monotonic() - start, 3),
        )
        raise
    finally:
        try:
            server.stop()
        finally:
            save(args.output / "checkpoint.json", checkpoint)
            lock.close()
    print(
        json.dumps(
            {
                "phase": checkpoint["phase"],
                "operations": checkpoint["operations"],
                "proofs": checkpoint["proofs_checked"],
                "restarts": checkpoint["restarts"],
            }
        )
    )


if __name__ == "__main__":
    main()
