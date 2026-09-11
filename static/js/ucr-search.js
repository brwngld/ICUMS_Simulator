const ucrResults = document.querySelector("#ucr-results");
const ucrMessage = document.querySelector("#ucr-action-message");

document.querySelector("#ucr-search").addEventListener("click", () => {
  ucrResults.innerHTML = `<tr>
    <td><button class="ucr-result-link" type="button">SIM-UCR-2600626027</button></td>
    <td>Import</td><td>JKB LOGISTICS LTD</td><td>P0033673896, HAYFORD ESHUN</td>
    <td>TRAINING-001</td><td>AP</td>
    <td><button type="button" data-ucr-action="Clone">Clone</button></td>
    <td><button type="button" data-ucr-action="Amend">Amend</button></td>
  </tr>`;
});

document.querySelector("#ucr-reset").addEventListener("click", () => {
  document.querySelectorAll("#main-content input").forEach((input) => { input.value = ""; });
  document.querySelectorAll("#main-content select").forEach((select) => { select.selectedIndex = 0; });
  ucrResults.innerHTML = `<tr class="ucr-empty"><td class="empty-row" colspan="8">No fictional data found.</td></tr>`;
  ucrMessage.hidden = true;
});

ucrResults.addEventListener("click", (event) => {
  const action = event.target.dataset.ucrAction;
  if (!action) return;
  ucrMessage.hidden = false;
  ucrMessage.textContent = `${action} is a frontend placeholder. No UCR has been changed.`;
});
