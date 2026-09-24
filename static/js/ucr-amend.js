(() => {
  const rows = document.querySelector('#document-rows');
  const form = document.querySelector('#ucr-amend-form');
  if (!rows || !form) return;

  function renumber() {
    [...rows.children].forEach((row, index) => {
      row.querySelector('[data-row-number]').textContent = index + 1;
      row.querySelector('input[type="file"]').name = `file_${index}`;
    });
  }
  function addDocument() {
    const row = document.createElement('tr');
    row.innerHTML = '<td data-row-number></td><td><div class="document-type-field"><input type="text" data-document-code aria-label="Document code" autocomplete="off"><button class="document-type-search" type="button" aria-label="Search document type">⌕</button><input type="text" data-document-name aria-label="Document name" readonly></div></td><td><input type="text" aria-label="Reference number"></td><td><input type="file" aria-label="Attached file" form="ucr-amend-form"></td><td><button class="document-delete-button" type="button">Del</button></td>';
    row.querySelector('.document-delete-button').addEventListener('click', () => { row.remove(); renumber(); });
    rows.append(row); renumber();
  }
  document.querySelector('#add-document').addEventListener('click', addDocument);

  form.addEventListener('submit', () => {
    const documents = [...rows.children].map((row) => ({
      code: row.querySelector('[data-document-code]').value.trim(),
      name: row.querySelector('[data-document-name]').value.trim(),
      reference: row.querySelector('td:nth-child(3) input').value.trim(),
    })).filter((entry) => entry.code || entry.reference);
    document.querySelector('#amend-new-documents').value = JSON.stringify(documents);
  });
})();
