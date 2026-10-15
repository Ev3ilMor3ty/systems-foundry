#!/usr/bin/env python3
"""Verify portable contents and launch them from a fresh path containing spaces."""
import argparse, json, hashlib, os, pathlib, selectors, shutil, subprocess, sys, tempfile, time, urllib.request
from harness import ROOT  # Enables reaping of this test's orphaned descendants.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=pathlib.Path, required=True)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=ROOT / "docs/evidence/linux-package-smoke.json",
    )
    args = parser.parse_args()
    count = 0
    for line in (args.package / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ", 1)
        path = args.package / name
        if not path.resolve().is_relative_to(args.package.resolve()):
            raise ValueError("Unsafe checksum path")
        assert (
            path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest
        ), name
        count += 1
    with tempfile.TemporaryDirectory(
        prefix="foundry extracted package with spaces "
    ) as directory:
        destination = pathlib.Path(directory) / "portable preview"
        shutil.copytree(args.package, destination)
        with open(pathlib.Path(directory) / "startup.log", "wb") as log:
            process = subprocess.Popen(
                ["bash", str(destination / "start.sh"), "--port", "0"],
                cwd=directory,
                stdout=subprocess.PIPE,
                stderr=log,
                text=True,
            )
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            children = []
            try:
                assert selector.select(12), "package did not announce its URL"
                line = process.stdout.readline().strip()
                assert "http://127.0.0.1:" in line, line
                base = line.split()[-1]

                def get(path):
                    with urllib.request.urlopen(base + path, timeout=8) as response:
                        return response.status, response.read()

                status, body = get("/")
                assert status == 200 and b"Network control" in body
                state = json.loads(get("/api/state")[1])
                assert len(state["tasks"]) == 12
                request = urllib.request.Request(
                    base + "/api/plan",
                    data=json.dumps(
                        {
                            "commandId": "portable-smoke",
                            "expectedRevision": state["revision"],
                        }
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=8) as response:
                    state = json.load(response)["state"]
                assert sum(t["status"] == "active" for t in state["tasks"]) == 6
                sys.path.insert(0, str(destination / "source/dispatch/tools"))
                from check_certificate import verify

                assert verify(state["latestPlan"]["problem"], state["latestPlan"])["ok"]
                assert (destination / "data/events.jsonl").is_file()
                children = [
                    int(x)
                    for x in subprocess.run(
                        ["ps", "--ppid", str(process.pid), "-o", "pid="],
                        capture_output=True,
                        text=True,
                    ).stdout.split()
                ]
                report = {
                    "ok": True,
                    "contents_checked": count,
                    "source_commit": json.loads(
                        (destination / "BUILD-INFO.json").read_text()
                    )["source_commit"],
                    "binary_sha256": json.loads(
                        (destination / "BUILD-INFO.json").read_text()
                    )["binary_sha256"],
                    "checks": [
                        "all content checksums",
                        "path containing spaces",
                        "Java runtime launch without build tools",
                        "local dashboard served",
                        "real optimizer dispatch",
                        "independent optimality proof",
                        "local durable data created",
                    ],
                }
            finally:
                selector.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                process.stdout.close()
                for pid in children:
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        try:
                            done, _ = os.waitpid(pid, os.WNOHANG)
                            if done:
                                break
                        except ChildProcessError:
                            break
                        time.sleep(0.02)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
