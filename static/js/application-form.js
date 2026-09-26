(() => {
  if (!window.appInitial) return;
  const initial = window.appInitial;
  let appId = new URLSearchParams(location.search).get("app");
  appId = appId && /^\d+$/.test(appId) ? Number(appId) : null;
  if (window.appMdaMode) appId = window.appMdaRequestId;
  const countryCodes = new Map(window.ucrCountryCodes || []);

  // --- Prefill every [data-app-field] from the initial payload ---
  document.querySelectorAll("[data-app-field]").forEach((field) => {
    const value = initial[field.dataset.appField];
    if (value !== undefined && value !== null) field.value = value;
  });
  ["consignor", "consignee"].forEach((role) => {
    const box = document.querySelector(`[data-app-same="${role}"]`);
    if (box && initial[`${role}_same`] !== undefined) box.checked = Boolean(initial[`${role}_same`]);
  });

  // --- Tabs ---
  const tabs = [...document.querySelectorAll(".app-tab")];
  function showTab(name) {
    tabs.forEach((tab) => tab.setAttribute("aria-current", tab.dataset.appTab === name ? "tab" : "false"));
    document.querySelectorAll(".app-tab-panel").forEach((panel) => { panel.hidden = panel.id !== `app-tab-${name}`; });
    if (name === "confirmation") renderConfirmation();
  }
  tabs.forEach((tab) => tab.addEventListener("click", () => {
    showTab(tab.dataset.appTab);
    history.replaceState(null, "", `#${tab.dataset.appTab}`);
  }));
  // --- Same-as consignor/consignee ---
  function applySame(role) {
    const box = document.querySelector(`[data-app-same="${role}"]`);
    const fields = document.querySelectorAll(`[data-app-field^="${role}."]`);
    const sourceRole = role === "consignor" ? "exporter" : "importer";
    const sourceKey = role === "consignor" ? "name" : "code";
    fields.forEach((field) => {
      const key = field.dataset.appField.split(".")[1];
      field.disabled = box.checked;
      if (box.checked) field.value = document.querySelector(`[data-app-field="${sourceRole}.${key === "name" ? sourceKey : key}"]`)?.value || "";
    });
    syncCountryNames();
  }
  ["consignor", "consignee"].forEach((role) => {
    const box = document.querySelector(`[data-app-same="${role}"]`);
    box.addEventListener("change", () => applySame(role));
    applySame(role);
  });
  ["exporter", "importer"].forEach((sourceRole) => {
    document.querySelectorAll(`[data-app-field^="${sourceRole}."]`).forEach((field) => field.addEventListener("input", () => {
      const targetRole = sourceRole === "exporter" ? "consignor" : "consignee";
      if (document.querySelector(`[data-app-same="${targetRole}"]`).checked) applySame(targetRole);
    }));
  });

  // --- Required General fields and cargo-type-specific transport fields ---
  const generalRequired = [...document.querySelectorAll("#app-tab-general .summary-grid label")]
    .filter((label) => label.querySelector("span")?.textContent.trim() === "*")
    .map((label) => ({ label, field: label.nextElementSibling?.matches("input, select, textarea") ? label.nextElementSibling : label.nextElementSibling?.querySelector("[data-app-field]") }))
    .filter(({ field }) => field?.matches("input, select, textarea"));
  function markRequired({ label, field }, invalid) {
    field.classList.toggle("ucr-field-invalid", invalid);
    label.classList.toggle("ucr-label-invalid", invalid);
    if (invalid) field.setAttribute("aria-invalid", "true");
    else field.removeAttribute("aria-invalid");
  }
  function validateGeneral() {
    const missing = generalRequired.filter(({ field }) => !field.value.trim());
    generalRequired.forEach((entry) => markRequired(entry, missing.includes(entry)));
    if (missing.length) {
      showTab("general");
      report(`Complete the ${missing.length} highlighted required General field${missing.length === 1 ? "" : "s"} before saving.`, true);
      missing[0].field.focus();
      return false;
    }
    return true;
  }
  document.querySelector("#app-tab-general").addEventListener("input", (event) => {
    const entry = generalRequired.find(({ field }) => field === event.target);
    if (entry && event.target.value.trim()) markRequired(entry, false);
  });
  const cargoType = document.querySelector('[data-app-field="cargo_type"]');
  const containerStatus = document.querySelector("#app-container-status");
  function updateContainerStatus() {
    containerStatus.hidden = cargoType.value !== "C";
  }
  if (cargoType.value === "C, Container") cargoType.value = "C";
  cargoType.addEventListener("change", updateContainerStatus);
  updateContainerStatus();

  // --- Country code/name controls for inherited and editable parties ---
  function syncCountryNames() {
    document.querySelectorAll("[data-app-country-name-for]").forEach((nameField) => {
      const codeField = document.querySelector(`[data-app-field="${nameField.dataset.appCountryNameFor}"]`);
      nameField.value = countryCodes.get(codeField?.value.trim().toUpperCase()) || "";
    });
    const itemCode = document.querySelector('[data-item-field="origin_country"]');
    const itemName = document.querySelector("[data-item-country-name]");
    if (itemCode && itemName) itemName.value = countryCodes.get(itemCode.value.trim().toUpperCase()) || "";
  }
  document.querySelectorAll(".app-country-field [data-app-field]").forEach((field) => field.addEventListener("change", () => {
    field.value = field.value.trim().toUpperCase();
    syncCountryNames();
  }));
  const countryDialog = document.querySelector("#app-country-dialog");
  const countryResults = document.querySelector("#app-country-results");
  let activeCountryField = null;
  let countryPage = 1;
  function renderCountries() {
    const codeFilter = document.querySelector("#app-country-filter-code").value.trim().toUpperCase();
    const nameFilter = document.querySelector("#app-country-filter-name").value.trim().toLowerCase();
    const filtered = [...countryCodes].filter(([code, name]) => (!codeFilter || code.includes(codeFilter)) && (!nameFilter || name.toLowerCase().includes(nameFilter)));
    const pageCount = Math.max(1, Math.ceil(filtered.length / 10));
    countryPage = Math.min(countryPage, pageCount);
    countryResults.replaceChildren();
    filtered.slice((countryPage - 1) * 10, countryPage * 10).forEach(([code, name], index) => {
      const row = document.createElement("tr");
      row.tabIndex = 0;
      row.innerHTML = `<td>${(countryPage - 1) * 10 + index + 1}</td><td>${code}</td><td>${name}</td><td>COUNTRY CODE</td>`;
      row.addEventListener("click", () => { activeCountryField.value = code; activeCountryField.dispatchEvent(new Event("change", { bubbles: true })); countryDialog.close(); });
      row.addEventListener("keydown", (event) => { if (event.key === "Enter") row.click(); });
      countryResults.append(row);
    });
    window.drawDialogPager(document.querySelector("#app-country-pagination"), { total: filtered.length, page: countryPage, pageCount, onPage: (page) => { countryPage = page; renderCountries(); } });
  }
  document.querySelectorAll("[data-app-country-search]").forEach((button) => button.addEventListener("click", () => {
    activeCountryField = document.querySelector(`[data-app-field="${button.dataset.appCountrySearch}"]`);
    countryPage = 1;
    renderCountries();
    countryDialog.showModal();
  }));
  document.querySelector("[data-item-country-search]").addEventListener("click", () => {
    activeCountryField = document.querySelector('[data-item-field="origin_country"]');
    countryPage = 1;
    renderCountries();
    countryDialog.showModal();
  });
  document.querySelector('[data-item-field="origin_country"]').addEventListener("change", (event) => {
    event.target.value = event.target.value.trim().toUpperCase();
    syncCountryNames();
  });
  document.querySelector("#app-country-close").addEventListener("click", () => countryDialog.close());
  document.querySelector("#app-country-filter-submit").addEventListener("click", () => { countryPage = 1; renderCountries(); });
  syncCountryNames();

  // --- Admin-managed port lookup shared by Arrival and Departure ---
  const portDialog = document.querySelector("#app-port-dialog");
  const portResults = document.querySelector("#app-port-results");
  let activePortField = null;
  let portPage = 1;
  function appendPortCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value || "";
    row.append(cell);
  }
  async function renderPorts() {
    const query = new URLSearchParams({
      code: document.querySelector("#app-port-filter-code").value.trim(),
      name: document.querySelector("#app-port-filter-name").value.trim(),
      country: document.querySelector("#app-port-filter-country").value.trim(),
      page: String(portPage),
    });
    portResults.replaceChildren();
    const loadingRow = document.createElement("tr");
    const loadingCell = document.createElement("td");
    loadingCell.colSpan = 5;
    loadingCell.textContent = "Loading…";
    loadingRow.append(loadingCell);
    portResults.append(loadingRow);
    try {
      const response = await fetch(`${window.appPortCodeSearchUrl}?${query}`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("Port search failed");
      const data = await response.json();
      portPage = data.page;
      portResults.replaceChildren();
      if (!data.results.length) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 5;
        cell.textContent = "No data found.";
        row.append(cell);
        portResults.append(row);
      }
      data.results.forEach((port, index) => {
        const row = document.createElement("tr");
        row.tabIndex = 0;
        appendPortCell(row, String((data.page - 1) * 10 + index + 1));
        appendPortCell(row, port.code);
        appendPortCell(row, port.name);
        appendPortCell(row, port.country_code);
        appendPortCell(row, port.country_name);
        row.addEventListener("click", () => {
          activePortField.value = `${port.code}, ${port.name}`;
          activePortField.dispatchEvent(new Event("change", { bubbles: true }));
          portDialog.close();
        });
        row.addEventListener("keydown", (event) => { if (event.key === "Enter") row.click(); });
        portResults.append(row);
      });
      window.drawDialogPager(document.querySelector("#app-port-pagination"), {
        total: data.total,
        page: data.page,
        pageCount: data.page_count,
        onPage: (page) => { portPage = page; renderPorts(); },
      });
    } catch (_error) {
      portResults.replaceChildren();
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 5;
      cell.textContent = "The port list could not be loaded. Please try again.";
      row.append(cell);
      portResults.append(row);
    }
  }
  document.querySelectorAll("[data-app-port-search]").forEach((button) => button.addEventListener("click", () => {
    activePortField = document.querySelector(`[data-app-field="${button.dataset.appPortSearch}"]`);
    portPage = 1;
    renderPorts();
    portDialog.showModal();
  }));
  document.querySelector("#app-port-close").addEventListener("click", () => portDialog.close());
  document.querySelector("#app-port-filter-submit").addEventListener("click", () => { portPage = 1; renderPorts(); });
  ["#app-port-filter-code", "#app-port-filter-name", "#app-port-filter-country"].forEach((selector) => {
    document.querySelector(selector).addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); portPage = 1; renderPorts(); }
    });
  });

  // --- Confirmation MDA application launcher ---
  const mdaDialog = document.querySelector("#app-mda-dialog");
  const mdaAgency = document.querySelector("#app-mda-agency");
  const mdaApplication = document.querySelector("#app-mda-application");
  const mdaProcess = document.querySelector("#app-mda-process");
  const mdaStatus = document.querySelector("#app-mda-status");
  const mdaType = document.querySelector("#app-mda-type");
  const mdaMaster = document.querySelector("#app-mda-master");
  const mdaRows = document.querySelector("#app-mda-rows");
  let mdaOptions = [];
  let activeMdaRow = null;
  function resetSelect(select, label = "-- Select One --") {
    select.replaceChildren(new Option(label, ""));
  }
  function fillMdaApplications() {
    resetSelect(mdaApplication);
    resetSelect(mdaProcess);
    const agency = mdaOptions.find((item) => String(item.id) === mdaAgency.value);
    (agency?.applications || []).forEach((item) => mdaApplication.add(new Option(`${item.code}, ${item.name}`, item.id)));
  }
  function fillMdaProcesses() {
    resetSelect(mdaProcess);
    const agency = mdaOptions.find((item) => String(item.id) === mdaAgency.value);
    const application = agency?.applications.find((item) => String(item.id) === mdaApplication.value);
    (application?.processes || []).forEach((item) => mdaProcess.add(new Option(`${item.code}, ${item.name}`, item.id)));
  }
  async function loadMdaOptions(preferredCode = "") {
    mdaStatus.hidden = true;
    resetSelect(mdaAgency, "Loading…");
    resetSelect(mdaApplication);
    resetSelect(mdaProcess);
    try {
      const response = await fetch(window.appMdaOptionsUrl, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("MDA configuration could not be loaded");
      mdaOptions = (await response.json()).results;
      resetSelect(mdaAgency);
      mdaOptions.forEach((item) => mdaAgency.add(new Option(`${item.code}, ${item.name}`, item.id)));
      const preferred = mdaOptions.find((item) => item.code === preferredCode);
      if (preferred) {
        mdaAgency.value = String(preferred.id);
        fillMdaApplications();
      }
    } catch (_error) {
      resetSelect(mdaAgency, "-- Configuration unavailable --");
      mdaStatus.textContent = "The MDA configuration could not be loaded. Please contact the administrator.";
      mdaStatus.hidden = false;
    }
  }
  mdaAgency.addEventListener("change", fillMdaApplications);
  mdaApplication.addEventListener("change", fillMdaProcesses);
  function updateMasterRequirement() {
    const required = mdaType.value === "SB";
    mdaMaster.readOnly = !required;
    mdaMaster.required = required;
    if (!required) mdaMaster.value = "";
  }
  mdaType.addEventListener("change", updateMasterRequirement);
  function openMdaDialog(preferredCode = "") {
    activeMdaRow = null;
    document.querySelector("#app-mda-ucr").value = document.querySelector("#app-ucr").value;
    mdaType.value = "";
    mdaMaster.value = "";
    updateMasterRequirement();
    loadMdaOptions(preferredCode);
    mdaDialog.showModal();
  }
  document.querySelector("#app-mda-add")?.addEventListener("click", () => openMdaDialog());
  mdaRows?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-mda-create]");
    if (button) openMdaDialog(button.dataset.mdaCreate);
  });
  document.querySelector("#app-mda-close").addEventListener("click", () => mdaDialog.close());
  function makeMdaRow(mdaCode) {
    const row = document.createElement("tr");
    const definitions = [
      [mdaCode, "cell-center", ""], ["", "", "application"], ["", "", "process"],
      [document.querySelector('[data-app-field="exporter.name"]')?.value || "", "cell-left", "exporter.name"],
      [document.querySelector('[data-app-field="importer.code"]')?.value || "", "cell-left", "importer.code"],
      ["", "cell-center", "app-no"], ["", "cell-center", "submitted"], ["", "cell-center", "status"],
    ];
    definitions.forEach(([text, className, confirm]) => {
      const cell = document.createElement("td");
      cell.textContent = text;
      if (className) cell.className = className;
      if (confirm) cell.dataset.confirm = confirm;
      row.append(cell);
    });
    const actionCell = document.createElement("td");
    actionCell.className = "cell-center";
    const createButton = document.createElement("button");
    createButton.type = "button";
    createButton.className = "ucr-row-action";
    createButton.dataset.mdaCreate = mdaCode;
    createButton.textContent = "Create";
    actionCell.append(createButton);
    row.append(actionCell);
    mdaRows.append(row);
    return row;
  }
  function showMdaRequest(record) {
    let row = [...mdaRows.rows].find((candidate) =>
      candidate.children[0]?.textContent.trim() === record.mda && !candidate.querySelector('[data-confirm="app-no"]')?.textContent.trim()
    );
    if (!row) row = makeMdaRow(record.mda);
    row.querySelector('[data-confirm="application"]').textContent = record.application;
    row.querySelector('[data-confirm="process"]').textContent = record.process;
    const numberCell = row.querySelector('[data-confirm="app-no"]');
    numberCell.replaceChildren();
    const numberLink = document.createElement("a");
    numberLink.href = record.url;
    numberLink.textContent = record.application_no;
    numberCell.append(numberLink);
    row.querySelector('[data-confirm="submitted"]').textContent = record.created_at;
    row.querySelector('[data-confirm="status"]').textContent = record.status;
  }
  if (mdaRows) (window.appMdaRequests || []).forEach(showMdaRequest);
  document.querySelector("#app-mda-create").addEventListener("click", async (event) => {
    const type = mdaType.value;
    const agency = mdaOptions.find((item) => String(item.id) === mdaAgency.value);
    const application = agency?.applications.find((item) => String(item.id) === mdaApplication.value);
    const process = application?.processes.find((item) => String(item.id) === mdaProcess.value);
    if (!type || !agency || !application || !process || (type === "SB" && !mdaMaster.value.trim())) {
      mdaStatus.textContent = "Complete all required fields before creating the application form.";
      mdaStatus.hidden = false;
      return;
    }
    if (!appId) {
      mdaStatus.textContent = "Save the Consignment Document before creating an MDA application.";
      mdaStatus.hidden = false;
      return;
    }
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const record = await post(window.appMdaRequestCreateUrl, {
        consignment_application_id: appId,
        mda_id: agency.id,
        application_id: application.id,
        process_id: process.id,
        consignment_type: type,
        master_no: mdaMaster.value.trim(),
      });
      showMdaRequest(record);
      mdaDialog.close();
      window.alert(`Application ${record.application_no} created successfully.`);
    } catch (error) {
      mdaStatus.textContent = error.message;
      mdaStatus.hidden = false;
    } finally {
      button.disabled = false;
    }
  });

  // --- MDA Approval tab ---
  let approvalParties = Array.isArray(window.appApprovalParties) ? [...window.appApprovalParties] : [];
  function renderApprovalParties() {
    const body = document.querySelector("#app-party-rows");
    if (!body) return;
    body.replaceChildren();
    if (!approvalParties.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 2;
      cell.textContent = "No data found.";
      row.append(cell);
      body.append(row);
      return;
    }
    approvalParties.forEach((party) => {
      const row = document.createElement("tr");
      [party.name, party.mailbox].forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      });
      body.append(row);
    });
  }
  document.querySelector("#app-party-add")?.addEventListener("click", () => {
    const name = window.prompt("Third Party Distribution name:", "")?.trim();
    if (!name) return;
    const mailbox = window.prompt("Mailbox:", "")?.trim() || "";
    approvalParties.push({ name, mailbox });
    renderApprovalParties();
  });
  document.querySelector("#app-party-reset")?.addEventListener("click", () => {
    approvalParties = [];
    renderApprovalParties();
  });
  renderApprovalParties();

  // --- Invoice currency lookup and FCY -> GHS conversion ---
  const currencies = [
    ["GHS", "Ghanaian Cedi", 1], ["USD", "US $", 12.41], ["GBP", "STD Pound", 16.22],
    ["EUR", "EURO", 14.08], ["CAD", "Canadian $", 9.02], ["CHF", "Switz. Franc", 13.90],
    ["JPY", "Japanese Yen", 0.085], ["SEK", "Swedish Kronor", 1.20], ["NOK", "Norwegian Kronor", 1.18],
    ["DKK", "Danish Kronor", 1.89], ["AUD", "Australian $", 8.10], ["ZAR", "South Africa", 0.71],
    ["CNY", "Chinese Yuan", 1.71], ["NZD", "New Zealand $", 7.35], ["NGN", "Nigerian naira", 0.008],
    ["XOF", "franc CFA BCEAO", 0.021],
  ];
  const currencyCode = document.querySelector('[data-app-field="currency"]');
  const currencyName = document.querySelector("#app-currency-name");
  const exchangeRate = document.querySelector('[data-app-field="exchange_rate"]');
  const currencyDialog = document.querySelector("#app-currency-dialog");
  const currencyResults = document.querySelector("#app-currency-results");
  const moneyNumber = (value) => {
    const parsed = Number(String(value || "").replace(/,/g, ""));
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const moneyText = (value) => value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  function calculateInvoice() {
    const rate = moneyNumber(exchangeRate.value);
    const pairs = [["fob_fcy", "fob_ncy"], ["freight_fcy", "freight_ncy"], ["insurance_fcy", "insurance_ncy"], ["other_costs_fcy", "other_costs_ncy"]];
    let customs = 0;
    pairs.forEach(([fcyKey, ncyKey]) => {
      const fcy = moneyNumber(document.querySelector(`[data-app-field="${fcyKey}"]`).value);
      customs += fcy;
      document.querySelector(`[data-app-field="${ncyKey}"]`).value = moneyText(fcy * rate);
    });
    document.querySelector('[data-app-field="customs_value_fcy"]').value = moneyText(customs);
    document.querySelector('[data-app-field="customs_value_ncy"]').value = moneyText(customs * rate);
  }
  function chooseCurrency(code) {
    const match = currencies.find(([itemCode]) => itemCode === code.toUpperCase());
    if (!match) return false;
    currencyCode.value = match[0];
    currencyName.value = match[1];
    exchangeRate.value = Number(match[2]).toFixed(4);
    document.querySelectorAll("[data-currency-prefix]").forEach((field) => { field.value = match[0]; });
    calculateInvoice();
    return true;
  }
  let currencyPage = 1;
  function renderCurrencies() {
    const codeFilter = document.querySelector("#app-currency-filter-code").value.trim().toUpperCase();
    const nameFilter = document.querySelector("#app-currency-filter-name").value.trim().toLowerCase();
    const filtered = currencies.filter(([code, name]) => (!codeFilter || code.includes(codeFilter)) && (!nameFilter || name.toLowerCase().includes(nameFilter)));
    const pageCount = Math.max(1, Math.ceil(filtered.length / 10));
    currencyPage = Math.min(currencyPage, pageCount);
    currencyResults.replaceChildren();
    filtered.slice((currencyPage - 1) * 10, currencyPage * 10).forEach(([code, name], index) => {
      const row = document.createElement("tr");
      row.tabIndex = 0;
      row.innerHTML = `<td>${(currencyPage - 1) * 10 + index + 1}</td><td>${code}</td><td>${name}</td><td>CURRENCY CODE</td>`;
      row.addEventListener("click", () => { chooseCurrency(code); currencyDialog.close(); });
      row.addEventListener("keydown", (event) => { if (event.key === "Enter") row.click(); });
      currencyResults.append(row);
    });
    window.drawDialogPager(document.querySelector("#app-currency-pagination"), { total: filtered.length, page: currencyPage, pageCount, onPage: (page) => { currencyPage = page; renderCurrencies(); } });
  }
  document.querySelector("#app-currency-search").addEventListener("click", () => { currencyPage = 1; renderCurrencies(); currencyDialog.showModal(); });
  document.querySelector("#app-currency-close").addEventListener("click", () => currencyDialog.close());
  document.querySelector("#app-currency-filter-submit").addEventListener("click", () => { currencyPage = 1; renderCurrencies(); });
  currencyCode.addEventListener("change", () => { if (!chooseCurrency(currencyCode.value)) { currencyName.value = ""; exchangeRate.value = ""; calculateInvoice(); } });
  ["fob_fcy", "freight_fcy", "insurance_fcy", "other_costs_fcy"].forEach((key) => document.querySelector(`[data-app-field="${key}"]`).addEventListener("input", calculateInvoice));
  const deliveryTerm = document.querySelector('[data-app-field="delivery_term"]');
  if (deliveryTerm.value.includes(",")) deliveryTerm.value = deliveryTerm.value.split(",", 1)[0].trim();
  if (currencyCode.value) chooseCurrency(currencyCode.value.split(",", 1)[0].trim());
  else calculateInvoice();

  // --- Ghana HS tariff lookup ---
  const hsDialog = document.querySelector("#app-hs-dialog");
  const hsResults = document.querySelector("#app-hs-results");
  let hsPage = 1;
  const displayHsCode = (code) => code.length === 10 ? `${code.slice(0, 4)}.${code.slice(4, 6)}.${code.slice(6, 8)}.${code.slice(8, 10)}` : code;
  function hsCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value ?? "";
    row.append(cell);
  }
  async function searchHsCodes() {
    const length = document.querySelector('input[name="app-hs-length"]:checked').value;
    const params = new URLSearchParams({
      code: document.querySelector("#app-hs-filter-code").value.trim(),
      description: document.querySelector("#app-hs-filter-description").value.trim(),
      length,
      page: String(hsPage),
    });
    hsResults.innerHTML = '<tr><td class="empty-row" colspan="9">Searching...</td></tr>';
    try {
      const response = await fetch(`${window.appHsCodeSearchUrl}?${params}`, { headers: { Accept: "application/json" } });
      const data = await response.json();
      const resultRows = Array.isArray(data.results) ? data.results : [];
      hsResults.replaceChildren();
      if (!response.ok || !resultRows.length) hsResults.innerHTML = '<tr><td class="empty-row" colspan="9">No data found.</td></tr>';
      resultRows.forEach((result, index) => {
        const row = document.createElement("tr");
        row.tabIndex = 0;
        hsCell(row, (data.page - 1) * 10 + index + 1);
        hsCell(row, displayHsCode(result.code));
        hsCell(row, result.description);
        hsCell(row, result.prohibited);
        hsCell(row, result.quantity_unit);
        hsCell(row, result.import_duty);
        hsCell(row, result.import_vat);
        hsCell(row, result.nhil_rate);
        hsCell(row, result.supplementary_unit);
        row.addEventListener("click", () => {
          if (length !== "10") {
            document.querySelector("#app-hs-filter-code").value = result.code;
            document.querySelector('input[name="app-hs-length"][value="10"]').checked = true;
            hsPage = 1;
            searchHsCodes();
            return;
          }
          document.querySelector('[data-item-field="hs_code"]').value = result.full_code;
          document.querySelector('[data-item-field="hs_name"]').value = result.description;
          hsDialog.close();
        });
        row.addEventListener("keydown", (event) => { if (event.key === "Enter") row.click(); });
        hsResults.append(row);
      });
      window.drawDialogPager(document.querySelector("#app-hs-pagination"), { total: data.total || 0, page: data.page || 1, pageCount: data.page_count || 1, onPage: (page) => { hsPage = page; searchHsCodes(); } });
    } catch {
      hsResults.innerHTML = '<tr><td class="empty-row" colspan="9">The HS-code directory could not be loaded.</td></tr>';
    }
  }
  document.querySelector("#app-hs-search").addEventListener("click", () => { hsPage = 1; searchHsCodes(); hsDialog.showModal(); });
  document.querySelector("#app-hs-close").addEventListener("click", () => hsDialog.close());
  document.querySelector("#app-hs-filter-submit").addEventListener("click", () => { hsPage = 1; searchHsCodes(); });
  document.querySelectorAll('input[name="app-hs-length"]').forEach((radio) => radio.addEventListener("change", () => { hsPage = 1; searchHsCodes(); }));
  [document.querySelector("#app-hs-filter-code"), document.querySelector("#app-hs-filter-description")].forEach((input) => input.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); hsPage = 1; searchHsCodes(); } }));

  // --- Item list ---
  const rows = document.querySelector("#app-item-rows");
  let itemPage = 0;
  let items = Array.isArray(initial.items) ? initial.items.map((item) => ({ ...item })) : [];
  const numeric = (value) => { const parsed = Number(String(value).replace(/,/g, "")); return Number.isFinite(parsed) ? parsed : 0; };
  const ticked = new Set();
  function renderItems() {
    rows.replaceChildren();
    const pageCount = Math.max(1, Math.ceil(items.length / 10));
    itemPage = Math.min(itemPage, pageCount - 1);
    items.slice(itemPage * 10, itemPage * 10 + 10).forEach((item, index) => {
      const absoluteIndex = itemPage * 10 + index;
      const row = document.createElement("tr");
      const checkCell = document.createElement("td");
      const check = document.createElement("input");
      check.type = "checkbox";
      check.className = "app-item-check";
      check.checked = ticked.has(absoluteIndex);
      check.setAttribute("aria-label", `Select item ${absoluteIndex + 1}`);
      check.addEventListener("change", () => {
        if (check.checked) ticked.add(absoluteIndex); else ticked.delete(absoluteIndex);
        syncItemActions();
      });
      checkCell.append(check);
      row.append(checkCell);
      const numberCell = document.createElement("td");
      numberCell.className = "app-item-no";
      const numberLink = document.createElement("button");
      numberLink.type = "button";
      numberLink.className = "app-item-edit-link";
      numberLink.textContent = String(absoluteIndex + 1).padStart(4, "0");
      numberLink.setAttribute("aria-label", `Edit item ${absoluteIndex + 1}`);
      numberLink.addEventListener("click", () => openItemEditor(absoluteIndex));
      numberCell.append(numberLink);
      row.append(numberCell);
      ["hs_code", "description", "net_weight", "gross_weight", "price_fcy", "unit_fob_fcy"].forEach((key) => {
        const cell = document.createElement("td");
        cell.textContent = item[key] ?? "";
        row.append(cell);
      });
      rows.append(row);
    });
    updateTotals();
    syncItemActions();
    window.drawDialogPager(document.querySelector("#app-item-pagination"), {
      total: items.length, page: itemPage + 1, pageCount,
      onPage: (page) => { itemPage = page - 1; renderItems(); },
    });
  }
  function firstTicked() {
    return ticked.size ? Math.min(...ticked) : null;
  }
  function syncItemActions() {
    const hasSelection = ticked.size > 0;
    const deleteButton = document.querySelector("#app-item-delete");
    const duplicateButton = document.querySelector("#app-item-duplicate");
    if (deleteButton) deleteButton.disabled = !hasSelection;
    if (duplicateButton) duplicateButton.disabled = !hasSelection;
    const allCheck = document.querySelector("#app-item-check-all");
    if (allCheck) allCheck.checked = items.length > 0 && ticked.size === items.length;
  }
  function updateTotals() {
    const sum = (key) => items.reduce((total, item) => total + numeric(item[key]), 0);
    document.querySelector("#app-total-net").textContent = sum("net_weight").toFixed(2);
    document.querySelector("#app-total-gross").textContent = sum("gross_weight").toFixed(2);
    document.querySelector("#app-total-price").textContent = sum("price_fcy").toFixed(2);
    updateFobCheck();
  }
  function updateFobCheck() {
    const line = document.querySelector("#app-fob-check");
    if (!line) return;
    const itemsFob = items.reduce((total, item) => total + (numeric(item.fob_fcy) || numeric(item.price_fcy)), 0);
    const invoiceFob = numeric(document.querySelector('[data-app-field="fob_fcy"]').value);
    line.hidden = false;
    if (!items.length && !invoiceFob) { line.hidden = true; return; }
    if (Math.abs(itemsFob - invoiceFob) < 0.005) {
      line.className = "dialog-help app-fob-ok";
      line.textContent = `Items FOB total ${itemsFob.toFixed(2)} matches Invoice FOB FCY ${invoiceFob.toFixed(2)}.`;
    } else {
      line.className = "dialog-help app-fob-mismatch";
      line.textContent = `Items FOB total ${itemsFob.toFixed(2)} does not match Invoice FOB FCY ${invoiceFob.toFixed(2)} — check the Invoice tab.`;
    }
  }
  document.querySelector('[data-app-field="fob_fcy"]').addEventListener("input", updateFobCheck);
  function addItem(copyFrom) {
    const blank = { hs_code: "", hs_name: "", description: "", state_of_goods: "", quantity_unit: "KGM", quantity: "", supplementary_unit: "KGM", supplementary_quantity: "", package_unit: "KG", package_quantity: "", origin_country: "", gross_weight: "", net_weight: "", currency: "", exchange_rate: "", unit_fob_fcy: "", unit_fob_ncy: "", price_fcy: "", price_ncy: "", fob_fcy: "", fob_ncy: "", remarks: "" };
    items.push(copyFrom !== undefined ? { ...items[copyFrom] } : blank);
    itemPage = Math.floor((items.length - 1) / 10);
    renderItems();
  }
  const itemList = document.querySelector("#app-item-list");
  const itemEditor = document.querySelector("#app-item-editor");
  const itemStatus = document.querySelector("#app-item-status");
  const itemFields = [...document.querySelectorAll("[data-item-field]")];
  let itemFobAdjustmentPending = false;
  function remainingInvoiceFob() {
    const invoiceFob = moneyNumber(document.querySelector('[data-app-field="fob_fcy"]').value);
    const alreadyAllocated = items.reduce((total, item, index) => {
      if (index === editingIndex) return total;
      return total + (numeric(item.fob_fcy) || numeric(item.price_fcy));
    }, 0);
    return Math.max(0, invoiceFob - alreadyAllocated);
  }
  function calculateItem() {
    const rate = moneyNumber(document.querySelector('[data-item-field="exchange_rate"]').value);
    const quantity = moneyNumber(document.querySelector('[data-item-field="quantity"]').value);
    const unitField = document.querySelector('[data-item-field="unit_fob_fcy"]');
    let unitFob = moneyNumber(unitField.value);
    const remaining = remainingInvoiceFob();
    let price = quantity * unitFob;
    if (quantity > 0 && price > remaining + 0.005) {
      unitFob = Math.floor((remaining / quantity) * 1000000) / 1000000;
      price = Math.min(remaining, quantity * unitFob);
      unitField.value = unitFob.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 6, useGrouping: false });
      itemFobAdjustmentPending = true;
    }
    const fob = price;
    document.querySelector('[data-item-field="unit_fob_ncy"]').value = moneyText(unitFob * rate);
    document.querySelector('[data-item-field="price_ncy"]').value = moneyText(price * rate);
    document.querySelector('[data-item-field="price_fcy"]').value = moneyText(price);
    document.querySelector('[data-item-field="fob_fcy"]').value = moneyText(fob);
    document.querySelector('[data-item-field="fob_ncy"]').value = moneyText(fob * rate);
  }
  let editingIndex = null;
  function openItemEditor(editIndex = null) {
    editingIndex = editIndex;
    itemFobAdjustmentPending = false;
    itemFields.forEach((field) => { if (!field.matches("select")) field.value = ""; });
    const editing = editIndex !== null ? items[editIndex] : null;
    if (editing) {
      itemFields.forEach((field) => { field.value = editing[field.dataset.itemField] ?? ""; });
    } else {
      document.querySelector('[data-item-field="item_no"]').value = String(items.length + 1).padStart(4, "0");
    }
    const code = currencyCode.value;
    const rate = exchangeRate.value;
    if (!document.querySelector('[data-item-field="currency"]').value) {
      document.querySelector('[data-item-field="currency"]').value = code ? `${code}, ${currencyName.value}` : "";
    }
    if (!document.querySelector('[data-item-field="exchange_rate"]').value) {
      document.querySelector('[data-item-field="exchange_rate"]').value = rate;
    }
    document.querySelectorAll("[data-item-currency]").forEach((field) => { field.value = code; });
    calculateItem();
    itemStatus.hidden = true;
    itemList.hidden = true;
    itemEditor.hidden = false;
    document.querySelector("#app-item-save").textContent = editing ? "▣ Update Item" : "▣ Save Item";
  }
  function closeItemEditor() { editingIndex = null; itemEditor.hidden = true; itemList.hidden = false; }
  document.querySelector("#app-item-add").addEventListener("click", () => openItemEditor());
  document.querySelector("#app-item-back").addEventListener("click", closeItemEditor);
  ["quantity", "unit_fob_fcy"].forEach((key) => document.querySelector(`[data-item-field="${key}"]`).addEventListener("input", calculateItem));
  async function resolveTypedHsCode() {
    const field = document.querySelector('[data-item-field="hs_code"]');
    const digits = field.value.replace(/\D/g, "");
    if (!digits) return;
    const params = new URLSearchParams({ code: digits, description: "", length: "10", page: "1" });
    try {
      const response = await fetch(`${window.appHsCodeSearchUrl}?${params}`, { headers: { Accept: "application/json" } });
      const data = await response.json();
      const rows = Array.isArray(data.results) ? data.results : [];
      const match = rows.find((row) => row.code === digits) || (rows.length === 1 ? rows[0] : null);
      if (match) {
        field.value = match.code;
        document.querySelector('[data-item-field="hs_name"]').value = match.description;
      }
    } catch { /* leave the typed code as entered */ }
  }
  document.querySelector('[data-item-field="hs_code"]').addEventListener("focusout", resolveTypedHsCode);
  async function persistDraft() {
    if (window.appReadOnly) throw new Error("Submitted applications are view-only.");
    const data = await post(window.appSaveUrl, collectPayload());
    if (!appId) {
      appId = data.id;
      const url = new URL(location.href);
      url.searchParams.set("app", String(appId));
      history.replaceState(null, "", url);
    }
    document.querySelector("#app-no").value = data.application_no;
    return data;
  }
  document.querySelector("#app-item-save").addEventListener("click", async (event) => {
    const required = ["hs_code", "description", "state_of_goods", "quantity", "package_quantity", "origin_country", "gross_weight", "net_weight", "currency", "unit_fob_fcy", "price_fcy"];
    const missing = required.map((key) => document.querySelector(`[data-item-field="${key}"]`)).filter((field) => !field.value.trim());
    itemFields.forEach((field) => field.classList.toggle("ucr-field-invalid", missing.includes(field)));
    if (missing.length) {
      itemStatus.hidden = false;
      itemStatus.classList.add("ucr-status-error");
      itemStatus.textContent = `Complete the ${missing.length} highlighted required item field${missing.length === 1 ? "" : "s"}.`;
      window.alert(itemStatus.textContent);
      missing[0].focus();
      return;
    }
    calculateItem();
    const adjusted = itemFobAdjustmentPending;
    if (adjusted) {
      window.alert("The unit price and item fob are automatically changed because the total fob of the item exceeds the fob amount of invoice. Please check.");
    }
    const item = {};
    itemFields.forEach((field) => { item[field.dataset.itemField] = field.value; });
    const previousItems = items.map((entry) => ({ ...entry }));
    if (editingIndex !== null) {
      items[editingIndex] = item;
    } else {
      items.push(item);
      itemPage = Math.floor((items.length - 1) / 10);
    }
    renumberItems();
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const data = await persistDraft();
      renderItems();
      closeItemEditor();
      itemFobAdjustmentPending = false;
      window.alert(`Item saved successfully in application ${data.application_no}.`);
    } catch (error) {
      items = previousItems;
      itemStatus.hidden = false;
      itemStatus.classList.add("ucr-status-error");
      itemStatus.textContent = error.message;
      window.alert(`Item was not saved. ${error.message}`);
    } finally {
      button.disabled = false;
    }
  });
  function renumberItems() {
    items.forEach((item, index) => { item.item_no = String(index + 1).padStart(4, "0"); });
  }
  document.querySelector("#app-item-duplicate").addEventListener("click", () => {
    const source = firstTicked();
    if (source === null) return;
    const copy = { ...items[source] };
    items.push(copy);
    renumberItems();
    itemPage = Math.floor((items.length - 1) / 10);
    renderItems();
    persistDraft().catch((error) => window.alert(`Duplicated item was not saved. ${error.message}`));
  });
  document.querySelector("#app-item-delete").addEventListener("click", () => {
    if (!ticked.size) return;
    items = items.filter((_, index) => !ticked.has(index));
    ticked.clear();
    renumberItems();
    itemPage = 0;
    renderItems();
    persistDraft().catch((error) => window.alert(`Item deletion was not saved. ${error.message}`));
  });
  document.querySelector("#app-item-check-all").addEventListener("change", (event) => {
    ticked.clear();
    if (event.target.checked) items.forEach((_, index) => ticked.add(index));
    renderItems();
  });
  renderItems();
  // Select the requested tab only after item state exists. This matters when a
  // saved application is opened directly at #confirmation.
  const requestedTab = location.hash.slice(1);
  showTab(tabs.some((tab) => tab.dataset.appTab === requestedTab) ? requestedTab : "general");

  // --- Confirmation tab ---
  function fieldParts() {
    const parts = {};
    document.querySelectorAll("[data-app-field]").forEach((field) => {
      parts[field.dataset.appField] = field.value;
    });
    return parts;
  }
  function confirmationSection(title, entries) {
    const section = document.createElement("section");
    section.className = "app-confirm-section";
    const heading = document.createElement("h3");
    heading.textContent = title;
    const table = document.createElement("table");
    table.className = "app-confirm-detail-table";
    const body = document.createElement("tbody");
    entries.forEach(([label, value]) => {
      const row = document.createElement("tr");
      const headingCell = document.createElement("th");
      const valueCell = document.createElement("td");
      headingCell.scope = "row";
      headingCell.textContent = label;
      valueCell.textContent = value || "";
      row.append(headingCell, valueCell);
      body.append(row);
    });
    table.append(body);
    section.append(heading, table);
    return section;
  }
  function countryDisplay(code) {
    const clean = String(code || "").trim().toUpperCase();
    return clean ? `${clean}, ${countryCodes.get(clean) || ""}`.replace(/, $/, "") : "";
  }
  function renderConfirmation() {
    const parts = fieldParts();
    document.querySelectorAll("[data-confirm]").forEach((cell) => {
      const key = cell.dataset.confirm;
      const mdaGeneratedField = cell.closest("#app-mda-rows") && ["application", "process", "app-no", "submitted", "status"].includes(key);
      if (mdaGeneratedField) return;
      if (key === "app-no") cell.textContent = document.querySelector("#app-no").value;
      else if (key === "submitted") cell.textContent = window.appSubmittedAt || "";
      else if (key === "status") cell.textContent = window.appStatusText || "Draft";
      else if (key === "application" || key === "process") cell.textContent = "";
      else cell.textContent = parts[key] || "";
    });
    const container = document.querySelector("#app-confirm-sections");
    const partyEntries = (role, identityLabel) => [
      [identityLabel, parts[`${role}.${role === "importer" || role === "consignee" ? "code" : "name"}`]],
      ["Physical Country", countryDisplay(parts[`${role}.physical_country`])],
      ["Physical Address", parts[`${role}.physical_address`]],
      ["Postal Country", countryDisplay(parts[`${role}.postal_country`])],
      ["Tel. No.", parts[`${role}.tel`]], ["Fax No.", parts[`${role}.fax`]],
      ["E-Mail", parts[`${role}.email`]], ["Postal Address", parts[`${role}.postal_address`]],
      ["MDA Ref. No.", parts[`${role}.mda_ref`]], ["Sector Of Activity", parts[`${role}.sector`]],
      ["Warehouse", parts[`${role}.warehouse`]],
    ];
    const currency = String(parts.currency || "").split(",")[0].trim();
    const invoiceEntries = [
      ["Delivery Term", parts.delivery_term], ["Currency", parts.currency], ["Exchange Rate", parts.exchange_rate],
      [`FOB FCY${currency ? ` (${currency})` : ""}`, parts.fob_fcy], ["FOB NCY (GHS)", parts.fob_ncy],
      [`Freight FCY${currency ? ` (${currency})` : ""}`, parts.freight_fcy], ["Freight NCY (GHS)", parts.freight_ncy],
      [`Insurance FCY${currency ? ` (${currency})` : ""}`, parts.insurance_fcy], ["Insurance NCY (GHS)", parts.insurance_ncy],
      [`Other Costs FCY${currency ? ` (${currency})` : ""}`, parts.other_costs_fcy], ["Other Costs NCY (GHS)", parts.other_costs_ncy],
      [`Customs Value FCY${currency ? ` (${currency})` : ""}`, parts.customs_value_fcy], ["Customs Value NCY (GHS)", parts.customs_value_ncy],
    ];
    container.replaceChildren(
      confirmationSection("Reference Info.", [["Reference Info.", parts.reference_info]]),
      confirmationSection("Exporter", partyEntries("exporter", "Name")),
      confirmationSection("Consignor", partyEntries("consignor", "Name")),
      confirmationSection("Importer", partyEntries("importer", "Code")),
      confirmationSection("Consignee", partyEntries("consignee", "Code")),
      confirmationSection("Transport", [
        ["Means of Transport", parts.means_of_transport], ["Vessel Name", parts.vessel_name], ["Voyage No.", parts.voyage_no],
        ["Shipment Date", parts.shipment_date], ["Carrier", parts.carrier], ["Manifest No.", parts.manifest_no], ["BL/AWB No.", parts.bl_awb_no],
        ["Marks and Numbers", parts.marks_numbers], ["Port of Arrival", parts.port_arrival], ["Port of Departure", parts.port_departure],
        ["Customs Office", parts.customs_office], ["Freight Station", parts.freight_station], ["Inland Transport Co.", parts.inland_transport_co],
        ["Inland Transport Co. Ref. No.", parts.inland_transport_ref], ["Cargo Type", parts.cargo_type],
        ["Up to 20 feet", parts.containers_up_to_20], ["30 feet or more (30/35/40, etc.) feet", parts.containers_30_plus],
      ]),
      confirmationSection("Invoice Detail", invoiceEntries),
    );
    const itemSection = document.createElement("section");
    itemSection.className = "app-confirm-section";
    itemSection.innerHTML = '<h3>Item</h3><div class="cargo-table-wrap"><table class="app-confirm-items"><thead><tr><th>Item No.</th><th>HS</th><th>Item Description</th><th>Net Weight (KG)</th><th>Gross Weight (KG)</th><th>Item Price FCY</th><th>Unit FOB FCY</th></tr></thead><tbody></tbody></table></div>';
    const body = itemSection.querySelector("tbody");
    items.filter((item) => Object.values(item).some(Boolean)).forEach((item, index) => {
      const row = document.createElement("tr");
      [item.item_no || String(index + 1).padStart(4, "0"), item.hs_code, item.description, item.net_weight, item.gross_weight, item.price_fcy, item.unit_fob_fcy].forEach((value) => {
        const cell = document.createElement("td"); cell.textContent = value || ""; row.append(cell);
      });
      body.append(row);
    });
    if (!body.children.length) body.innerHTML = '<tr><td class="empty-row" colspan="7">No item data found.</td></tr>';
    container.append(itemSection);
  }

  // --- Save / Submit ---
  const status = document.querySelector("#app-status");
  function report(message, isError) {
    status.hidden = false;
    status.classList.toggle("ucr-status-error", Boolean(isError));
    status.textContent = message;
  }
  function collectPayload() {
    const parties = {};
    ["exporter", "consignor", "importer", "consignee"].forEach((role) => {
      parties[role] = {};
      document.querySelectorAll(`[data-app-field^="${role}."]`).forEach((field) => {
        parties[role][field.dataset.appField.split(".")[1]] = field.value;
      });
      const box = document.querySelector(`[data-app-same="${role}"]`);
      if (box) parties[role].same = box.checked;
    });
    const flat = {};
    document.querySelectorAll('[data-app-field]:not([data-app-field^="exporter."]):not([data-app-field^="consignor."]):not([data-app-field^="importer."]):not([data-app-field^="consignee."])').forEach((field) => {
      flat[field.dataset.appField] = field.value;
    });
    const payload = {
      app_id: appId,
      ucr_no: document.querySelector("#app-ucr").value,
      ...parties,
      ...flat,
      items: items.filter((item) => Object.values(item).some(Boolean)),
    };
    if (window.appMdaMode) {
      payload.approval_terms = document.querySelector("#app-approval-terms")?.checked || false;
      payload.approval_purpose = document.querySelector("#app-approval-purpose")?.value || "";
      payload.approval_remarks = document.querySelector("#app-approval-remarks")?.value || "";
      payload.additional_parties = approvalParties;
    }
    return payload;
  }
  async function post(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json", "X-CSRFToken": window.appCsrfToken || "" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "The simulator could not complete this request.");
    return data;
  }
  document.querySelector("#app-save").addEventListener("click", async (event) => {
    if (!validateGeneral()) {
      window.alert(status.textContent);
      return;
    }
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const data = await post(window.appSaveUrl, collectPayload());
      appId = data.id;
      if (!window.appSubmittedAt && !window.appMdaMode) {
        const url = new URL(location.href);
        url.searchParams.set("app", String(appId));
        history.replaceState(null, "", url);
      }
      document.querySelector("#app-no").value = data.application_no;
      report(`Application saved as ${data.application_no}.`);
      window.alert(`Saved successfully. Application ${data.application_no} is still a draft and has not been submitted.`);
    } catch (error) {
      report(error.message, true);
      window.alert(`Save failed. ${error.message}`);
    } finally {
      button.disabled = false;
    }
  });
  const submitButton = document.querySelector("#app-submit");
  if (submitButton) {
    submitButton.addEventListener("click", async () => {
      submitButton.disabled = true;
      try {
        const data = await post(window.appSubmitUrl, {});
        report(`${data.application_no} submitted — status ${data.status}.`);
        window.alert(`Submitted successfully. ${data.application_no} — status ${data.status}.`);
        window.location.reload();
      } catch (error) {
        report(error.message, true);
        window.alert(`Submit failed. ${error.message}`);
        submitButton.disabled = false;
      }
    });
  }
  if (window.appReadOnly) {
    document.querySelectorAll("[data-app-field], [data-app-same], #app-item-add, #app-item-duplicate, #app-item-delete").forEach((control) => { control.disabled = true; });
    document.querySelector("#app-save").disabled = true;
    report("This submitted application is open in view mode.");
  }
})();
