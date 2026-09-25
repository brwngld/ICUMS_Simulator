(() => {
  const regimes = Array.isArray(window.boeRegimes) ? window.boeRegimes : [];
  const byCode = new Map(regimes);
  const dialog = document.querySelector("#boe-regime-dialog");
  const codeField = document.querySelector("#boe-regime-code");
  const nameField = document.querySelector("#boe-regime-name");
  const results = document.querySelector("#boe-regime-results");
  let page = 1;

  function updateReuseDocument() {
    const selected = document.querySelector('input[name="reuse-document"]:checked')?.value || "NONE";
    const showsDetails = ["IDF", "EMDA", "LOC"].includes(selected);
    const extra = document.querySelector("#boe-reuse-extra");
    const cancelledExtra = document.querySelector("#boe-cancelled-extra");
    extra.hidden = !showsDetails;
    cancelledExtra.hidden = selected !== "CANCELLED";
    document.querySelector("#boe-loc-note").hidden = selected !== "LOC";
    document.querySelector("#boe-reuse-label").textContent = selected === "EMDA" ? "eMda Docs." : selected;
    if (!showsDetails) {
      extra.querySelectorAll("input").forEach((field) => { field.value = ""; });
    }
    if (selected !== "CANCELLED") document.querySelector("#boe-cancelled-ucr").value = "";
  }

  function choose(code, name) {
    codeField.value = code;
    nameField.value = name;
    document.querySelector("#boe-cpc-code").value = "";
    document.querySelector("#boe-cpc-name").value = "";
    dialog.close();
  }

  function render() {
    const codeFilter = document.querySelector("#boe-regime-filter-code").value.trim();
    const nameFilter = document.querySelector("#boe-regime-filter-name").value.trim().toLowerCase();
    const filtered = regimes.filter(([code, name]) =>
      (!codeFilter || code.includes(codeFilter)) && (!nameFilter || name.toLowerCase().includes(nameFilter))
    );
    const pageCount = Math.max(1, Math.ceil(filtered.length / 30));
    page = Math.min(page, pageCount);
    results.replaceChildren();
    filtered.slice((page - 1) * 30, page * 30).forEach(([code, name], index) => {
      const row = document.createElement("tr");
      row.tabIndex = 0;
      [String((page - 1) * 30 + index + 1), code, name, "Regime(Customs) Code"].forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      });
      row.addEventListener("click", () => choose(code, name));
      row.addEventListener("keydown", (event) => { if (event.key === "Enter") choose(code, name); });
      results.append(row);
    });
    if (!filtered.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = "No data found.";
      row.append(cell);
      results.append(row);
    }
    window.drawDialogPager(document.querySelector("#boe-regime-pagination"), {
      total: filtered.length,
      page,
      pageCount,
      onPage: (nextPage) => { page = nextPage; render(); },
    });
  }

  codeField.addEventListener("change", () => {
    codeField.value = codeField.value.trim();
    nameField.value = byCode.get(codeField.value) || "";
    document.querySelector("#boe-cpc-code").value = "";
    document.querySelector("#boe-cpc-name").value = "";
  });
  document.querySelector("#boe-regime-search").addEventListener("click", () => { page = 1; render(); dialog.showModal(); });
  document.querySelector("#boe-regime-close").addEventListener("click", () => dialog.close());
  document.querySelector("#boe-regime-filter-submit").addEventListener("click", () => { page = 1; render(); });
  ["#boe-regime-filter-code", "#boe-regime-filter-name"].forEach((selector) => {
    document.querySelector(selector).addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); page = 1; render(); }
    });
  });
  document.querySelectorAll('input[name="reuse-document"]').forEach((radio) => radio.addEventListener("change", updateReuseDocument));
  updateReuseDocument();

  // CPC results are always restricted to the currently selected regime.
  const cpcDialog = document.querySelector("#boe-cpc-dialog");
  const cpcResults = document.querySelector("#boe-cpc-results");
  let cpcPage = 1;
  function cpcMessage(message) {
    cpcResults.replaceChildren();
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.textContent = message;
    row.append(cell);
    cpcResults.append(row);
  }
  async function renderCpcs() {
    const regime = codeField.value.trim();
    if (!regime) {
      cpcMessage("Select a Regime before searching for a CPC.");
      window.drawDialogPager(document.querySelector("#boe-cpc-pagination"), { total: 0, page: 1, pageCount: 1, onPage: () => {} });
      return;
    }
    cpcMessage("Loading…");
    const query = new URLSearchParams({ regime, q: document.querySelector("#boe-cpc-filter").value.trim(), page: String(cpcPage) });
    try {
      const response = await fetch(`${window.boeCpcSearchUrl}?${query}`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error();
      const data = await response.json();
      cpcPage = data.page;
      cpcResults.replaceChildren();
      data.results.forEach((item, index) => {
        const row = document.createElement("tr");
        row.tabIndex = 0;
        [String((data.page - 1) * 100 + index + 1), item.code, item.description].forEach((value) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.append(cell);
        });
        const chooseCpc = () => {
          document.querySelector("#boe-cpc-code").value = item.code;
          document.querySelector("#boe-cpc-name").value = item.description;
          cpcDialog.close();
        };
        row.addEventListener("click", chooseCpc);
        row.addEventListener("keydown", (event) => { if (event.key === "Enter") chooseCpc(); });
        cpcResults.append(row);
      });
      if (!data.results.length) cpcMessage("No data found.");
      window.drawDialogPager(document.querySelector("#boe-cpc-pagination"), {
        total: data.total, page: data.page, pageCount: data.page_count,
        onPage: (nextPage) => { cpcPage = nextPage; renderCpcs(); },
      });
    } catch (_error) {
      cpcMessage("The CPC list could not be loaded. Please try again.");
    }
  }
  async function resolveCpcCode() {
    const cpcCode = document.querySelector("#boe-cpc-code");
    const cpcName = document.querySelector("#boe-cpc-name");
    const regime = codeField.value.trim();
    const enteredCode = cpcCode.value.trim().toUpperCase();
    cpcCode.value = enteredCode;
    cpcName.value = "";
    if (!regime || !enteredCode) return;

    const query = new URLSearchParams({ regime, q: enteredCode, page: "1" });
    try {
      const response = await fetch(`${window.boeCpcSearchUrl}?${query}`, { headers: { Accept: "application/json" } });
      if (!response.ok) return;
      const data = await response.json();
      const exactMatch = data.results.find((item) => item.code.toUpperCase() === enteredCode);
      if (exactMatch && cpcCode.value === enteredCode && codeField.value.trim() === regime) {
        cpcName.value = exactMatch.description;
      }
    } catch (_error) {
      cpcName.value = "";
    }
  }
  document.querySelector("#boe-cpc-search").addEventListener("click", () => { cpcPage = 1; renderCpcs(); cpcDialog.showModal(); });
  document.querySelector("#boe-cpc-close").addEventListener("click", () => cpcDialog.close());
  document.querySelector("#boe-cpc-filter-submit").addEventListener("click", () => { cpcPage = 1; renderCpcs(); });
  document.querySelector("#boe-cpc-code").addEventListener("change", resolveCpcCode);
  document.querySelector("#boe-cpc-filter").addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); cpcPage = 1; renderCpcs(); }
  });

  const zones = Array.isArray(window.boeZones) ? window.boeZones : [];
  const zoneByCode = new Map(zones);
  const zoneDialog = document.querySelector("#boe-zone-dialog");
  const zoneCode = document.querySelector("#boe-zone-code");
  const zoneName = document.querySelector("#boe-zone-name");
  const zoneResults = document.querySelector("#boe-zone-results");

  function chooseZone(code, name) {
    zoneCode.value = code;
    zoneName.value = name;
    zoneDialog.close();
  }

  function renderZones() {
    const codeFilter = document.querySelector("#boe-zone-filter-code").value.trim().toUpperCase();
    const nameFilter = document.querySelector("#boe-zone-filter-name").value.trim().toLowerCase();
    const filtered = zones.filter(([code, name]) =>
      (!codeFilter || code.includes(codeFilter)) && (!nameFilter || name.toLowerCase().includes(nameFilter))
    );
    zoneResults.replaceChildren();
    filtered.forEach(([code, name], index) => {
      const row = document.createElement("tr");
      row.tabIndex = 0;
      [String(index + 1), code, name, "ZONE CODE"].forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      });
      row.addEventListener("click", () => chooseZone(code, name));
      row.addEventListener("keydown", (event) => { if (event.key === "Enter") chooseZone(code, name); });
      zoneResults.append(row);
    });
    if (!filtered.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = "No data found.";
      row.append(cell);
      zoneResults.append(row);
    }
    window.drawDialogPager(document.querySelector("#boe-zone-pagination"), {
      total: filtered.length, page: 1, pageCount: 1, onPage: () => {},
    });
  }

  zoneCode.addEventListener("change", () => {
    zoneCode.value = zoneCode.value.trim().toUpperCase();
    zoneName.value = zoneByCode.get(zoneCode.value) || "";
  });
  document.querySelector("#boe-zone-search").addEventListener("click", () => { renderZones(); zoneDialog.showModal(); });
  document.querySelector("#boe-zone-close").addEventListener("click", () => zoneDialog.close());
  document.querySelector("#boe-zone-filter-submit").addEventListener("click", renderZones);
  ["#boe-zone-filter-code", "#boe-zone-filter-name"].forEach((selector) => {
    document.querySelector(selector).addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); renderZones(); }
    });
  });
})();
