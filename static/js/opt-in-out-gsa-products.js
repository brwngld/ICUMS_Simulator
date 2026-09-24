const gsaProducts = [
  ["Shopping Malls/Impex/Super Markets","22,800"],["Office equipment and Stationery (Large Scale)","4,560"],["Office equipment and Stationery (Small Scale)","2,280"],["Printing press equipment and accessories","2,280"],["Gaming Items","1,150"],["Solar Panels and Accessories","2,280"],["Cement Products","5,700"],["Iron Rods, Steel sheets, Steel coils","2,280"],["Roofing materials","2,280"],["Floor tiles","2,280"],
  ["Other Building Materials - Prefabricated structures, door locks, louvers, painting items accessories","2,280"],["Sanitary wares - WCs, Sinks, taps and accessories etc","2,280"],["Telecommunication Equipment and accessories","2,280"],["Mobile phones and accessories","2,280"],["Furniture","2,280"],["Industrial Machinery and accessories","5,700"],["Mining equipment/Items","5,700"],["Construction Equipment/items","5,700"],["Petroleum Exploration Equipment/Items","5,700"],["Weighing and other Measuring Instruments","1,140"],
  ["Pharmaceutical Products","3,420"],["Cosmetics / toiletry Products","2,280"],["Medical Devices","2,280"],["Tobacco Products","5,700"],["Food Products","2,280"],["Frozen Products","2,280"],["Chemicals & Allied Products","2,280"],["Plastic Granules","2,280"],["Plastic Products","2,280"],["Large Scale Automobile Dealers - New Vehicles (Vehicles, Spare Parts and Lubricants)","5,700"],
  ["Garages - Used Vehicles (Vehicles and Spare Parts)","2,280"],["Individual Vehicle imports","570"],["Vehicle Spare Parts only","1,710"],["Motor cycles, Bicycles and accessories","1,140"],["Petroleum Products - Petrol, Diesel, Kerosene and LPG","5,700"],["Engine Oil/Lubricants/ Gas Refrigerant","2,280"],["LPG Cylinders & Accessories","2,280"],["Fuel Additives","1,140"],["Water Purifying equipment /Items","2,280"],["Power Generators and accessories","2,280"],
  ["Electrical and Electronic Products","2,280"],["Electricals cables and accessories","2,280"],["Textiles and its raw materials","2,280"],["Arms and Ammunition","5,700"],["Pyrotechnic Products","2,280"],["Raw Materials for Agriculture - Fertilizer and Agrochemicals","1,140"],["Used products - Household items, clothing, bags and shoes","570"],["Farming implements - cutlasses, hoes, etc","570"],["Cooking and serving utensils","570"],["Other undefined products","570"],
  ["Re-labelling (Packaging) - Non-Compliance","2,736"],["Absence of Certificate of Conformity, CoC/Certificate of Analysis, CoA - Penalty","5,130"]
];

const gsaDialog = document.querySelector("#gsa-product-dialog");
const gsaList = document.querySelector("#gsa-product-list");
const gsaPagination = document.querySelector("#gsa-product-pagination");
const addProductButton = document.querySelector("#add-product-group");
let filteredGsaProducts = gsaProducts;
let gsaPage = 1;
let activeGsaRow = null;

function renderGsaProducts() {
  const pageCount = Math.max(1, Math.ceil(filteredGsaProducts.length / 10));
  gsaPage = Math.min(gsaPage, pageCount);
  gsaList.innerHTML = filteredGsaProducts.slice((gsaPage - 1) * 10, gsaPage * 10).map((entry) => {
    const number = gsaProducts.indexOf(entry) + 1;
    return `<tr data-name="${entry[0]}" data-fee="${entry[1]}"><td>${number}</td><td>${entry[0]}</td><td>${entry[1]}</td><td>GHS</td><td></td></tr>`;
  }).join("") || `<tr><td class="empty-row" colspan="5">No fictional product found.</td></tr>`;
  window.drawDialogPager(gsaPagination, { total: filteredGsaProducts.length, page: gsaPage, pageCount, onPage: (page) => { gsaPage = page; renderGsaProducts(); } });
}

function addGsaProductRow() {
  productRows.querySelector(".product-empty")?.remove();
  const number = productRows.children.length + 1;
  const row = document.createElement("tr");
  row.className = "gsa-product-row";
  row.innerHTML = `<td>${number}</td><td><div class="document-type-field"><input class="gsa-product-name" readonly aria-label="GSA Product Group ${number}"><button class="gsa-product-search" type="button" aria-label="Search GSA Product Group ${number}">⌕</button></div></td><td><input class="gsa-product-fee" readonly aria-label="Product Group Fee ${number}"></td><td><input value="GHS" readonly aria-label="Currency ${number}"></td><td><button class="document-delete-button" type="button">Delete</button></td>`;
  row.querySelector(".document-delete-button").addEventListener("click", () => { row.remove(); if (!productRows.children.length) addGsaProductRow(); });
  productRows.appendChild(row);
}

mda.addEventListener("change", () => {
  document.querySelector("#gsa-rule-note").hidden = mda.value !== "GSA";
  if (mda.value === "GSA") {
    productRows.innerHTML = "";
    addProductButton.hidden = false;
    addGsaProductRow();
  }
  else {
    addProductButton.hidden = false;
    productRows.innerHTML = `<tr class="product-empty"><td class="empty-row" colspan="5">No fictional data found.</td></tr>`;
  }
});

productRows.addEventListener("click", (event) => {
  const searchButton = event.target.closest(".gsa-product-search");
  if (!searchButton) return;
  activeGsaRow = searchButton.closest("tr");
  filteredGsaProducts = gsaProducts; gsaPage = 1; renderGsaProducts(); gsaDialog.showModal();
});
addProductButton.addEventListener("click", () => { if (mda.value === "GSA") addGsaProductRow(); });
document.querySelector("#filter-gsa-products").addEventListener("click", () => { const query = document.querySelector("#gsa-product-filter").value.trim().toLowerCase(); filteredGsaProducts = gsaProducts.filter(([name]) => name.toLowerCase().includes(query)); gsaPage = 1; renderGsaProducts(); });
gsaList.addEventListener("click", (event) => { const row = event.target.closest("tr[data-name]"); if (!row || !activeGsaRow) return; activeGsaRow.querySelector(".gsa-product-name").value = row.dataset.name; activeGsaRow.querySelector(".gsa-product-fee").value = row.dataset.fee; gsaDialog.close(); });
