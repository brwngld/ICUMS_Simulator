let activeDocumentTypeInput = null;
const codeDialog = document.querySelector("#document-code-dialog");

const documentRows = document.querySelector("#document-rows");
const documentCodes = new Map(
  [...document.querySelectorAll("#document-code-list tr[data-code]")].map((row) => [
    row.dataset.code.trim().toUpperCase(), row.dataset.name,
  ]),
);

function documentCodeField(target) {
  if (!(target instanceof HTMLInputElement)) return null;
  if (!target.matches('[data-document-code], .document-type-field input:first-child')) return null;
  const nameInput = target.parentElement.querySelector('[data-document-name], input[readonly]');
  return nameInput ? { codeInput: target, nameInput } : null;
}

function fillDocumentName(target) {
  const fields = documentCodeField(target);
  if (!fields) return;
  const code = fields.codeInput.value.trim().toUpperCase();
  fields.nameInput.value = documentCodes.get(code) || "";
  if (fields.nameInput.value) fields.codeInput.value = code;
}

// Delegation keeps the same behaviour for rows added later and for other tables
// that use data-document-code and data-document-name.
document.addEventListener("input", (event) => {
  const fields = documentCodeField(event.target);
  if (fields) fields.nameInput.value = "";
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Tab") fillDocumentName(event.target);
});
document.addEventListener("focusout", (event) => fillDocumentName(event.target));

documentRows.addEventListener("click", (event) => {
  const searchButton = event.target.closest(".document-type-search");
  if (!searchButton) return;
  activeDocumentTypeInput = searchButton.previousElementSibling;
  codeDialog.showModal();
});

const documentPager = document.querySelector("#document-code-pagination");
const allDocumentRows = [...document.querySelectorAll("#document-code-list tr[data-code]")];
let documentPage = 1;
function renderDocumentCodePage() {
  const code = document.querySelector("#document-code-filter").value.trim().toLowerCase();
  const name = document.querySelector("#document-name-filter").value.trim().toLowerCase();
  const visible = allDocumentRows.filter((row) => row.dataset.code.toLowerCase().includes(code) && row.dataset.name.toLowerCase().includes(name));
  const pageCount = Math.max(1, Math.ceil(visible.length / 10));
  documentPage = Math.min(documentPage, pageCount);
  const shown = new Set(visible.slice((documentPage - 1) * 10, documentPage * 10));
  allDocumentRows.forEach((row) => { row.hidden = !shown.has(row); });
  window.drawDialogPager(documentPager, { total: visible.length, page: documentPage, pageCount, onPage: (page) => { documentPage = page; renderDocumentCodePage(); } });
}
function filterDocumentCodes() { documentPage = 1; renderDocumentCodePage(); }
document.querySelector("#filter-document-codes").addEventListener("click", filterDocumentCodes);
document.querySelector("#document-code-filter").addEventListener("input", filterDocumentCodes);
document.querySelector("#document-name-filter").addEventListener("input", filterDocumentCodes);
renderDocumentCodePage();

document.querySelector("#document-code-list").addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-code]");
  if (!row || !activeDocumentTypeInput) return;
  const documentNameInput = activeDocumentTypeInput.parentElement.querySelector('[data-document-name], input[readonly]');
  activeDocumentTypeInput.value = documentNameInput ? row.dataset.code : `${row.dataset.code} — ${row.dataset.name}`;
  if (documentNameInput) documentNameInput.value = row.dataset.name;
  codeDialog.close();
  activeDocumentTypeInput.focus();
});


