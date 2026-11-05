"use strict";
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const crypto = require("node:crypto");
const assert = require("node:assert/strict");
const { chromium } = require(process.env.X3_PLAYWRIGHT_MODULE || "playwright");
const core = require("./core.js");
(async () => {
  const html = fs.readFileSync(path.join(__dirname, "index.html"));
  const server = http.createServer((request, response) => {
    if (!["/", "/index.html"].includes(request.url)) { response.writeHead(404); response.end(); return; }
    response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    response.end(html);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  let browser;
  const results = [];
  try {
    browser = await chromium.launch({ headless: true });
    for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
      const context = await browser.newContext({ viewport, isMobile: viewport.width < 500, hasTouch: viewport.width < 500, reducedMotion: "reduce", acceptDownloads: true });
      const legacy = core.blank("max-g3-d");
      delete legacy.stats; delete legacy.samples;
      legacy.firmware.vcu = "1.5.4";
      legacy.notes = "Legacy profile fixture";
      await context.addInitScript((value) => {
        if (!localStorage.getItem("x3-fixture-seeded")) {
          localStorage.setItem("x3-workshop:v1:max-g3-d", JSON.stringify(value));
          localStorage.setItem("x3-fixture-seeded", "1");
        }
      }, legacy);
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto("http://127.0.0.1:" + server.address().port + "/");
      await page.getByRole("heading", { name: /X3 Studio/ }).waitFor();
      assert.equal(await page.locator("#firmware-rows tr").count(), 4);
      assert.equal(await page.locator("#model-picker button").count(), 4);
      const blocked = () => page.getByRole("button", { name: "Keine geprüfte Flashfreigabe" }).isDisabled();
      assert.equal(await blocked(), true);
      assert.equal(await page.locator("#notes").inputValue(), "Legacy profile fixture");
      const versions = { vcu: "1.6.4", mcu: "1.6.0", ble: "0.4.5", bms: "4.1.6.8" };
      for (const [component, value] of Object.entries(versions)) await page.locator("#fw-" + component).fill(value);
      const save = () => page.getByRole("button", { name: "Entwurf speichern", exact: true }).click();
      await save();
      assert.match(await page.locator("#assessment").innerText(), /bisherige SHU-Bluetooth-Flashweg/);
      await page.locator("#field-weakening").check();
      await page.waitForFunction(() => !document.getElementById("fw-parameters").disabled);
      await page.locator("#fwCurrentA").fill("1");
      await save();

      await page.getByRole("button", { name: "VCU", exact: true }).click();
      assert.equal(await page.locator("#firmware-rows tr:visible").count(), 1);
      await page.getByRole("button", { name: "Alle", exact: true }).click();
      assert.equal(await page.locator("#firmware-rows tr:visible").count(), 4);
      assert.equal(await page.locator("#value-input-power").innerText(), "—");
      await page.locator("#stat-voltageV").fill("50");
      await page.locator("#stat-batteryCurrentA").fill("20");
      await page.locator("#stat-phaseCurrentA").fill("80");
      await page.getByRole("button", { name: "Stats speichern", exact: true }).click();
      assert.equal(await page.locator("#value-input-power").innerText(), "1.000 W");
      assert.equal(await page.locator("#value-input-peak").innerText(), "—");
      await page.locator("#record-sample").click();
      assert.equal(await page.locator("#value-input-peak").innerText(), "1.000 W");
      await page.locator("#stat-voltageV").fill("40");
      await page.locator("#stat-batteryCurrentA").fill("30");
      await page.locator("#record-sample").click();
      assert.equal(await page.locator("#value-input-peak").innerText(), "1.200 W");
      assert.equal(await page.locator("#value-current-peak").innerText(), "30 A");
      assert.equal(await page.locator("#value-phase-peak").innerText(), "80 A");
      await page.locator("#stat-batteryCurrentA").fill("-5");
      await page.locator("#record-sample").click();
      assert.equal(await page.locator("#value-input-power").innerText(), "-200 W");
      assert.equal(await page.locator("#value-charge-peak").innerText(), "200 W");
      assert.equal(await page.locator("#power-chart circle").count(), 3);

      const waiting = page.waitForEvent("download");
      await page.locator("#export").click();
      const stream = await (await waiting).createReadStream();
      const chunks = [];
      for await (const chunk of stream) chunks.push(chunk);
      const exported = core.parse(Buffer.concat(chunks).toString("utf8"));
      assert.equal(exported.model, "max-g3-d");
      assert.equal(exported.samples.length, 3);
      assert.equal(core.summarize(exported).peakInputW, 1200);
      assert.equal(exported.tuning.fieldWeakeningRequested, true);
      assert.equal(core.assess(exported).canFlash, false);
      await page.getByRole("button", { name: "E3 Pro D", exact: true }).click();
      assert.equal(await page.locator("#fw-vcu").inputValue(), "");
      assert.equal(await page.locator("#stat-voltageV").inputValue(), "");
      assert.equal(await page.locator("#value-input-power").innerText(), "—");
      await page.getByRole("button", { name: "MAX G3 D", exact: true }).click();
      assert.equal(await page.locator("#fw-vcu").inputValue(), "1.6.4");
      assert.equal(await page.locator("#stat-batteryCurrentA").inputValue(), "-5");
      await page.evaluate(() => {
        // Simulate an older immutable page writing its legacy key.
        const old = JSON.parse(localStorage.getItem("x3-workshop:v1:max-g3-d"));
        old.firmware.vcu = "0.0.1";
        localStorage.setItem("x3-workshop:v1:max-g3-d", JSON.stringify(old));
      });
      await page.reload();
      assert.equal(await page.locator("#fw-vcu").inputValue(), "1.6.4");
      const profile = core.blank("f3-pro-d");
      profile.notes = '<img src=x onerror="window.x3Injected=1">';
      const importProfile = (value) => page.locator("#import").setInputFiles({ name: "profile.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(value)) });
      await importProfile(profile);
      await page.waitForFunction(() => document.getElementById("model-name").textContent === "F3 Pro D");
      assert.equal(await page.locator("#notes").inputValue(), profile.notes);
      assert.equal(await page.evaluate(() => window.x3Injected), undefined);
      profile.model = "unsupported";
      await importProfile(profile);
      await page.waitForFunction(() => document.getElementById("status").classList.contains("error"));
      assert.equal(await page.locator("#model-name").innerText(), "F3 Pro D");
      await page.locator("#import").setInputFiles({ name: "huge.json", mimeType: "application/json", buffer: Buffer.alloc(65537, 32) });
      await page.waitForFunction(() => document.getElementById("status").textContent.includes("64 KiB"));
      const payload = Buffer.from("X3 local checksum test\n");
      const hash = crypto.createHash("sha256").update(payload).digest("hex");
      await page.locator("#expected-hash").fill(hash);
      await page.locator("#package").setInputFiles({ name: "test.bin", mimeType: "application/octet-stream", buffer: payload });
      await page.waitForFunction((wanted) => document.getElementById("file-hash").textContent === wanted, hash);
      assert.match(await page.locator("#hash-comparison").innerText(), /stimmen überein/);
      await page.locator("#expected-hash").fill("0".repeat(64));
      assert.match(await page.locator("#hash-comparison").innerText(), /unterscheiden/);
      await page.locator("#package").setInputFiles({ name: "large.bin", mimeType: "application/octet-stream", buffer: Buffer.alloc(16777217) });
      await page.waitForFunction(() => document.getElementById("hash-comparison").textContent.includes("16 MiB"));
      assert.equal(await blocked(), true);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1), false);
      await page.getByRole("button", { name: "MAX G3 D", exact: true }).click();
      page.once("dialog", (dialog) => dialog.accept());
      await page.locator("#reset").click();
      await page.reload();
      assert.equal(await page.locator("#fw-vcu").inputValue(), "");
      assert.equal(await page.locator("#stat-voltageV").inputValue(), "");
      assert.equal(await page.locator("#value-input-peak").innerText(), "—");
      assert.deepEqual(errors, []);
      results.push({ viewport, result: "passed", browser: "Chromium", realIOS: false });
      await context.close();
    }
    console.log(JSON.stringify({ results, hardwareTests: "not run", flashing: "not implemented" }, null, 2));
  } finally {
    if (browser) await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
