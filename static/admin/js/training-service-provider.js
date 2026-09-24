document.addEventListener('DOMContentLoaded', () => {
  const stakeholder = document.querySelector('#id_stakeholder');
  const name = document.querySelector('#id_name');
  const address = document.querySelector('#id_address');
  if (stakeholder && name && address && window.trainingStakeholders) {
    stakeholder.addEventListener('change', () => {
      const record = window.trainingStakeholders[stakeholder.value];
      if (record) {
        name.value = record.name;
        address.value = record.address;
      }
    });
  }

  const country = document.querySelector('#id_country_code');
  if (!country || !window.ucrCountryCodes || !window.drawDialogPager) return;
  country.setAttribute('autocomplete', 'off');
  country.addEventListener('input', () => { country.value = country.value.toUpperCase(); });

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'button sp-country-button';
  button.textContent = '⌕';
  button.setAttribute('aria-label', 'Search country code');
  const wrap = document.createElement('div');
  wrap.className = 'sp-country-lookup';
  country.replaceWith(wrap);
  wrap.append(country, button);

  const dialog = document.createElement('dialog');
  dialog.className = 'sp-country-dialog';
  const card = document.createElement('div');
  card.className = 'sp-dialog-card';
  const header = document.createElement('header');
  const heading = document.createElement('h3');
  heading.textContent = 'Common Code · Country';
  const closeButton = document.createElement('button');
  closeButton.type = 'button';
  closeButton.className = 'sp-dialog-close';
  closeButton.textContent = '×';
  closeButton.setAttribute('aria-label', 'Close country search');
  header.append(heading, closeButton);

  const filters = document.createElement('div');
  filters.className = 'sp-dialog-filters';
  const codeFilter = document.createElement('input');
  codeFilter.maxLength = 2;
  codeFilter.setAttribute('aria-label', 'Filter by code');
  const nameFilter = document.createElement('input');
  nameFilter.setAttribute('aria-label', 'Filter by code name');
  const searchButton = document.createElement('button');
  searchButton.type = 'button';
  searchButton.className = 'sp-filter-button';
  searchButton.textContent = 'Search';
  const codeLabel = document.createElement('label');
  codeLabel.textContent = 'Code ';
  codeLabel.append(codeFilter);
  const nameLabel = document.createElement('label');
  nameLabel.textContent = 'Code Name ';
  nameLabel.append(nameFilter);
  filters.append(codeLabel, nameLabel, searchButton);

  const scroll = document.createElement('div');
  scroll.className = 'sp-dialog-scroll';
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>No.</th><th>Code</th><th>Code Name</th><th>Code Description</th></tr>';
  const tbody = document.createElement('tbody');
  table.append(thead, tbody);
  scroll.append(table);
  const empty = document.createElement('p');
  empty.className = 'sp-dialog-empty';
  empty.hidden = true;
  empty.textContent = 'No country matches that code or name.';

  const footer = document.createElement('div');
  footer.className = 'sp-dialog-footer';
  const pager = document.createElement('div');
  pager.className = 'sp-dialog-pager-holder';
  const help = document.createElement('p');
  help.className = 'sp-dialog-help';
  help.textContent = 'Select a row to place its code in Country.';
  card.append(header, filters, scroll, empty, footer, help);
  dialog.append(card);
  document.body.append(dialog);

  const PAGE_SIZE = 10;
  let page = 1;
  let matches = [...window.ucrCountryCodes];
  function choose(code) {
    country.value = code;
    dialog.close();
    country.dispatchEvent(new Event('change', {bubbles: true}));
    country.focus();
  }
  function draw() {
    const pageCount = Math.max(1, Math.ceil(matches.length / PAGE_SIZE));
    page = Math.min(page, pageCount);
    tbody.replaceChildren();
    matches.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).forEach(([code, label], index) => {
      const row = document.createElement('tr');
      [(page - 1) * PAGE_SIZE + index + 1, code, label, 'Country Code'].forEach((value) => {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.append(cell);
      });
      row.tabIndex = 0;
      const pick = () => choose(code);
      row.addEventListener('click', pick);
      row.addEventListener('keydown', (event) => { if (event.key === 'Enter') pick(); });
      tbody.append(row);
    });
    empty.hidden = matches.length > 0;
    window.drawDialogPager(footer, {total: matches.length, page, pageCount, onPage: (target) => { page = target; draw(); }});
  }
  function applyFilter() {
    const code = codeFilter.value.trim().toUpperCase();
    const needle = nameFilter.value.trim().toLowerCase();
    matches = window.ucrCountryCodes.filter(([key, label]) => key.includes(code) && label.toLowerCase().includes(needle));
    page = 1;
    draw();
  }
  searchButton.addEventListener('click', applyFilter);
  codeFilter.addEventListener('input', applyFilter);
  nameFilter.addEventListener('input', applyFilter);
  closeButton.addEventListener('click', () => dialog.close());
  button.addEventListener('click', () => {
    codeFilter.value = country.value.trim();
    nameFilter.value = '';
    applyFilter();
    dialog.showModal();
  });
});
