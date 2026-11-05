(() => {
  "use strict";
  const core = X3Core;
  const $ = (id) => document.getElementById(id);
  const key = (id) => "x3-workshop:v1:" + id;
  let draft = core.blank(core.models[0].id);
  let saveTimer;
  let fileGeneration = 0;
  let packageHash = "";
  function message(text, bad = false) {
    $("status").textContent = text;
    $("status").classList.toggle("error", bad);
  }
  function stored(id) {
    try {
      const raw = localStorage.getItem(key(id));
      if (raw) {
        const clean = core.parse(raw);
        if (clean.model === id) return clean;
      }
    } catch { message("Gespeicherter Entwurf konnte nicht geladen werden.", true); }
    return core.blank(id);
  }
  function read() {
    const result = core.blank(draft.model);
    core.components.forEach(({ id }) => { result.firmware[id] = $("fw-" + id).value; });
    ["motor", "controller", "battery"].forEach((id) => { result.hardware[id] = $("hw-" + id).value; });
    result.tuning.fieldWeakeningRequested = $("field-weakening").checked;
    ["fwStartKmh", "fwCurrentA", "ecoKmh", "driveKmh", "sportKmh"].forEach((id) => {
      const value = $(id).value;
      result.tuning[id] = value === "" ? null : Number(value);
    });
    result.tuning.regen = $("regen").value;
    result.notes = $("notes").value;
    return core.validate(result);
  }
  function persist() {
    clearTimeout(saveTimer);
    draft = read();
    try {
      localStorage.setItem(key(draft.model), JSON.stringify(draft));
      message("Entwurf auf diesem Gerät gespeichert.");
    } catch { message("Browserspeicher nicht verfügbar. Bitte als JSON exportieren.", true); }
    render();
  }
  function addText(parent, tag, value, className) {
    const child = document.createElement(tag);
    child.textContent = value;
    if (className) child.className = className;
    parent.append(child);
    return child;
  }
  function render() {
    const selected = core.model(draft.model);
    $("model-name").textContent = selected.name;
    $("model-mark").textContent = selected.family;
    document.querySelectorAll("[data-model]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.model === draft.model));
    });
    const body = $("firmware-rows");
    body.replaceChildren();
    core.components.forEach(({ id, name, detail }) => {
      const row = document.createElement("tr");
      const label = document.createElement("th");
      label.scope = "row";
      addText(label, "strong", name);
      addText(label, "span", detail, "sub");
      row.append(label);
      addText(row, "td", draft.firmware[id] || "Nicht erfasst", "mono");
      addText(row, "td", "Unbekannt", "muted");
      addText(row, "td", "Unbekannt", "muted");
      body.append(row);
    });
    const evidence = $("observation");
    evidence.replaceChildren();
    if (draft.model === "max-g3-d") {
      addText(evidence, "p", "Beobachteter Originalstand · Community-Bericht vom 13.10.2026", "eyebrow");
      addText(evidence, "p", "VCU 1.6.4 · MCU 1.6.0 · BLE 0.4.5 · BMS 4.1.6.8", "mono");
      addText(evidence, "p", "Ein einzelner G3-D-Bericht, keine Bestätigung der neuesten oder vorletzten Version. Hardware-Revision und Release-Datum unbekannt.", "muted");
      const link = addText(evidence, "a", "Beleg öffnen ↗");
      link.href = core.observedG3.source;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    } else {
      addText(evidence, "p", "Noch kein belastbarer komponentengenauer Ausgangsbestand für diese D-Variante vorhanden.", "muted");
    }
    const assessment = core.assess(draft);
    $("coverage").textContent = (4 - assessment.missing.length) + " / 4 Stände erfasst";
    $("assessment").textContent = assessment.detail;
    $("missing").textContent = assessment.missing.length ? "Noch offen: " + assessment.missing.join(", ") : "Alle Stände eingetragen. Die Hardware- und Flashprüfung bleibt offen.";
    $("fw-draft-state").textContent = draft.tuning.fieldWeakeningRequested ? "Angefragt · nicht angewendet" : "Nicht angefragt";
    $("fw-parameters").disabled = !draft.tuning.fieldWeakeningRequested;
  }
  function fill() {
    core.components.forEach(({ id }) => { $("fw-" + id).value = draft.firmware[id]; });
    ["motor", "controller", "battery"].forEach((id) => { $("hw-" + id).value = draft.hardware[id]; });
    $("field-weakening").checked = draft.tuning.fieldWeakeningRequested;
    ["fwStartKmh", "fwCurrentA", "ecoKmh", "driveKmh", "sportKmh"].forEach((id) => {
      $(id).value = draft.tuning[id] === null ? "" : String(draft.tuning[id]);
    });
    $("regen").value = draft.tuning.regen;
    $("notes").value = draft.notes;
    render();
  }
  core.models.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.model = item.id;
    button.textContent = item.name;
    button.addEventListener("click", () => {
      try {
        persist();
        draft = stored(item.id);
        fill();
        message(item.name + " ausgewählt. Hardwarezuordnung bleibt unbestätigt.");
      } catch (error) { message(error.message, true); }
    });
    $("model-picker").append(button);
  });
  $("draft-form").addEventListener("input", () => {
    clearTimeout(saveTimer);
    message("Ungespeicherte Änderungen …");
    saveTimer = setTimeout(() => {
      try { persist(); } catch (error) { message(error.message, true); }
    }, 500);
  });
  $("draft-form").addEventListener("submit", (event) => {
    event.preventDefault();
    try { persist(); } catch (error) { message(error.message, true); }
  });
  $("export").addEventListener("click", () => {
    try {
      persist();
      const payload = JSON.stringify(draft, null, 2) + "\n";
      const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = draft.model + ".x3profile.json";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      message("JSON-Profil exportiert. Es ist keine flashbare Firmware.");
    } catch (error) { message(error.message, true); }
  });
  $("import").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    event.target.value = "";
    if (!file) return;
    try {
      if (file.size > 65536) throw new Error("Profildatei maximal 64 KiB.");
      const imported = core.parse(await file.text());
      // Save the existing model before switching; invalid input never replaces it.
      persist();
      draft = imported;
      fill();
      persist();
      message("Profil importiert. Gerätezuordnung und Parameter sind nicht hardwaregeprüft.");
    } catch (error) { message(error.message, true); }
  });
  $("reset").addEventListener("click", () => {
    if (!confirm("Diesen lokalen Modellentwurf löschen? Exportierte Dateien bleiben erhalten.")) return;
    clearTimeout(saveTimer);
    try { localStorage.removeItem(key(draft.model)); } catch {}
    draft = core.blank(draft.model);
    fill();
    message("Lokalen Entwurf zurückgesetzt.");
  });
  function compareHash() {
    const expected = $("expected-hash").value.trim().toLowerCase();
    if (!expected) { $("hash-comparison").textContent = "Keine Referenz-Prüfsumme angegeben."; return; }
    if (!/^[a-f0-9]{64}$/.test(expected)) { $("hash-comparison").textContent = "Eine SHA-256-Prüfsumme hat 64 Hex-Zeichen."; return; }
    $("hash-comparison").textContent = packageHash
      ? (packageHash === expected ? "Prüfsummen stimmen überein. Das belegt keine Kompatibilität oder Herkunft." : "Prüfsummen unterscheiden sich.")
      : "Bitte zuerst eine Datei auswählen.";
  }
  $("expected-hash").addEventListener("input", compareHash);
  $("package").addEventListener("change", async (event) => {
    const generation = ++fileGeneration;
    const file = event.target.files[0];
    packageHash = "";
    $("file-hash").textContent = "—";
    $("hash-comparison").textContent = "";
    if (!file) { $("file-result").textContent = "Noch keine Datei ausgewählt."; return; }
    $("file-result").textContent = file.name + " · " + file.size.toLocaleString("de-DE") + " Bytes";
    if (file.size < 1 || file.size > 16777216) {
      $("hash-comparison").textContent = "Datei muss zwischen 1 Byte und 16 MiB groß sein.";
      return;
    }
    if (!globalThis.crypto || !globalThis.crypto.subtle) {
      $("hash-comparison").textContent = "SHA-256 ist in diesem Browser-Kontext nicht verfügbar.";
      return;
    }
    try {
      const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
      if (generation !== fileGeneration) return;
      packageHash = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
      $("file-hash").textContent = packageHash;
      compareHash();
    } catch {
      if (generation === fileGeneration) $("hash-comparison").textContent = "Datei konnte nicht geprüft werden.";
    }
  });
  draft = stored(draft.model);
  fill();
})();
