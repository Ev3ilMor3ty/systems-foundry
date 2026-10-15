# Control Room

A framework-free HTML/CSS/JavaScript dashboard served by Control API. It shows fictional routes and carrier movement, a filterable request queue, exact-dispatch controls, manual/automatic simulation steps, the current ledger head and a short event timeline.

Runtime has no Node, CDN, analytics or external font requirement. It requires the local Java backend and its C++/Rust workers; opening `index.html` directly does not start them.

```bash
# From the repository root:
./scripts/run.sh
# Open http://127.0.0.1:8090
```

Node is used only for development checks:

```bash
cd control-room
npm ci --ignore-scripts
npm test
npm run format:check
```

`ui-model.mjs` contains independently tested metrics, filtering, route interpolation, eligibility and stale-snapshot handling. `scripts/ui_test.py` drives the real backend in Chromium, checks proof downloads and plain-text rendering, tests widths from 320 to 1440 pixels, and runs axe WCAG checks. Automated checks cover tested states only; they do not establish full accessibility conformance.

All names, coordinates, workloads and travel costs belong to a fictional simulation. The map is illustrative, not geographic navigation. Auto run advances simulated ticks while the page remains open; it does not start an external scheduler.
