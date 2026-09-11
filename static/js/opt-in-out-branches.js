const mdaBranches = [
  ["AFO1","CEPS AFLAO"],["AGA1","AGOTIME AFEGAME CUSTOMS BORDER POST"],["AKA1","AKANU"],["AKO1","AKIN ODA CUSTOMS POST"],["BAT1","BATUME JUNCTION CUSTOMS POST"],["BBP1","BREBRE (YARO CAMP) BORDER POST"],["BDB9","BOST DEPOT - BUIPE"],["BLC1","BOLE CHACHE CUSTOMS BORDER POST"],["BLG1","GRA (CUSTOMS) BOLGATANGA COLLECTION"],["BLG9","BOLGATANGA BOST"],
  ["BOL1","BOLE CUSTOMS BORDER POST"],["BPG1","BUNKPURUGU CUSTOMS BORDER POST"],["CUHQ","GRA - CUSTOMS HEADQUARTERS"],["DAD1","DADIESO CUSTOMS POST"],["DAM1","DAMBAI COLLECTION"],["DBL1","DABALA JUNCTION"],["DMG1","GRA CUSTOMS DAMONGO COLLECTION"],["ELU1","CEPS ELUBO"],["GKM1","GONOKROM"],["HAF1","HALF ASSINI CUSTOMS POST"],
  ["HAM1","HAMILE"],["HAV1","AVE-HAVI CUSTOMS POST"],["HOC1","GRA (CUSTOMS) HO COLLECTION"],["HON1","HONUTA CUSTOMS BORDER POST"],["ICUM","ICUMS - GCMS STOCK MIGRATION"],["JMT1","CEPS JAMES TOWN"],["JWP1","JEHWI WHARF CUSTOMS POST"],["KBK1","KOFI-BADUKROM BORDER POST"],["KFD1","GRA CUSTOMS, KOFORIDUA"],["KGG1","KULUNGUGU"],
  ["KIA1","CEPS KIA"],["KLB1","KALBA CUSTOMS BORDER POST"],["KMS1","CEPS KUMASI"],["KMS9","KUMASI BOST"],["KPG1","KPOGLO"],["KSP1","KWAME SEIKROM CUSTOMS BORDER POST"],["LAD1","LAKPLEVI DAFOR CUSTOMS BORDER POST"],["LAW1","LAWRA CUSTOMS BORDER POST"],["MEN1","MENUSO CUSTOMS BORDER POST"],["MMW9","MAMI WATER BOST"],
  ["MON1","MOGNORI CUSTOMS BORDER POST"],["MSG1","MISSIGA CUSTOMS BORDER POST"],["NAM1","NAMOO CUSTOMS BORDER POST"],["NBP1","NKYENSENKOKOR CUSTOMS BORDER POST"],["NKK1","NKRANKWANTA CUSTOMS BORDER POST"],["NYI1","NYIVE CUSTOMS BORDER POST"],["OCT1","OFFSHORE CAPE THREE POINT"],["OKK1","OSEIKOJOKROM"],["OMA1","OMANPE CUSTOMS POST"],["PGA1","PAGA"],
  ["PJB1","JUBILEE OIL FIELD"],["PUL1","PULIMAKOM CUSTOMS BORDER POST"],["QTL9","QUANTUM TERMINAL LIMITED"],["SAM1","SAMPA CUSTOMS BORDER POST"],["SEG1","SEGBE JUNCTION"],["SEW1","SEWUM CUSTOMS POST"],["SHI1","SHIA CUSTOMS BORDER POST"],["SUN1","SUNYANI CUSTOMS POST"],["TAT1","TATALE CUSTOMS BORDER POST"],["TEN1","TWENEBOA ENYENRA NTOMME"],
  ["TIN1","TINJASE CUSTOMS BORDER POST"],["TKD1","CEPS TAKORADI"],["TKD9","TAKORADI BOST"],["TMA1","CEPS TEMA"],["TML1","CEPS TAMALE"],["TML9","TAMALE BOST"],["TOR9","TEMA OIL REFINERY"],["TUM1","TUMU CUSTOMS OFFICE"],["WAC1","GRA CUSTOMS WA COLLECTION"],["WLI1","WLI AGORVIEFE CUSTOMS BORDER POST"],
  ["WON1","WONJUGA CUSTOMS BORDER POST"],["YAK1","YAAKROM CUSTOMS BORDER POST"],["YBP1","PILLAR 34 CUSTOMS BORDER POST"],["YEN1","YENDI CUSTOMS BORDER POST"],["YKS1","YAKAASE CUSTOMS POST"],["ZEB1","ZEBILLA CUSTOMS BORDER POST"],["ZUR1","ZUARUNGU CUSTOMS POST"]
];

const mdaDialog = document.querySelector("#mda-branch-dialog");
const mdaList = document.querySelector("#mda-code-list");
const mdaPagination = document.querySelector("#mda-code-pagination");
const gfzaBranchInput = document.querySelector("#gfza-branch-search input");
let filteredBranches = mdaBranches;
let mdaPage = 1;

function renderMdaBranches() {
  const pageCount = Math.max(1, Math.ceil(filteredBranches.length / 10));
  mdaPage = Math.min(mdaPage, pageCount);
  mdaList.innerHTML = filteredBranches.slice((mdaPage - 1) * 10, mdaPage * 10).map((entry) => {
    const originalNumber = mdaBranches.indexOf(entry) + 1;
    return `<tr data-code="${entry[0]}" data-name="${entry[1]}"><td>${originalNumber}</td><td>${entry[0]}</td><td>${entry[1]}</td><td>Customs Office</td></tr>`;
  }).join("") || `<tr><td class="empty-row" colspan="4">No fictional code found.</td></tr>`;
  mdaPagination.innerHTML = Array.from({length: pageCount}, (_, index) => `<button type="button" data-mda-page="${index + 1}"${index + 1 === mdaPage ? ' aria-current="page"' : ''}>${index + 1}</button>`).join("");
}

document.querySelector("#gfza-search-button").addEventListener("click", () => { filteredBranches = mdaBranches; mdaPage = 1; renderMdaBranches(); mdaDialog.showModal(); });
document.querySelector("#filter-mda-codes").addEventListener("click", () => {
  const code = document.querySelector("#mda-code-filter").value.trim().toLowerCase();
  const name = document.querySelector("#mda-name-filter").value.trim().toLowerCase();
  filteredBranches = mdaBranches.filter(([itemCode, itemName]) => itemCode.toLowerCase().includes(code) && itemName.toLowerCase().includes(name));
  mdaPage = 1; renderMdaBranches();
});
mdaPagination.addEventListener("click", (event) => { const button = event.target.closest("[data-mda-page]"); if (button) { mdaPage = Number(button.dataset.mdaPage); renderMdaBranches(); } });
mdaList.addEventListener("click", (event) => { const row = event.target.closest("tr[data-code]"); if (!row) return; gfzaBranchInput.value = `${row.dataset.code} — ${row.dataset.name}`; mdaDialog.close(); gfzaBranchInput.focus(); });
