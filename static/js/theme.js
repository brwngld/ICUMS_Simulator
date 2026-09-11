/* Shared ICUMS theme preference for learner, instructor, and admin surfaces. */
(() => {
  window.ICUMSThemeReady = true;
  const storageKey = 'icums-theme';
  const root = document.documentElement;
  const systemTheme = () => window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

  const stored = window.localStorage.getItem(storageKey);
  root.dataset.theme = stored === 'dark' || stored === 'light' ? stored : systemTheme();

  const refreshLabels = () => {
    const dark = root.dataset.theme === 'dark';
    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
      button.setAttribute('aria-pressed', String(dark));
      const label = button.querySelector('[data-theme-label]');
      if (label) label.textContent = dark ? 'Light theme' : 'Dark theme';
      button.setAttribute('title', dark ? 'Switch to light theme' : 'Switch to dark theme');
    });
  };

  const toggle = (event) => {
    const button = event.target.closest('[data-theme-toggle]');
    if (!button) return;
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    window.localStorage.setItem(storageKey, next);
    refreshLabels();
  };

  document.addEventListener('click', toggle);
  document.addEventListener('DOMContentLoaded', refreshLabels);
  refreshLabels();
})();
