/* X3 Workshop — MIT. Profile planning only; no device writes. */
var X3Core = (() => {
  "use strict";
  const models = Object.freeze([
    { id: "max-g3-d", name: "MAX G3 D", family: "G3" },
    { id: "f3-pro-d", name: "F3 Pro D", family: "F3" },
    { id: "zt3-pro-d", name: "ZT3 Pro D", family: "ZT3" },
    { id: "e3-pro-d", name: "E3 Pro D", family: "E3" },
  ]);
  const components = Object.freeze([
    { id: "vcu", name: "VCU", detail: "Fahrzeugsteuerung" },
    { id: "mcu", name: "MCU / ESC / DRV", detail: "Motorsteuerung" },
    { id: "ble", name: "BLE / Dashboard", detail: "Bluetooth und Anzeige" },
    { id: "bms", name: "BMS", detail: "Akkusteuerung" },
  ]);
  const issue = "https://github.com/scooterhacking/scooterhacking-issues-public/issues/279";
  const observedG3 = Object.freeze({
    vcu: "1.6.4", mcu: "1.6.0", ble: "0.4.5", bms: "4.1.6.8",
    date: "2026-10-13", source: issue,
  });
  function model(id) {
    const found = models.find((item) => item.id === id);
    if (!found) throw new Error("Unbekanntes Modell. Es wird kein Ersatzmodell verwendet.");
    return found;
  }
  function text(value, max, label) {
    if (typeof value !== "string" || value.length > max || /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value))
      throw new Error(label + ": ungültiger Text oder zu lang.");
    return value.trim();
  }
  function version(value) {
    const result = text(value, 48, "Firmware-Version");
    if (result && (!/^[A-Za-z0-9][A-Za-z0-9._+-]*$/.test(result) || !/\d/.test(result)))
      throw new Error("Versionskennung ungültig. Beispiel: 1.6.4. Unbekannte Versionen leer lassen.");
    return result;
  }
  function number(value, label) {
    if (value === null || value === undefined || value === "") return null;
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1000)
      throw new Error(label + ": nur endliche Zahlen von 0 bis 1000 oder leer.");
    return value;
  }
  function object(value, label) {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(label + " fehlt.");
    return value;
  }
  function blank(id) {
    model(id);
    return {
      schemaVersion: 1, kind: "x3-workshop-profile", model: id,
      firmware: { vcu: "", mcu: "", ble: "", bms: "" },
      hardware: { motor: "", controller: "", battery: "" },
      tuning: { fieldWeakeningRequested: false, fwStartKmh: null, fwCurrentA: null,
        ecoKmh: null, driveKmh: null, sportKmh: null, regen: "stock" },
      notes: "",
    };
  }
  function validate(input) {
    object(input, "Profil");
    if (input.schemaVersion !== 1 || input.kind !== "x3-workshop-profile")
      throw new Error("Keine X3-Workshop-Profildatei im Format 1. Firmwaredateien werden nicht importiert.");
    const clean = blank(input.model);
    const fw = object(input.firmware, "Firmwarestände");
    const hw = object(input.hardware, "Hardware");
    const tuning = object(input.tuning, "Profilparameter");
    components.forEach(({ id }) => { clean.firmware[id] = version(fw[id]); });
    ["motor", "controller", "battery"].forEach((key) => {
      clean.hardware[key] = text(hw[key], 120, "Hardware");
    });
    if (typeof tuning.fieldWeakeningRequested !== "boolean") throw new Error("Field-Weakening-Wunsch ungültig.");
    clean.tuning.fieldWeakeningRequested = tuning.fieldWeakeningRequested;
    ["fwStartKmh", "fwCurrentA", "ecoKmh", "driveKmh", "sportKmh"].forEach((key) => {
      clean.tuning[key] = number(tuning[key], key);
    });
    if (!["stock", "off", "weak", "standard"].includes(tuning.regen))
      throw new Error("Rekuperations-Auswahl ungültig.");
    clean.tuning.regen = tuning.regen;
    clean.notes = text(input.notes, 2000, "Notizen");
    return clean;
  }
  function parse(source) {
    if (typeof source !== "string" || source.length > 65536) throw new Error("Profil ist größer als 64 KiB.");
    let data;
    try { data = JSON.parse(source); } catch { throw new Error("Die Datei enthält kein gültiges JSON."); }
    return validate(data);
  }
  function assess(input) {
    const draft = validate(input);
    const missing = components.filter(({ id }) => !draft.firmware[id]).map(({ name }) => name);
    const knownBlockedPath = draft.model === "max-g3-d" && draft.firmware.vcu.replace(/^v/i, "") === "1.6.4";
    return {
      canFlash: false, deviceTested: false, firmwareGenerated: false,
      missing, knownBlockedPath,
      title: "Flashen nicht verfügbar",
      detail: knownBlockedPath
        ? "Für G3 VCU 1.6.4 ist der bisherige SHU-Bluetooth-Flashweg laut Community-Maintainer geschlossen. Das ist keine Aussage über andere Werkzeuge oder spätere Verfahren."
        : "Für diese exakte Kombination liegt hier kein getesteter Flashadapter vor. Vollständige Eingaben sind kein Kompatibilitätsnachweis.",
      source: knownBlockedPath ? issue : null,
    };
  }
  return Object.freeze({ models, components, model, blank, validate, parse, assess, observedG3 });
})();
if (typeof module !== "undefined" && module.exports) module.exports = X3Core;
