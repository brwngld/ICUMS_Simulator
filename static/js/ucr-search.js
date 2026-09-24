(() => {
  const iso = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  document.querySelectorAll('[data-date-range]').forEach((button) => button.addEventListener('click', () => {
    const inputs = button.closest('.date-range')?.querySelectorAll('input[type="date"]');
    const from = inputs?.[0];
    const to = inputs?.[1];
    if (!from || !to) return;
    const action = button.dataset.dateRange;
    if (action === 'reset') { from.value = ''; to.value = ''; return; }
    const today = new Date();
    const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const end = new Date(start);
    if (action === 'month') start.setMonth(start.getMonth() - 1);
    if (action === 'week') start.setDate(start.getDate() - 7);
    if (action === 'next-week') end.setDate(end.getDate() + 7);
    from.value = iso(start);
    to.value = iso(end);
  }));
})();
