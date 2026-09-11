/* Shared shell enhancement: responsive navigation, menu accordions, and theme controls. */
(() => {
  const themeKey = 'icums-theme';
  const root = document.documentElement;
  const systemTheme = () => window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const storedTheme = window.localStorage.getItem(themeKey);
  root.dataset.theme = storedTheme === 'dark' || storedTheme === 'light' ? storedTheme : systemTheme();

  const sidebar = document.querySelector('.app-layout .site-header, .portal-sidebar');
  if (!sidebar) return;

  if (sidebar.classList.contains('portal-sidebar') && !sidebar.querySelector('[data-student-dashboard]')) {
    const dashboardLink = document.createElement('a');
    dashboardLink.className = 'return-link';
    dashboardLink.dataset.studentDashboard = '';
    dashboardLink.href = '/';
    dashboardLink.textContent = '← Back to student dashboard';
    sidebar.append(dashboardLink);
  }

  if (sidebar.classList.contains('portal-sidebar') && !sidebar.querySelector('[data-theme-toggle]')) {
    const themeButton = document.createElement('button');
    themeButton.type = 'button';
    themeButton.className = 'theme-toggle';
    themeButton.dataset.themeToggle = '';
    themeButton.innerHTML = '<span class="theme-toggle-icon" aria-hidden="true">◐</span><span data-theme-label>Dark theme</span>';
    const returnLink = sidebar.querySelector('.return-link');
    (returnLink ? returnLink.parentElement : sidebar).append(themeButton);
  }

  const refreshThemeLabel = () => {
    const dark = root.dataset.theme === 'dark';
    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
      button.setAttribute('aria-pressed', String(dark));
      const label = button.querySelector('[data-theme-label]');
      if (label) label.textContent = dark ? 'Light theme' : 'Dark theme';
    });
  };
  if (!window.ICUMSThemeReady) {
    document.addEventListener('click', (event) => {
      if (!event.target.closest('[data-theme-toggle]')) return;
      root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      window.localStorage.setItem(themeKey, root.dataset.theme);
      refreshThemeLabel();
    });
  }
  refreshThemeLabel();

  const mobile = window.matchMedia('(max-width: 52rem)');
  sidebar.id = sidebar.id || 'workspace-navigation';
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'navigation-toggle';
  toggle.setAttribute('aria-controls', sidebar.id);
  toggle.innerHTML = '<span aria-hidden="true">☰</span> Menu';
  const scrim = document.createElement('button');
  scrim.type = 'button';
  scrim.className = 'navigation-scrim';
  scrim.setAttribute('aria-label', 'Close navigation');
  scrim.tabIndex = -1;
  document.body.append(toggle, scrim);
  document.body.classList.add('navigation-enhanced');
  const menu = document.querySelector('.portal-menu');
  if (menu) {
    menu.querySelectorAll('details').forEach((opened) => {
      opened.addEventListener('toggle', () => {
        if (!opened.open) return;
        const parent = opened.parentElement;
        [...parent.children].forEach((sibling) => {
          if (sibling !== opened && sibling instanceof HTMLDetailsElement) sibling.open = false;
        });
      });
    });
  }
  const setOpen = (open, restoreFocus = false) => {
    document.body.classList.toggle('navigation-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.innerHTML = open ? '<span aria-hidden="true">×</span> Close menu' : '<span aria-hidden="true">☰</span> Menu';
    sidebar.inert = mobile.matches && !open;
    if (restoreFocus) toggle.focus();
  };
  toggle.addEventListener('click', () => setOpen(toggle.getAttribute('aria-expanded') !== 'true'));
  scrim.addEventListener('click', () => setOpen(false, true));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && document.body.classList.contains('navigation-open')) setOpen(false, true);
    if (event.key === 'Tab' && mobile.matches && document.body.classList.contains('navigation-open')) {
      const controls = [...sidebar.querySelectorAll('a[href], button, summary, input')].filter(el => el.getClientRects().length && !el.disabled);
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (!first) return;
      if (document.activeElement === toggle) { event.preventDefault(); (event.shiftKey ? last : first).focus(); }
      else if ((!event.shiftKey && document.activeElement === last) || (event.shiftKey && document.activeElement === first)) { event.preventDefault(); toggle.focus(); }
    }
  });
  mobile.addEventListener('change', () => setOpen(false));
  setOpen(false);
})();

