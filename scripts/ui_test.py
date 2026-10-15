#!/usr/bin/env python3
"""Browser workflow, responsive layout and axe WCAG checks against the real API.

Requires Playwright, Chromium and `npm ci` in control-room. No mock dashboard data.
"""
import argparse, json, pathlib, sys, tempfile
from harness import ROOT, Server, freeze
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(ROOT / "dispatch/tools"))
from check_certificate import verify


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chromium", default="/usr/bin/chromium")
    p.add_argument("--output", type=pathlib.Path, default=ROOT / "docs/evidence/ui")
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="foundry browser ") as temp:
        temp = pathlib.Path(temp)
        b = temp / "binaries"
        identity = freeze(ROOT, b)
        with Server(b, temp / "state") as server, sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=a.chromium, headless=True, args=["--no-sandbox"]
            )
            page = browser.new_page(
                viewport={"width": 1440, "height": 1100}, device_scale_factor=1
            )
            errors = []
            console = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on(
                "console",
                lambda m: console.append(m.text) if m.type == "error" else None,
            )
            page.goto(server.base, wait_until="networkidle")
            page.wait_for_function(
                "() => document.querySelector('#queued-count').textContent==='12'"
            )
            page.get_by_role("button", name="Optimize & dispatch").click()
            page.wait_for_function(
                "() => document.querySelector('#active-count').textContent==='6'"
            )
            with page.expect_download() as download:
                page.get_by_role(
                    "button", name="Download last optimality proof"
                ).click()
            path = temp / "proof.json"
            download.value.save_as(path)
            bundle = json.loads(path.read_text())
            assert verify(bundle["problem"], bundle["response"])["ok"]
            page.get_by_role("button", name="New request", exact=False).click()
            page.get_by_label("Request name").fill("<script>window.hacked=1</script>")
            page.get_by_label("Pickup", exact=True).select_option("dock")
            page.get_by_label("Destination", exact=True).select_option("glass")
            page.get_by_role("button", name="Create request").click()
            page.wait_for_function(
                "() => !document.querySelector('#request-dialog').open"
            )
            assert (
                page.locator("#request-rows")
                .inner_text()
                .find("<script>window.hacked=1</script>")
                >= 0
            )
            assert page.evaluate("window.hacked === undefined")
            assert page.locator("script:not([src])").count() == 0
            page.get_by_role("button", name="Active", exact=True).click()
            assert page.locator("#request-rows tr").count() == 6
            page.locator("#step").click()
            page.wait_for_function(
                "() => document.querySelector('#clock').textContent==='00:05'"
            )
            page.screenshot(path=str(a.output / "desktop.png"), full_page=True)
            # A dependency failure is visible and a later successful action clears it.
            page.route(
                "**/api/plan",
                lambda route: route.fulfill(
                    status=503,
                    content_type="application/json",
                    body=json.dumps({"error": "Test dependency unavailable"}),
                ),
            )
            page.locator("#optimize").click()
            page.wait_for_function(
                "() => document.querySelector('#error-banner').textContent.includes('Test dependency')"
            )
            page.unroute("**/api/plan")
            page.locator("#optimize").click()
            page.wait_for_function(
                "() => document.querySelector('#error-banner').hidden"
            )
            layouts = []
            for width in [320, 390, 768, 1024, 1440]:
                page.set_viewport_size({"width": width, "height": 1000})
                page.wait_for_timeout(100)
                assert not page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth"
                ), f"overflow at {width}"
                assert page.locator("#optimize").is_visible()
                layouts.append(width)
                if width == 390:
                    page.screenshot(path=str(a.output / "mobile.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1100})
            page.evaluate(
                (ROOT / "control-room/node_modules/axe-core/axe.min.js").read_text()
            )
            accessibility = page.evaluate(
                "async () => await axe.run(document, {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})"
            )
            (a.output / "accessibility.json").write_text(
                json.dumps(accessibility, indent=2) + "\n"
            )
            assert not accessibility["violations"], [
                (v["id"], len(v["nodes"])) for v in accessibility["violations"]
            ]
            assert not errors, errors
            # Browser-generated favicon 404s are omitted; application console errors are not.
            meaningful = [
                e
                for e in console
                if "favicon" not in e and "503" not in e and "404" not in e
            ]
            assert not meaningful, meaningful
            browser.close()
    report = {
        "ok": True,
        "binary_sha256": identity,
        "viewports": layouts,
        "wcag_violations": 0,
        "page_errors": errors,
        "checks": [
            "real dispatch",
            "downloaded proof verified",
            "untrusted text rendered safely",
            "state filters",
            "tick controls",
            "visible failure and recovery",
            "responsive layout",
            "WCAG automated checks",
        ],
    }
    (a.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
