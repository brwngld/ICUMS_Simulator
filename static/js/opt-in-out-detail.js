const fallbackRecord = {optNo:"OPTGSA-SIM-00028158",products:[{name:"Food Products",fee:"2,280"}]};
const optRecord = JSON.parse(localStorage.getItem("icumsSimulatorOptRecord") || "null") || fallbackRecord;
document.querySelector("#detail-opt-no").value = optRecord.optNo;
const detailProducts = document.querySelector("#detail-products");
detailProducts.innerHTML = optRecord.products.map((product,index) => `<tr><td>${index+1}</td><td>${product.name}</td><td>${product.fee}</td><td>GHS</td><td>${product.fee}</td><td>SU</td><td></td></tr>`).join("");
document.querySelector("#payment-bill").addEventListener("click", () => {
  document.querySelector("#bill-products").innerHTML = optRecord.products.map((product,index) => `<tr><td>${index+1}</td><td>${product.name}</td><td>${product.fee}</td></tr>`).join("");
  const highest = Math.max(...optRecord.products.map(product => Number(product.fee.replaceAll(",","")) || 0));
  document.querySelector("#bill-total").textContent = highest.toLocaleString("en-GH", {minimumFractionDigits:2,maximumFractionDigits:2});
  document.querySelector("#payment-dialog").showModal();
});
