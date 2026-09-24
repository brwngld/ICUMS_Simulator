/* Shared shell enhancement: responsive navigation, menu accordions, and theme controls. */
(() => {
  const themeKey = 'icums-theme';
  const root = document.documentElement;
  const systemTheme = () => window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const storedTheme = window.localStorage.getItem(themeKey);
  root.dataset.theme = storedTheme === 'dark' || storedTheme === 'light' ? storedTheme : systemTheme();

  const sidebar = document.querySelector('.app-layout .site-header, .portal-sidebar');
  if (!sidebar) return;

  const portalBrand = sidebar.querySelector('.portal-brand');
  if (portalBrand && portalBrand.tagName !== 'A') {
    const homeLink = document.createElement('a');
    homeLink.className = portalBrand.className;
    homeLink.href = '/practical/portal/';
    homeLink.setAttribute('aria-label', 'ICUMS simulator home');
    homeLink.innerHTML = portalBrand.innerHTML;
    portalBrand.replaceWith(homeLink);
  }

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
  toggle.setAttribute('aria-label', 'Toggle navigation');
  toggle.innerHTML = '<span aria-hidden="true">☰</span>';
  const scrim = document.createElement('button');
  scrim.type = 'button';
  scrim.className = 'navigation-scrim';
  scrim.setAttribute('aria-label', 'Close navigation');
  scrim.tabIndex = -1;
  const portalHeader = sidebar.classList.contains('portal-sidebar') && !document.body.hasAttribute('data-portal-home') ? document.querySelector('.portal-header') : null;
  // The simulator hamburger exists on every portal page except the workspace home.
  if (!portalHeader) return;
  const portalHeading = portalHeader.querySelector('.portal-heading');
  if (portalHeading) {
    const textWrapper = document.createElement('div');
    textWrapper.className = 'portal-heading-text';
    [...portalHeading.childNodes].forEach((node) => textWrapper.append(node));
    portalHeading.append(toggle, textWrapper);
  } else portalHeader.prepend(toggle);
  document.body.append(scrim);
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
    toggle.innerHTML = open ? '<span aria-hidden="true">×</span>' : '<span aria-hidden="true">☰</span>';
    sidebar.inert = mobile.matches && !open || !mobile.matches && document.body.classList.contains('navigation-collapsed');
    if (restoreFocus) toggle.focus();
  };
  toggle.addEventListener('click', () => {
    if (mobile.matches) setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    else {
      const collapsed = document.body.classList.toggle('navigation-collapsed');
      sidebar.inert = collapsed;
      toggle.setAttribute('aria-expanded', String(!collapsed));
    }
  });
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
  mobile.addEventListener('change', () => { document.body.classList.remove('navigation-collapsed'); setOpen(false); });
  setOpen(false);
  if (!mobile.matches) toggle.setAttribute('aria-expanded', 'true');
})();
