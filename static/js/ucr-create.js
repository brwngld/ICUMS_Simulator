(() => {
  const regime = document.querySelector('#ucr-regime');
  const content = document.querySelector('.cargo-content');
  let selectedProvider = null;
  const rules = {
    EX: ['tin', 'name'], FO: ['tin', 'name'],
    IM: ['name', 'tin'], FI: ['name', 'tin'], TR: ['name', 'tin'],
    TN: ['name', 'name'],
  };
  function updateRegime() {
    const [exporter, importer] = rules[regime.value] || ['name', 'name'];
    [['exporter', exporter], ['importer', importer]].forEach(([role, kind]) => {
      document.querySelector(`#ucr-${role}-label`).innerHTML = `${kind === 'tin' ? 'TIN' : role[0].toUpperCase() + role.slice(1) + ' Name'} <span>*</span>`;
      document.querySelector(`[data-party-search="${role}"]`).hidden = kind !== 'tin';
      document.querySelector(`#ucr-${role}-identity`).placeholder = kind === 'tin' ? 'Enter TIN / NID, then search' : '';
      const matchedName = document.querySelector(`#ucr-${role}-name`);
      matchedName.hidden = kind !== 'tin';
      if (kind !== 'tin') matchedName.value = '';
    });
  }
  function resetForRegime() {
    content.querySelectorAll('input, textarea, select').forEach((field) => {
      if (field === regime || field.id === 'ucr-temp' || field.type === 'file') return;
      if (field.type === 'checkbox') field.checked = field.id === 'ucr-show-provider';
      else field.value = '';
    });
    document.querySelector('#ucr-provider').hidden = false;
    selectedProvider = null;
    document.querySelector('#document-rows').replaceChildren();
    requiredFields.forEach((entry) => markRequired(entry, false));
    status.hidden = true;
  }
  function setRegimeGate() {
    content.querySelectorAll('input, textarea, select, button').forEach((field) => {
      if (field !== regime && field.id !== 'ucr-save' && field.id !== 'ucr-submit' && field.id !== 'ucr-show-provider') field.disabled = !regime.value;
    });
  }
  regime.addEventListener('change', () => { resetForRegime(); updateRegime(); setRegimeGate(); loadAssignedProvider(); });
  updateRegime();
  document.querySelector('#ucr-show-provider').addEventListener('change', (event) => {
    document.querySelector('#ucr-provider').hidden = !event.target.checked;
  });

  const countryCodes = new Map(window.ucrCountryCodes || []);
  const countryDialog = document.querySelector('#ucr-country-dialog');
  let activeCountry = null;
  let countryPage = 0;
  let countryMatches = [...countryCodes];
  function setCountry(field, code) {
    const normalized = code.trim().toUpperCase();
    field.value = normalized;
    field.dispatchEvent(new Event('input', {bubbles: true}));
    document.querySelector(`[data-country-name-for="${field.id}"]`).value = countryCodes.get(normalized) || '';
  }
  function drawCountries() {
    const tbody = document.querySelector('#ucr-country-results');
    tbody.replaceChildren();
    countryMatches.slice(countryPage * 10, countryPage * 10 + 10).forEach(([code, name], index) => {
      const row = document.createElement('tr');
      [countryPage * 10 + index + 1, code, name, 'Country Code'].forEach((value) => {
        const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
      });
      row.tabIndex = 0;
      const choose = () => { setCountry(activeCountry, code); countryDialog.close(); };
      row.addEventListener('click', choose);
      row.addEventListener('keydown', (event) => { if (event.key === 'Enter') choose(); });
      tbody.append(row);
    });
    const pageCount = Math.max(1, Math.ceil(countryMatches.length / 10));
    window.drawDialogPager(document.querySelector('#ucr-country-pagination'), {
      total: countryMatches.length, page: countryPage + 1, pageCount,
      onPage: (page) => { countryPage = page - 1; drawCountries(); },
    });
  }
  function filterCountries() {
    const code = document.querySelector('#ucr-country-filter-code').value.trim().toUpperCase();
    const name = document.querySelector('#ucr-country-filter-name').value.trim().toLowerCase();
    countryMatches = [...countryCodes].filter(([key, value]) => key.includes(code) && value.toLowerCase().includes(name));
    countryPage = 0; drawCountries();
  }
  document.querySelectorAll('[data-country-search]').forEach((button) => button.addEventListener('click', () => {
    activeCountry = document.getElementById(button.dataset.countrySearch);
    document.querySelector('#ucr-country-filter-code').value = activeCountry.value.trim();
    document.querySelector('#ucr-country-filter-name').value = '';
    filterCountries(); countryDialog.showModal();
  }));
  document.querySelectorAll('[data-country-code]').forEach((field) => {
    field.addEventListener('change', () => setCountry(field, field.value));
    field.addEventListener('input', () => { document.querySelector(`[data-country-name-for="${field.id}"]`).value = ''; });
  });
  document.querySelector('#ucr-country-filter-submit').addEventListener('click', filterCountries);
  document.querySelector('#ucr-country-filter-code').addEventListener('input', filterCountries);
  document.querySelector('#ucr-country-filter-name').addEventListener('input', filterCountries);
  document.querySelector('#ucr-country-close').addEventListener('click', () => countryDialog.close());

  const dialog = document.querySelector('#ucr-party-dialog');
  const results = document.querySelector('#ucr-party-results');
  const errorDialog = document.querySelector('#ucr-lookup-error');
  let activeRole = null;
  let matches = [];
  function showError(message) {
    document.querySelector('#ucr-error-message').textContent = message;
    errorDialog.showModal();
  }
  function drawResults() {
    results.replaceChildren();
    matches.forEach((record, index) => {
      const row = document.createElement('tr');
      const select = document.createElement('td');
      const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'ucr-party-choice'; radio.value = String(index);
      if (index === 0) radio.checked = true;
      select.append(radio); row.append(select);
      [record.code, record.description, record.name].forEach((value) => { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); });
      row.addEventListener('click', () => {
        radio.checked = true;
        chooseParty();
      });
      results.append(row);
    });
  }
  function chooseParty() {
    const selected = results.querySelector('input:checked')?.value;
    const record = matches[Number(selected)];
    if (!record || !activeRole) return;
    document.querySelector(`#ucr-${activeRole}-identity`).value = record.code;
    document.querySelector(`#ucr-${activeRole}-address`).value = record.address;
    const nameOutput = document.querySelector(`#ucr-${activeRole}-name`);
    nameOutput.value = record.name;
    dialog.close();
    document.querySelectorAll(`#ucr-${activeRole} .ucr-field-invalid`).forEach((field) => {
      if (field.value.trim()) field.dispatchEvent(new Event('input', {bubbles: true}));
    });
  }
  document.querySelectorAll('[data-party-search]').forEach((button) => button.addEventListener('click', async () => {
    activeRole = button.dataset.partySearch;
    const code = document.querySelector(`#ucr-${activeRole}-identity`).value.trim().toUpperCase();
    if (code.length < 11) {
      showError('The code entered is an invalid code.( input at least 11 characters)');
      return;
    }
    try {
      const response = await fetch(`${window.ucrStakeholderLookupUrl}?code=${encodeURIComponent(code)}`, {headers: {'Accept': 'application/json'}});
      const data = await response.json();
      if (!response.ok) { showError(data.error); return; }
      matches = data.results;
      drawResults();
      dialog.showModal();
    } catch {
      showError('The training directory could not be reached. Please try again.');
    }
  }));
  document.querySelector('#ucr-party-choose').addEventListener('click', chooseParty);
  document.querySelector('#ucr-party-close').addEventListener('click', () => dialog.close());
  document.querySelector('#ucr-error-close').addEventListener('click', () => errorDialog.close());
  document.querySelector('#ucr-error-ok').addEventListener('click', () => errorDialog.close());

  async function loadAssignedProvider() {
    try {
      const response = await fetch(window.ucrProviderLookupUrl, {headers: {'Accept': 'application/json'}});
      if (!response.ok) return;
      const data = await response.json();
      selectedProvider = data;
      document.querySelector('#ucr-declarant').value = data.declarant_code;
      document.querySelector('#ucr-provider-code').value = `${data.tin_code}, ${data.name}`;
      setCountry(document.querySelector('#ucr-provider-country'), data.country_code);
      document.querySelector('#ucr-provider-address').value = data.address;
      document.querySelector('#ucr-provider-contact').value = data.contact_name;
      document.querySelector('#ucr-provider-phone').value = data.phone;
      document.querySelector('#ucr-provider-email').value = data.email;
      document.querySelector('#ucr-provider-email-2').value = data.email_2 || '';
      document.querySelectorAll('#ucr-provider .ucr-field-invalid').forEach((field) => {
        if (field.value.trim()) field.dispatchEvent(new Event('input', {bubbles: true}));
      });
    } catch { /* no assigned provider yet; the learner can fill the panel manually */ }
  }
  const initialDraft = window.ucrInitialDraft || null;
  if (!initialDraft) loadAssignedProvider();
  function populateFromDeclarant(checkbox) {
    if (!checkbox.checked) return;
    if (!selectedProvider || document.querySelector('#ucr-provider').hidden) {
      checkbox.checked = false;
      showError('No service provider is assigned to your account yet.');
      return;
    }
    const role = checkbox.closest('.ucr-party').id.replace('ucr-', '');
    const isTin = !document.querySelector(`[data-party-search="${role}"]`).hidden;
    document.querySelector(`#ucr-${role}-identity`).value = isTin ? selectedProvider.tin_code : selectedProvider.name;
    document.querySelector(`#ucr-${role}-name`).value = isTin ? selectedProvider.name : '';
    setCountry(document.querySelector(`#ucr-${role}-country`), document.querySelector('#ucr-provider-country').value);
    document.querySelector(`#ucr-${role}-address`).value = document.querySelector('#ucr-provider-address').value;
    document.querySelector(`#ucr-${role}-phone`).value = document.querySelector('#ucr-provider-phone').value;
    document.querySelector(`#ucr-${role}-contact`).value = document.querySelector('#ucr-provider-contact').value;
    document.querySelector(`#ucr-${role}-contact-no`).value = document.querySelector('#ucr-provider-phone').value;
    document.querySelector(`#ucr-${role}-designation`).value = selectedProvider.contact_designation || '';
    document.querySelectorAll(`#ucr-${role} .ucr-field-invalid`).forEach((field) => {
      if (field.value.trim()) field.dispatchEvent(new Event('input', {bubbles: true}));
    });
  }
  document.querySelectorAll('[data-same-declarant]').forEach((checkbox) => checkbox.addEventListener('change', () => populateFromDeclarant(checkbox)));

  const requiredFields = [...document.querySelectorAll('#main-content .summary-grid label[for]')]
    .filter((label) => label.querySelector('span')?.textContent.trim() === '*')
    .map((label) => ({label, field: document.getElementById(label.htmlFor)}))
    .filter(({field}) => field);
  const status = document.querySelector('#ucr-status');
  function markRequired({label, field}, invalid) {
    field.classList.toggle('ucr-field-invalid', invalid);
    label.classList.toggle('ucr-label-invalid', invalid);
    if (invalid) field.setAttribute('aria-invalid', 'true');
    else field.removeAttribute('aria-invalid');
  }
  function isVisibleRequired({field}) {
    return !field.closest('[hidden]');
  }
  document.querySelector('#main-content').addEventListener('input', (event) => {
    const entry = requiredFields.find(({field}) => field === event.target);
    if (entry && event.target.value.trim()) markRequired(entry, false);
  });
  document.querySelector('#main-content').addEventListener('change', (event) => {
    const entry = requiredFields.find(({field}) => field === event.target);
    if (entry && event.target.value.trim()) markRequired(entry, false);
  });

  const rows = document.querySelector('#document-rows');
  function renumber() { [...rows.children].forEach((row, index) => { row.querySelector('[data-row-number]').textContent = index + 1; }); }
  function renderAttachment(row, attachment) {
    const cell = row.querySelector('.document-file-cell');
    if (!cell || !attachment || !attachment.url) return;
    const link = document.createElement('a');
    link.href = attachment.url;
    link.textContent = attachment.name;
    cell.replaceChildren(link);
  }
  function addDocument(data = null) {
    const row = document.createElement('tr');
    row.innerHTML = '<td data-row-number></td><td><div class="document-type-field"><input type="text" data-document-code aria-label="Document code" autocomplete="off"><button class="document-type-search" type="button" aria-label="Search document type">⌕</button><input type="text" data-document-name aria-label="Document name" readonly></div></td><td><input type="text" aria-label="Reference number"></td><td class="document-file-cell"><input type="file" aria-label="Attached file"></td><td><button class="document-delete-button document-row-delete" type="button">Del</button></td>';
    row.querySelector('.document-row-delete').addEventListener('click', () => { row.remove(); renumber(); });
    rows.append(row);
    renumber();
    if (data && data.attachment) renderAttachment(row, data.attachment);
    if (data) {
      row.querySelector('[data-document-code]').value = data.code || '';
      row.querySelector('[data-document-name]').value = data.name || '';
      row.querySelector('td:nth-child(3) input').value = data.reference || '';
    }
  }
  document.querySelector('#add-document').addEventListener('click', () => {
    addDocument();
    rows.querySelector('tr:last-child input[data-document-code]')?.focus();
  });
  if (initialDraft) {
    regime.value = initialDraft.regime;
    updateRegime();
    document.querySelector('#ucr-temp').value = initialDraft.temp_no;
    document.querySelector('#ucr-submit').disabled = false;
    document.querySelector('#ucr-show-provider').checked = initialDraft.show_provider;
    document.querySelector('#ucr-provider').hidden = !initialDraft.show_provider;
    const provider = initialDraft.provider;
    selectedProvider = {tin_code: provider.code, name: provider.name, contact_designation: ''};
    document.querySelector('#ucr-declarant').value = provider.declarant_code;
    document.querySelector('#ucr-provider-code').value = `${provider.code}, ${provider.name}`;
    setCountry(document.querySelector('#ucr-provider-country'), provider.country);
    [['address', 'address'], ['contact', 'contact'], ['phone', 'phone'], ['email', 'email'], ['email-2', 'email_2']].forEach(([id, key]) => { document.querySelector(`#ucr-provider-${id}`).value = provider[key] || ''; });
    ['exporter', 'importer'].forEach((role) => {
      const data = initialDraft[role];
      [['identity', 'identity'], ['name', 'name'], ['address', 'address'], ['phone', 'phone'], ['fax', 'fax'], ['contact', 'contact'], ['contact-no', 'contact_no'], ['designation', 'designation']].forEach(([id, key]) => { document.querySelector(`#ucr-${role}-${id}`).value = data[key] || ''; });
      setCountry(document.querySelector(`#ucr-${role}-country`), data.country);
    });
    const consignment = initialDraft.consignment;
    [['goods', 'goods'], ['mode', 'mode'], ['reference', 'reference'], ['email', 'email']].forEach(([id, key]) => { document.querySelector(`#ucr-${id}`).value = consignment[key] || ''; });
    setCountry(document.querySelector('#ucr-origin'), consignment.origin);
    setCountry(document.querySelector('#ucr-destination'), consignment.destination);
    (initialDraft.documents || []).forEach((document, index) => {
      addDocument({...document, attachment: (initialDraft.attachments || []).find((entry) => entry.row_index === index)});
    });
  }

  const saveButton = document.querySelector('#ucr-save');
  const submitButton = document.querySelector('#ucr-submit');
  let draftId = new URLSearchParams(location.search).get('draft');
  draftId = draftId && /^\d+$/.test(draftId) ? Number(draftId) : null;
  function collectUcrPayload() {
    const value = (selector) => (document.querySelector(selector)?.value || '').trim();
    const providerCodeField = value('#ucr-provider-code');
    const [providerCode, ...providerNameParts] = providerCodeField.split(',');
    const party = (role) => ({
      identity: value(`#ucr-${role}-identity`),
      name: value(`#ucr-${role}-name`) || value(`#ucr-${role}-identity`),
      country: value(`#ucr-${role}-country`),
      address: value(`#ucr-${role}-address`),
      phone: value(`#ucr-${role}-phone`),
      fax: value(`#ucr-${role}-fax`),
      contact: value(`#ucr-${role}-contact`),
      contact_no: value(`#ucr-${role}-contact-no`),
      designation: value(`#ucr-${role}-designation`),
    });
    const documents = [...rows.querySelectorAll('tr')].map((row) => ({
      code: row.querySelector('[data-document-code]').value.trim(),
      name: row.querySelector('[data-document-name]').value.trim(),
      reference: row.querySelector('td:nth-child(3) input').value.trim(),
    })).filter((entry) => entry.code || entry.reference);
    return {
      draft_id: draftId,
      regime: regime.value,
      show_provider: document.querySelector('#ucr-show-provider').checked,
      provider: {
        declarant_code: value('#ucr-declarant'),
        code: providerCode.trim(),
        name: providerNameParts.join(',').trim(),
        country: value('#ucr-provider-country'),
        address: value('#ucr-provider-address'),
        contact: value('#ucr-provider-contact'),
        phone: value('#ucr-provider-phone'),
        email: value('#ucr-provider-email'),
        email_2: value('#ucr-provider-email-2'),
      },
      exporter: party('exporter'),
      importer: party('importer'),
      consignment: {
        goods: value('#ucr-goods'),
        origin: value('#ucr-origin'),
        destination: value('#ucr-destination'),
        mode: value('#ucr-mode'),
        reference: value('#ucr-reference'),
        email: value('#ucr-email'),
      },
      documents,
    };
  }
  async function postUcr(url, payload) {
    const allRows = [...rows.querySelectorAll('tr')];
    const missingCode = allRows.some((row) => {
      const input = row.querySelector('input[type=file]');
      return input && input.files[0] && !row.querySelector('[data-document-code]').value.trim() && !row.querySelector('td:nth-child(3) input').value.trim();
    });
    if (missingCode) throw new Error('Enter a document code or reference number for each attached file.');
    const form = new FormData();
    form.append('payload', JSON.stringify(payload));
    allRows.filter((row) => row.querySelector('[data-document-code]').value.trim() || row.querySelector('td:nth-child(3) input').value.trim()).forEach((row, index) => {
      const file = row.querySelector('input[type=file]')?.files[0];
      if (file) form.append(`file_${index}`, file);
    });
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Accept': 'application/json', 'X-CSRFToken': window.ucrCsrfToken || '' },
      body: form,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.error || 'The simulator could not complete this request.');
      error.fieldErrors = data.errors || null;
      throw error;
    }
    return data;
  }
  function applyAttachments(data) {
    const attachments = data.attachments || [];
    if (!attachments.length) return;
    const indexedRows = [...rows.querySelectorAll('tr')].filter((row) => row.querySelector('[data-document-code]').value.trim() || row.querySelector('td:nth-child(3) input').value.trim());
    attachments.forEach((attachment) => {
      const row = indexedRows[attachment.row_index];
      if (row) renderAttachment(row, attachment);
    });
  }
  function reportStatus(message, isError) {
    status.hidden = false;
    status.classList.toggle('ucr-status-error', Boolean(isError));
    status.textContent = message;
  }
  function reportFieldErrors(errors) {
    const count = Object.keys(errors).length;
    reportStatus(`Correct ${count} highlighted field${count === 1 ? '' : 's'} before saving.`, true);
    const fieldMap = {
      'regime': regime,
      'provider.country': document.querySelector('#ucr-provider-country'),
      'provider.address': document.querySelector('#ucr-provider-address'),
      'provider.contact': document.querySelector('#ucr-provider-contact'),
      'provider.phone': document.querySelector('#ucr-provider-phone'),
      'provider.email': document.querySelector('#ucr-provider-email'),
      'provider.email_2': document.querySelector('#ucr-provider-email-2'),
    };
    ['exporter', 'importer'].forEach((role) => {
      ['identity', 'name', 'country', 'address', 'phone', 'contact', 'contact_no', 'designation'].forEach((key) => {
        fieldMap[`${role}.${key}`] = document.querySelector(`#ucr-${role}-${key === 'contact_no' ? 'contact-no' : key}`);
      });
    });
    Object.entries(errors).forEach(([key]) => { if (fieldMap[key]) fieldMap[key].focus(); });
  }
  saveButton.addEventListener('click', async () => {
    const missing = requiredFields.filter((entry) => {
      if (!regime.value) return entry.field === regime;
      return isVisibleRequired(entry) && (!entry.field.value.trim() || (entry.field.hasAttribute('data-country-code') && !countryCodes.has(entry.field.value.trim().toUpperCase())));
    });
    requiredFields.forEach((entry) => markRequired(entry, missing.includes(entry)));
    if (missing.length) {
      reportStatus(`Complete or correct the ${missing.length} highlighted required field${missing.length === 1 ? '' : 's'} before saving.`, true);
      missing[0].field.focus();
      return;
    }
    saveButton.disabled = true;
    try {
      const data = await postUcr(window.ucrSaveUrl, collectUcrPayload());
      if (!draftId && data.id) {
        draftId = data.id;
        const url = new URL(location.href);
        url.searchParams.set('draft', String(draftId));
        history.replaceState(null, '', url);
      }
      document.querySelector('#ucr-temp').value = data.temp_no;
      applyAttachments(data);
      submitButton.disabled = false;
      reportStatus(`Draft saved as ${data.temp_no}. Select Submit to generate the final UCR number.`);
    } catch (error) {
      if (error.fieldErrors) reportFieldErrors(error.fieldErrors);
      else reportStatus(error.message, true);
    } finally {
      saveButton.disabled = false;
    }
  });
  submitButton.addEventListener('click', async () => {
    if (submitButton.disabled) return;
    submitButton.disabled = true;
    try {
      const data = await postUcr(window.ucrSubmitUrl, collectUcrPayload());
      document.querySelector('#ucr-temp').value = data.ucr_no;
      applyAttachments(data);
      saveButton.disabled = true;
      reportStatus(`Submitted successfully. UCR No.: ${data.ucr_no}`);
      if (data.detail_url) setTimeout(() => { window.location.href = data.detail_url; }, 1500);
    } catch (error) {
      if (error.fieldErrors) reportFieldErrors(error.fieldErrors);
      else reportStatus(error.message, true);
      if (!saveButton.disabled) submitButton.disabled = false;
    }
  });
  setRegimeGate();
})();
