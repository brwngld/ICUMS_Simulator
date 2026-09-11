const preparationRecords = [
  ["SIM-CD-0790708","SIM-UCR-2600627850","DOWELL INTERNATIONAL TRADING LTD","SIM-IMP-001, FELABROK ENTERPRISE","07/09/2026 15:01:56"],
  ["SIM-CD-0707654","SIM-UCR-2600626027","JKB LOGISTICS LTD","SIM-IMP-002, HAYFORD ESHUN","07/09/2026 10:13:10"],
  ["SIM-CD-0705709","SIM-UCR-2600624121","YIWU PENGDA LIMITED","SIM-IMP-003, LUCY ADOM","04/09/2026 15:14:11"],
  ["SIM-CD-0695290","SIM-UCR-2600614996","HUBEI ZHONGBAO PROTECTIVE PRODUCTS CO., LTD.","SIM-IMP-004, COSMIST ENTERPRISE","02/09/2026 08:07:05"],
  ["SIM-CD-0693884","SIM-UCR-2600613876","SHREE LLC","SIM-IMP-005, OXFORD PAINTS LTD","01/09/2026 15:36:41"],
  ["SIM-CD-0692790","SIM-UCR-2600613040","FORREST FRESH FOOD LTD","SIM-IMP-006, EARLYMAN ENTERPRISE","01/09/2026 13:15:45"],
  ["SIM-CD-0690748","SIM-UCR-2600611377","GUANGDONG MEDICAL TECHNOLOGY CO., LTD.","SIM-IMP-007, CROWN HEALTHCARE LTD","01/09/2026 06:34:53"]
];
const results = document.querySelector("#preparation-results");
document.querySelector("#search-preparation").addEventListener("click", () => {
  results.innerHTML = preparationRecords.map((row,index) => `<tr><td>${index+1}</td><td><a class="ucr-result-link" href="#">${row[0]}</a></td><td>${row[1]}</td><td>${row[2]}</td><td>${row[3]}</td><td>${row[4]}</td></tr>`).join("");
  document.querySelector("#preparation-total").textContent = `Total: ${preparationRecords.length}`;
});
document.querySelector("#reset-preparation-search").addEventListener("click", () => { document.querySelectorAll("#main-content input").forEach(input => { if (input.type !== "date") input.value = ""; }); results.innerHTML = `<tr><td class="empty-row" colspan="6">No fictional data found.</td></tr>`; document.querySelector("#preparation-total").textContent = "Total: 0"; });
