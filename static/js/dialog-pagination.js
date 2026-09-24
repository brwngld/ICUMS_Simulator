// Shared pager for common-code dialogs, styled like the ICUMS reference:
// "Total : N" on the left, « ‹ 1 2 3 … n › » on the right.
// Usage: drawDialogPager(container, { total, page, pageCount, onPage })
(() => {
  function pagerEntries(page, pageCount) {
    if (pageCount <= 7) return Array.from({ length: pageCount }, (_, index) => index + 1);
    const keep = new Set([1, pageCount, page - 1, page, page + 1]);
    const entries = [];
    let previous = 0;
    [...keep].filter((n) => n >= 1 && n <= pageCount).sort((a, b) => a - b).forEach((n) => {
      if (n - previous > 1) entries.push("…");
      entries.push(n);
      previous = n;
    });
    return entries;
  }

  window.drawDialogPager = (container, { total, page, pageCount, onPage }) => {
    if (!container) return;
    container.replaceChildren();
    const totalSpan = document.createElement("span");
    totalSpan.className = "dialog-total";
    totalSpan.textContent = `Total : ${total}`;
    const pager = document.createElement("nav");
    pager.className = "dialog-pager";
    pager.setAttribute("aria-label", "Dialog pages");

    const arrow = (label, target, disabled, name) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.dataset.page = String(target);
      button.disabled = disabled;
      button.setAttribute("aria-label", name);
      pager.append(button);
    };
    arrow("«", 1, page === 1, "First page");
    arrow("‹", page - 1, page === 1, "Previous page");
    pagerEntries(page, pageCount).forEach((entry) => {
      if (entry === "…") {
        const gap = document.createElement("span");
        gap.className = "pager-gap";
        gap.textContent = "…";
        pager.append(gap);
        return;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = String(entry);
      button.dataset.page = String(entry);
      if (entry === page) button.setAttribute("aria-current", "page");
      pager.append(button);
    });
    arrow("›", page + 1, page === pageCount, "Next page");
    arrow("»", pageCount, page === pageCount, "Last page");

    container.append(totalSpan, pager);
    container.onclick = (event) => {
      const button = event.target.closest("button[data-page]");
      if (!button || button.disabled) return;
      const target = Math.min(Math.max(Number(button.dataset.page), 1), pageCount);
      if (target !== page) onPage(target);
    };
  };
})();
