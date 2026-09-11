let activeDocumentTypeInput = null;
const codeDialog = document.querySelector("#document-code-dialog");

document.querySelector("#document-rows").addEventListener("click", (event) => {
  const searchButton = event.target.closest(".document-type-search");
  if (!searchButton) return;
  activeDocumentTypeInput = searchButton.previousElementSibling;
  codeDialog.showModal();
});

document.querySelector("#filter-document-codes").addEventListener("click", () => {
  const code = document.querySelector("#document-code-filter").value.trim().toLowerCase();
  const name = document.querySelector("#document-name-filter").value.trim().toLowerCase();
  document.querySelectorAll("#document-code-list tr").forEach((row) => {
    row.hidden = !(row.dataset.code.toLowerCase().includes(code) && row.dataset.name.toLowerCase().includes(name));
  });
});

document.querySelector("#document-code-list").addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-code]");
  if (!row || !activeDocumentTypeInput) return;
  activeDocumentTypeInput.value = `${row.dataset.code} — ${row.dataset.name}`;
  codeDialog.close();
  activeDocumentTypeInput.focus();
});

document.querySelector(".code-pagination").addEventListener("click", (event) => {
  const button = event.target.closest("[data-code-page]");
  if (!button) return;
  const page = button.dataset.codePage;
  document.querySelectorAll("#document-code-list tr").forEach((row) => {
    row.hidden = (row.dataset.page || "1") !== page;
  });
  document.querySelectorAll("[data-code-page]").forEach((pageButton) => {
    if (pageButton === button) pageButton.setAttribute("aria-current", "page");
    else pageButton.removeAttribute("aria-current");
  });
});
