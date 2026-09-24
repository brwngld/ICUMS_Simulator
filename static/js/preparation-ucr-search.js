(() => {
  const dialog = document.querySelector('#ucr-reference-dialog');
  const openButton = document.querySelector('#preparation-ucr-search');
  const target = document.querySelector('#preparation-ucr');
  if (!dialog || !openButton || !target || !window.ucrReferenceSearchUrl) return;

  const results = dialog.querySelector('#ucr-reference-results');
  const numberInput = dialog.querySelector('#ucr-reference-number');
  const regimeInput = dialog.querySelector('#ucr-reference-regime');
  const exporterInput = dialog.querySelector('#ucr-reference-exporter');
  const importerInput = dialog.querySelector('#ucr-reference-importer');
  const emptyRow = '<tr><td class="empty-row" colspan="4">No data found.</td></tr>';

  function draw(resultsList) {
    results.innerHTML = resultsList.length
      ? resultsList.map((row) => `<tr><td class="cell-center ucr-pick-cell" data-ucr="${row.ucr_no}">${row.ucr_no}</td><td class="cell-center">${row.regime}</td><td class="cell-left">${row.exporter}</td><td class="cell-left">${row.importer}</td></tr>`).join("")
      : emptyRow;
  }

  async function run() {
    const params = new URLSearchParams();
    for (const [key, input] of [["number", numberInput], ["regime", regimeInput], ["exporter", exporterInput], ["importer", importerInput]]) {
      const value = input.value.trim();
      if (value) params.set(key, value);
    }
    try {
      const response = await fetch(`${window.ucrReferenceSearchUrl}?${params}`, { headers: { Accept: "application/json" } });
      const data = await response.json();
      draw(response.ok ? data.results : []);
    } catch {
      draw([]);
    }
  }

  openButton.addEventListener("click", () => {
    results.innerHTML = emptyRow;
    dialog.showModal();
    numberInput.focus();
  });
  dialog.querySelector('#ucr-reference-close').addEventListener('click', () => dialog.close());
  dialog.querySelector('#ucr-reference-reset').addEventListener('click', () => {
    [numberInput, exporterInput, importerInput].forEach((input) => { input.value = ""; });
    regimeInput.selectedIndex = 0;
    results.innerHTML = emptyRow;
  });
  dialog.querySelector('#ucr-reference-submit').addEventListener('click', run);
  numberInput.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); run(); } });
  results.addEventListener('click', (event) => {
    const cell = event.target.closest('td.ucr-pick-cell');
    if (!cell) return;
    target.value = cell.dataset.ucr;
    dialog.close();
    target.focus();
  });
})();
