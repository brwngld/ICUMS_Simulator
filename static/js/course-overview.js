(() => {
  const tabs = [...document.querySelectorAll("[data-course-tab]")];
  const panels = [...document.querySelectorAll("[data-course-panel]")];

  function activate(name, moveFocus = false) {
    const selected = tabs.find((tab) => tab.dataset.courseTab === name) || tabs[0];
    if (!selected) return;
    tabs.forEach((tab) => {
      const active = tab === selected;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.coursePanel !== selected.dataset.courseTab;
    });
    if (moveFocus) selected.focus();
    history.replaceState(null, "", `#${selected.dataset.courseTab}`);
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activate(tab.dataset.courseTab));
    tab.addEventListener("keydown", (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      let target = index;
      if (event.key === 'ArrowLeft') target = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'ArrowRight') target = (index + 1) % tabs.length;
      if (event.key === 'Home') target = 0;
      if (event.key === 'End') target = tabs.length - 1;
      activate(tabs[target].dataset.courseTab, true);
    });
  });

  document.querySelectorAll("[data-open-tab]").forEach((button) => {
    button.addEventListener("click", () => activate(button.dataset.openTab, true));
  });

  const expandButton = document.querySelector("[data-expand-modules]");
  expandButton?.addEventListener("click", () => {
    const modules = [...document.querySelectorAll(".course-module")];
    const shouldOpen = modules.some((module) => !module.open);
    modules.forEach((module) => { module.open = shouldOpen; });
    expandButton.textContent = shouldOpen ? "Collapse all" : "Expand all";
  });

  const search = document.querySelector("[data-resource-search]");
  search?.addEventListener("input", () => {
    const query = search.value.trim().toLowerCase();
    const items = [...document.querySelectorAll("[data-resource-item]")];
    let matches = 0;
    items.forEach((item) => {
      const visible = !query || item.textContent.toLowerCase().includes(query);
      item.hidden = !visible;
      if (visible) matches += 1;
    });
    const empty = document.querySelector("[data-search-empty]");
    if (empty) empty.hidden = !query || matches > 0;
  });

  const initial = location.hash.slice(1);
  if (tabs.some((tab) => tab.dataset.courseTab === initial)) activate(initial);
})();
