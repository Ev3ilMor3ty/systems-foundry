#!/usr/bin/env python3
"""Run the real Auto workflow with an accelerated browser clock, not mock API data."""
import argparse, json, pathlib, tempfile, time
from harness import ROOT, Server, freeze
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="foundry auto workflow ") as directory:
        directory = pathlib.Path(directory)
        binaries = directory / "binaries"
        identity = freeze(ROOT, binaries)
        with Server(
            binaries, directory / "state"
        ) as server, sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=args.chromium, headless=True, args=["--no-sandbox"]
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.clock.install()
            page.goto(server.base, wait_until="domcontentloaded")
            page.wait_for_function(
                "() => document.querySelector('#queued-count').textContent==='12'"
            )
            page.locator("#autoplay").click()
            page.wait_for_function(
                "() => document.querySelector('#active-count').textContent==='6'"
            )
            jumps = 0
            while jumps < 30:
                old = server.get()
                page.clock.fast_forward(3500)
                jumps += 1
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    current = server.get()
                    if current["tick"] > old["tick"]:
                        break
                    time.sleep(0.02)
                else:
                    raise AssertionError("Auto workflow failed to advance")
                page.wait_for_function(
                    "() => !document.querySelector('#step').disabled"
                )
                if all(t["status"] == "done" for t in server.get()["tasks"]):
                    break
            final = server.get()
            assert all(t["status"] == "done" for t in final["tasks"])
            assert all(r["taskId"] is None for r in final["resources"])
            page.wait_for_function(
                "() => document.querySelector('#autoplay').getAttribute('aria-pressed')==='false'"
            )
            report = {
                "ok": True,
                "binary_sha256": identity,
                "completed_requests": len(final["tasks"]),
                "final_tick": final["tick"],
                "browser_clock_jumps": jumps,
                "clock_note": "Browser timers accelerated; real Java/C++/Rust requests and durability remained active. This is a workflow test, not elapsed-time endurance evidence.",
            }
            browser.close()
    (ROOT / "docs/evidence/ui/auto-workflow.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
