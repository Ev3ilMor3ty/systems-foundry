# X3 Workshop

German-language website for recording firmware versions, drafting profiles and locally hashing files for **MAX G3 D, F3 Pro D, ZT3 Pro D and E3 Pro D**.

**This is a functioning profile/inventory tool, not a tuning firmware release.** It does not connect to a scooter, build firmware, flash, restore firmware or apply field weakening. There have been no physical scooter/controller tests.

## Open

[Browser preview via raw.githack.com](https://raw.githack.com/Ev3ilMor3ty/systems-foundry/main/labs/x3-workshop/index.html)

This is a third-party HTML preview, not a GitHub Pages deployment. It may cache changes. GitHub Pages was not enabled when this project was added; no permanent Pages URL is claimed.

Alternatively, download index.html and open it in a desktop browser. The page is self-contained: no runtime dependencies, CDN scripts, analytics or application network requests. iPhone layouts are designed responsively, but Chromium mobile emulation is not a physical Safari/iOS test.

## Features and limits

- Four separately stored local model drafts.
- Manual VCU, MCU/ESC/DRV, BLE/dashboard and BMS versions, plus hardware identifiers.
- Field-weakening request and optional parameters; Eco/Drive/Sport/regen wishes.
- Bounded, schema-validated JSON import/export. Imported trust flags cannot enable flashing.
- Local SHA-256 with optional reference comparison; files up to 16 MiB. A matching hash does not establish origin or compatibility.
- Keyboard labels, reduced-motion support, text-only rendering and export fallback when browser storage is unavailable.

Numeric bounds protect the file format; they are **not** approved electrical operating limits. Blank parameters remain unset. No tuning values or 70+ km/h setup are recommended or verified.

## Firmware evidence

Snapshot: **2026-11-05**. Latest and previous original component versions remain **unknown** for all four D models.

A community firsthand MAX G3 D report dated 2026-10-13 records VCU 1.6.4, MCU 1.6.0, BLE 0.4.5 and BMS 4.1.6.8. Hardware revision and original release dates are unknown. This example is not proof of the latest release or another model's compatibility:

- [Community report / ScooterHacking issue 279](https://github.com/scooterhacking/scooterhacking-issues-public/issues/279)
- [Official Segway product security](https://eu-en.segway.com/regulation/report-a-vulnerability.html)
- [ScooterHacking announcements — community](https://t.me/s/scooterhackingupdates)
- [Incomplete community firmware mirror](https://firmware.scooterhacking.org/)

The documented restriction concerns a particular SHU Bluetooth path for G3 VCU 1.6.4, not every possible tool or future method.

A separate ChatGPT firmware-notification task was created in the setup conversation. **This website is not connected to it, does not update automatically and does not enable visitor notifications.** No firmware binaries are distributed.


## X3 Studio statistics update

The compact, numbered model/component/configuration layout is inspired by the public x3fw builder structure. The interface, CSS and source remain independently written; no Kasai assets or firmware are copied.

Statistics are **manual entries or calculations, never live scooter readings**:

- Motor rated/nameplate peak watts and mechanical RPM.
- Battery voltage, DC amps, separate phase amps, SOC and temperatures.
- Nameplate Wh versus calculated nominal Wh (nominal volts × Ah).
- Signed battery input watts (measured-point volts × DC amps), not mechanical motor output.
- Up to 128 explicitly manual time-stamped points, a power plot, discharge amp/watt peaks, phase magnitude peak and charging/regen watt peak.
- Watt peaks use the product at each individual point, not max(voltage) × max(current). SOC and mechanical motor power are not inferred.
- Stats and history are stored separately per model and round-trip through the existing JSON profile. Legacy profiles migrate to unknown stats and an empty history.
- The sample cap rejects additional entries rather than silently discarding old peaks. Export before explicitly resetting a series.

Added pure-logic coverage: **18 groups / 195 assertions passed** in the available JavaScript isolate, including the existing profile tests. Remote Node and desktop/mobile Chromium results must be checked in the corresponding Actions run. No real iPhone, scooter or dynamometer result is implied.

## Tests

Node 22, no dependencies:

~~~sh
node labs/x3-workshop/tests.cjs
~~~

The initial core suite was run in the available JavaScript isolate: **11 groups, 99 assertions passed**. Tests cover round trips for all models, malformed/oversized imports, version identity, exact scope of evidence, forged trust flags, invalid numbers, unset versus zero, prototype keys and text bounds.

The Node runner executes the suite against both standalone and embedded core and checks that index.html contains the exact tested sources. The [path-scoped CI workflow](../../.github/workflows/x3-workshop.yml) additionally runs Playwright 1.56.1/Chromium at desktop 1280×900 and mobile 390×844. It tests storage, model isolation, JSON download/import, inert HTML-like notes, hashes, size bounds, disabled flashing and overflow. A workflow definition is not a passing run; consult its actual result.

For local browser tests, install Playwright separately and select its module:

~~~sh
npm install --prefix /tmp/x3-qa playwright@1.56.1
node /tmp/x3-qa/node_modules/playwright/cli.js install chromium
X3_PLAYWRIGHT_MODULE=/tmp/x3-qa/node_modules/playwright node labs/x3-workshop/browser-tests.cjs
~~~

No hardware, BLE authentication, flash-abort/recovery, braking, thermal or field-weakening tests have run. See TEST_MATRIX.md. Software tests do not prove device compatibility.

## Development and privacy

index.html embeds core.js and app.js for one-file use. Update the matching script block whenever either source changes; the tests reject stale copies.

Drafts stay in this browser's localStorage; chosen files are read locally for hashing and never uploaded. Exports include entered hardware identifiers and notes. Storage may be cleared, so retain JSON exports if needed.

Independently written source under the repository's MIT license. No N-SAK/Kasai private code, firmware binaries, logos or UI assets are copied. External projects are linked as evidence only.
