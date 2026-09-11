const mda = document.querySelector("#opt-mda");
const branch = document.querySelector("#opt-branch");
const gfzaSearch = document.querySelector("#gfza-branch-search");
const branchMessage = document.querySelector("#branch-message");

mda.addEventListener("change", () => {
  branchMessage.hidden = true;
  if (mda.value === "GSA") {
    gfzaSearch.hidden = true;
    branch.hidden = false;
    branch.disabled = false;
    branch.innerHTML = `<option value="">-- Select One --</option><option value="AFO1">AFLAO</option><option value="CUHQ">CUSTOMS HEADQUARTERS</option><option value="ELU1">ELUBO</option><option value="KIA1">KIA</option><option value="KMS1">KUMASI</option><option value="TKD1">TAKORADI</option><option value="TMA1">TEMA</option>`;
  } else if (mda.value === "GFZA") {
    branch.hidden = true;
    branch.disabled = true;
    gfzaSearch.hidden = false;
  } else {
    gfzaSearch.hidden = true;
    branch.hidden = false;
    branch.disabled = true;
    branch.innerHTML = `<option value="">-- Select MDA first --</option>`;
  }
});

const productRows = document.querySelector("#product-group-rows");
let productCount = 0;
document.querySelector("#add-product-group").addEventListener("click", () => {
  if (mda.value === "GSA") return;
  productRows.querySelector(".product-empty")?.remove();
  productCount += 1;
  const row = document.createElement("tr");
  row.innerHTML = `<td>${productCount}</td><td><div class="document-type-field"><input aria-label="Product group code ${productCount}"><button type="button" aria-label="Search product group ${productCount}">⌕</button></div></td><td><input aria-label="Product group fee ${productCount}" type="number" min="0" step="0.01"></td><td><input aria-label="Currency ${productCount}" value="GHS" readonly></td><td><button class="document-delete-button" type="button">Delete</button></td>`;
  row.querySelector(".document-delete-button").addEventListener("click", () => {
    row.remove();
    if (!productRows.children.length) productRows.innerHTML = `<tr class="product-empty"><td class="empty-row" colspan="5">No fictional data found.</td></tr>`;
  });
  productRows.appendChild(row);
});

document.querySelector("#save-opt").addEventListener("click", () => {
  const message = document.querySelector("#opt-message");
  message.hidden = false;
  message.textContent = "Frontend preview saved for review only. No Opt In/Out request was submitted.";
});

document.querySelector("#submit-opt").addEventListener("click", () => {
  const products = [...document.querySelectorAll(".gsa-product-row")].map((row) => ({
    name: row.querySelector(".gsa-product-name").value,
    fee: row.querySelector(".gsa-product-fee").value,
  })).filter((product) => product.name && product.fee);
  if (mda.value !== "GSA" || !products.length) {
    const message = document.querySelector("#opt-message");
    message.hidden = false;
    message.textContent = "Select GSA and choose at least one Product Group before submitting.";
    return;
  }
  const record = {optNo: `OPTGSA-SIM-${Date.now().toString().slice(-8)}`, products};
  localStorage.setItem("icumsSimulatorOptRecord", JSON.stringify(record));
  window.location.href = document.querySelector("#submit-opt").dataset.detailUrl;
});
