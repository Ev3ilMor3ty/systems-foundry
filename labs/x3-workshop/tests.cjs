"use strict";
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
function runCoreTests(core) {
  let assertions = 0;
  const groups = [];
  const ok = (value, label) => { assertions++; if (!value) throw new Error(label); };
  const same = (a, b, label) => ok(JSON.stringify(a) === JSON.stringify(b), label);
  const throws = (fn, label) => { let rejected = false; try { fn(); } catch { rejected = true; } ok(rejected, label); };
  function group(name, fn) { fn(); groups.push(name); }
  group("four model profiles round-trip independently", () => {
    for (const item of core.models) {
      const draft = core.blank(item.id);
      draft.notes = "Prüfung / iPad / Maß";
      same(core.parse(JSON.stringify(draft)), draft, item.id + " round trip");
      ok(!core.assess(draft).canFlash, item.id + " no device writes");
      ok(core.assess(draft).missing.length === 4, "missing data stays missing");
    }
  });
  group("unsupported models never fall back", () => {
    for (const id of ["gt3-pro", "max-g3-e", "", "__proto__"]) throws(() => core.blank(id), "reject " + id);
  });
  group("foreign formats and malformed JSON rejected", () => {
    for (const raw of ["null", "[]", "{}", "{bad", '{"schemaVersion":2}', "0"]) throws(() => core.parse(raw), "reject " + raw);
    const draft = core.blank("max-g3-d");
    draft.kind = "flash-package";
    throws(() => core.validate(draft), "firmware package not a profile");
  });
  group("oversized profiles rejected", () => {
    throws(() => core.parse(" ".repeat(65537)), "64 KiB bound");
  });
  group("firmware labels preserve exact versions", () => {
    const draft = core.blank("max-g3-d");
    for (const value of ["1.6.4", "4.1.6.8", "V0.1.5.F", "1.2.11-Compat"]) {
      draft.firmware.vcu = value;
      same(core.validate(draft).firmware.vcu, value, "preserve version");
    }
    for (const value of ["<img src=x>", "../firm.bin", "undefined", "x".repeat(49)]) {
      draft.firmware.vcu = value;
      throws(() => core.validate(draft), "invalid version label");
    }
  });
  group("known issue stays scoped to exact G3 version", () => {
    const draft = core.blank("max-g3-d");
    draft.firmware.vcu = "1.6.4";
    ok(core.assess(draft).knownBlockedPath, "documented path");
    draft.firmware.vcu = "v1.6.4";
    ok(core.assess(draft).knownBlockedPath, "v prefix");
    for (const value of ["1.6.40", "1.6.5", "1.6.3", ""]) {
      draft.firmware.vcu = value;
      ok(!core.assess(draft).knownBlockedPath, "do not extrapolate " + value);
    }
    for (const id of ["f3-pro-d", "zt3-pro-d", "e3-pro-d"]) {
      const other = core.blank(id);
      other.firmware.vcu = "1.6.4";
      ok(!core.assess(other).knownBlockedPath, "do not inherit G3 evidence");
    }
  });
  group("complete imported claims cannot enable flashing", () => {
    for (const item of core.models) {
      const draft = core.blank(item.id);
      for (const component of core.components) draft.firmware[component.id] = "99.99";
      draft.hardware = { motor: "US", controller: "claimed supported", battery: "claimed supported" };
      draft.canFlash = true;
      draft.deviceTested = true;
      draft.tuning.fieldWeakeningRequested = true;
      const clean = core.parse(JSON.stringify(draft));
      ok(!Object.hasOwn(clean, "canFlash"), "drop imported trust flag");
      const assessment = core.assess(clean);
      ok(!assessment.canFlash && !assessment.deviceTested && !assessment.firmwareGenerated, "no fabricated support");
      ok(assessment.missing.length === 0, "complete does not mean verified");
    }
  });
  group("non-finite negative and coerced values rejected", () => {
    for (const field of ["fwStartKmh", "fwCurrentA", "ecoKmh", "driveKmh", "sportKmh"]) {
      for (const invalid of [-1, Infinity, NaN, "12", true, {}, 1001]) {
        const draft = core.blank("e3-pro-d");
        draft.tuning[field] = invalid;
        throws(() => core.validate(draft), field + " rejects invalid number");
      }
    }
  });
  group("unset values and zero remain distinct", () => {
    const draft = core.blank("max-g3-d");
    draft.tuning.ecoKmh = 0;
    draft.tuning.driveKmh = 12.5;
    same(core.validate(draft).tuning.ecoKmh, 0, "zero preserved");
    same(core.validate(draft).tuning.driveKmh, 12.5, "decimal preserved");
    same(core.validate(draft).tuning.sportKmh, null, "unset preserved");
  });
  group("prototype keys never cross the allowed schema", () => {
    const draft = core.blank("max-g3-d");
    const raw = JSON.stringify(draft).replace('"schemaVersion":1', '"schemaVersion":1,"__proto__":{"canFlash":true},"constructor":{"prototype":{"canFlash":true}}');
    const clean = core.parse(raw);
    ok(!Object.hasOwn(clean, "__proto__"), "drop prototype key");
    ok(!Object.hasOwn(clean, "constructor"), "drop constructor key");
    ok(!core.assess(clean).canFlash, "still blocked");
  });
  group("text bounds and missing sections rejected", () => {
    const draft = core.blank("max-g3-d");
    draft.notes = "x".repeat(2001);
    throws(() => core.validate(draft), "notes bound");
    draft.notes = "bad\u0000text";
    throws(() => core.validate(draft), "control character");
    draft.notes = "";
    draft.hardware.motor = "x".repeat(121);
    throws(() => core.validate(draft), "hardware bound");
    draft.hardware.motor = "";
    draft.tuning.regen = "disable-all-brakes";
    throws(() => core.validate(draft), "unknown enum");
    draft.tuning.regen = "stock";
    delete draft.firmware;
    throws(() => core.validate(draft), "missing component section");
  });

  group("legacy profiles migrate with no fabricated telemetry", () => {
    const old = core.blank("max-g3-d");
    delete old.stats; delete old.samples;
    const migrated = core.parse(JSON.stringify(old));
    same(migrated.samples, [], "legacy history is empty");
    ok(Object.values(migrated.stats).every((value) => value === null), "legacy stats unknown");
    ok(!core.summarize(migrated).isLive, "no live claim");
  });
  group("DC power does not use phase current or motor nameplate", () => {
    const p = core.blank("max-g3-d");
    p.stats.voltageV = 50; p.stats.batteryCurrentA = 10; p.stats.phaseCurrentA = 200;
    p.stats.motorDeclaredPeakW = 9999;
    const summary = core.summarize(core.appendSample(p, "2026-11-05T19:00:00.000Z"));
    same(summary.inputPowerW, 500, "battery U times DC I");
    same(summary.peakInputW, 500, "electrical peak independent of nameplate");
    same(summary.peakPhaseA, 200, "phase reported separately");
    same(summary.motorOutputW, null, "no inferred mechanical watts");
  });
  group("peak watts use simultaneous samples not independent maxima", () => {
    let p = core.blank("max-g3-d");
    p.stats.voltageV = 60; p.stats.batteryCurrentA = 10;
    p = core.appendSample(p, "2026-11-05T19:00:00.000Z");
    p.stats.voltageV = 40; p.stats.batteryCurrentA = 20;
    p = core.appendSample(p, "2026-11-05T19:00:01.000Z");
    const summary = core.summarize(p);
    same(summary.peakInputW, 800, "not 60 times 20");
    same(summary.peakBatteryA, 20, "DC peak");
    same(summary.sampleCount, 2, "two logged samples");
    same(summary.powerSeries.map((point) => point.powerW), [600, 800], "series is unmodified");
  });
  group("signed charging and regen stay separate from discharge", () => {
    let p = core.blank("f3-pro-d");
    p.stats.voltageV = 50; p.stats.batteryCurrentA = -5; p.stats.phaseCurrentA = -80;
    p = core.appendSample(p, "2026-11-05T19:00:00.000Z");
    const summary = core.summarize(p);
    same(summary.inputPowerW, -250, "signed power");
    same(summary.peakChargeW, 250, "charge magnitude");
    same(summary.peakInputW, null, "no recorded discharge peak");
    same(summary.peakBatteryA, null, "no recorded discharge amps");
    same(summary.peakPhaseA, 80, "absolute recorded phase peak");
  });
  group("unknown zero and nameplate energy remain distinct", () => {
    const p = core.blank("e3-pro-d");
    same(core.summarize(p).inputPowerW, null, "unknown power");
    p.stats.voltageV = 50;
    same(core.summarize(p).inputPowerW, null, "voltage alone is insufficient");
    p.stats.batteryCurrentA = 0;
    same(core.summarize(p).inputPowerW, 0, "zero current is valid");
    p.stats.batteryNominalV = 46.8; p.stats.batteryCapacityAh = 12.75;
    p.stats.batteryDeclaredWh = 597;
    ok(Math.abs(core.summarize(p).nominalEnergyWh - 596.7) < 0.00001, "nominal U times Ah");
    same(p.stats.batteryDeclaredWh, 597, "rounded nameplate preserved separately");
    same(p.stats.socPct, null, "SOC not guessed from voltage");
    same(core.summarize(p).peakInputW, null, "unlogged snapshot not a historical peak");
  });
  group("stats bounds and sample provenance validated", () => {
    for (const field of core.statsFields) {
      for (const invalid of [Infinity, NaN, "10", field.min - 1, field.max + 1]) {
        const p = core.blank("zt3-pro-d");
        p.stats[field.id] = invalid;
        throws(() => core.validate(p), "reject " + field.id);
      }
    }
    const p = core.blank("max-g3-d");
    throws(() => core.appendSample(p, "2026-11-05T19:00:00.000Z"), "missing simultaneous data");
    p.stats.voltageV = 50; p.stats.batteryCurrentA = 1;
    throws(() => core.appendSample(p, "not-a-date"), "invalid timestamp");
    throws(() => core.appendSample(p, "2026-02-29T19:00:00.000Z"), "invalid calendar date");
    const logged = core.appendSample(p, "2026-11-05T19:00:00.000Z");
    logged.samples[0].source = "live";
    throws(() => core.validate(logged), "reject fabricated live source");
  });
  group("sample cap does not silently discard peaks", () => {
    let p = core.blank("max-g3-d");
    p.stats.voltageV = 50; p.stats.batteryCurrentA = 1;
    p.notes = "x".repeat(2000);
    for (let i = 0; i < 128; i++) p = core.appendSample(p, new Date(1793905200000 + i * 1000).toISOString());
    same(core.summarize(p).sampleCount, 128, "full history preserved");
    throws(() => core.appendSample(p, "2026-11-05T19:10:00.000Z"), "do not overwrite old points");
    ok(JSON.stringify(p).length < 65536, "full export fits import limit");
    same(core.parse(JSON.stringify(p)).samples.length, 128, "full history round trip");
  });

  return { groups: groups.length, assertions, names: groups };
}

function loadCore(source) {
  const context = vm.createContext({});
  vm.runInContext(source, context, { timeout: 3000 });
  return context.X3Core;
}
const standalone = fs.readFileSync(path.join(__dirname, "core.js"), "utf8");
const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const embedded = html.match(/<script id="x3-core">\n([\s\S]*?)\n<\/script>/);
if (!embedded) throw new Error("Embedded core missing.");
const app = html.match(/<script id="x3-app">\n([\s\S]*?)\n<\/script>/);
if (!app) throw new Error("Embedded UI missing.");
new vm.Script(app[1]);
if (embedded[1] !== standalone.trimEnd()) throw new Error("Embedded core differs from tested source.");
if (app[1] !== fs.readFileSync(path.join(__dirname, "app.js"), "utf8").trimEnd()) throw new Error("Embedded UI differs from source.");
const first = runCoreTests(loadCore(standalone));
const second = runCoreTests(loadCore(embedded[1]));
console.log(JSON.stringify({ standalone: first, embedded: second, bundleConsistency: "passed", uiSyntax: "passed" }, null, 2));