// Single Window UCR training directory and regime-specific role guidance.
(() => {
  const regime = [...document.querySelectorAll('select')].find((el) => el.previousElementSibling?.textContent?.includes('Regime Type'));
  if (!regime) return;
  [['FI', 'FI, Free Zones - Inbound'], ['FO', 'FO, Free Zones - Outbound']].forEach(([value, text]) => {
    if (![...regime.options].some((option) => option.value === value || option.textContent.startsWith(value + ','))) {
      regime.add(new Option(text, value));
    }
  });
  const panels = [...document.querySelectorAll('.cargo-panel')];
  const partyPanels = panels.filter((panel) => /^(Exporter|Importer)$/.test(panel.querySelector('h2')?.textContent?.trim() || ''));
  const directory = [
    ['GHA0011002008', 'BERNARD KWAKU AMEGAH', 'Fictional training address, Accra'],
    ['GHA0023004011', 'AKOSUA MENSAH TRADING', 'Fictional training address, Tema'],
    ['GHA0045006022', 'NOVA FREIGHT AND LOGISTICS LTD', ''],
  ];
  const showDirectory = (input) => {
    const dialog = document.createElement('dialog');
    dialog.className = 'code-dialog';
    dialog.innerHTML = '<form method="dialog" class="code-dialog-card"><header><h2>ICUMS fictional TIN / NID directory</h2><button aria-label="Close">×</button></header><p class="dialog-help">Choose a training record to fill the party details.</p><div class="cargo-table-wrap"><table><thead><tr><th>Select</th><th>TIN</th><th>Description</th><th>Name</th><th></th></tr></thead><tbody></tbody></table></div></form>';
    const body = dialog.querySelector('tbody');
    directory.forEach(([tin, name, address]) => { const row = document.createElement('tr'); row.innerHTML = `<td><input type="radio" name="ucr-party" aria-label="Select ${name}"></td><td>${tin}</td><td>${name} (Importers, Exporters)</td><td>${name}</td><td><button type="button">Choose</button></td>`; row.querySelector('button').addEventListener('click', () => { input.value = tin; const panel = input.closest('.cargo-panel'); const fields = [...panel.querySelectorAll('input, textarea')]; const nameField = fields.find((field) => field !== input && !field.type && field.previousElementSibling?.textContent?.includes('Name')); if (nameField) nameField.value = name; const addressField = fields.find((field) => field !== input && field.tagName === 'TEXTAREA'); if (addressField && address) addressField.value = address; dialog.close(); dialog.remove(); }); body.appendChild(row); });
    document.body.appendChild(dialog); dialog.addEventListener('close', () => dialog.remove()); dialog.showModal();
  };
  const addSearch = (panel) => { const input = [...panel.querySelectorAll('input')].find((el) => el.previousElementSibling?.textContent?.includes('TIN / NID')); if (!input || panel.querySelector('[data-tin-search]')) return; const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Search'; button.dataset.tinSearch = 'true'; button.className = 'secondary-button'; button.addEventListener('click', () => showDirectory(input)); input.insertAdjacentElement('afterend', button); };
  const update = () => { const switched = regime.value.startsWith('FO') || regime.value.startsWith('EX'); partyPanels.forEach((panel) => { const heading = panel.querySelector('h2'); if (heading) heading.textContent = switched ? (heading.textContent.trim() === 'Exporter' ? 'Importer' : 'Exporter') : heading.textContent.trim(); if (switched) addSearch(panel); }); };
  regime.addEventListener('change', update); update();
})();
