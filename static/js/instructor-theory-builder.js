(() => {
  document.querySelectorAll('[data-authoring-tabs]').forEach((tabset) => {
    const tabs = [...tabset.querySelectorAll('[data-authoring-tab]')];
    const scope = tabset.closest('.authoring') || document;
    const panels = [...scope.querySelectorAll('[data-authoring-panel]')];
    const activate = (name, focus = false) => {
      tabs.forEach((tab) => {
        const active = tab.dataset.authoringTab === name;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
        if (active && focus) tab.focus();
      });
      panels.forEach((panel) => { panel.hidden = panel.dataset.authoringPanel !== name; });
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => activate(tab.dataset.authoringTab));
      tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault();
        const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        activate(tabs[next].dataset.authoringTab, true);
      });
    });
  });
  document.querySelectorAll('.authoring-section-nav [data-authoring-tab]').forEach((shortcut) => {
    shortcut.addEventListener('click', () => {
      document.querySelector(`[data-authoring-tabs] [data-authoring-tab="${shortcut.dataset.authoringTab}"]`)?.click();
      document.querySelectorAll('.authoring-section-nav [data-authoring-tab]').forEach((item) => item.setAttribute('aria-selected', String(item === shortcut)));
    });
  });

  const search = document.querySelector('[data-course-search]');
  const status = document.querySelector('[data-course-status]');
  const filterRows = () => {
    const query = (search?.value || '').trim().toLowerCase();
    const selected = status?.value || 'all';
    document.querySelectorAll('[data-course-row]').forEach((row) => {
      const matchesText = !query || row.textContent.toLowerCase().includes(query);
      const matchesStatus = selected === 'all' || row.dataset.status === selected;
      row.hidden = !(matchesText && matchesStatus);
    });
  };
  search?.addEventListener('input', filterRows);
  status?.addEventListener('change', filterRows);
})();
