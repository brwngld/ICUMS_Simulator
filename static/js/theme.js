/* ICUMS theme controller — single source of truth for the whole platform.
   Unfold (admin + dashboards in the unfold chrome) persists the choice in
   localStorage "adminTheme" and renders via the html.dark class. The classic
   app pages render via html[data-theme]. This controller keeps both
   conventions in sync so one switch themes every surface. */
(() => {
  const root = document.documentElement;
  const adminKey = "adminTheme";
  const legacyKey = "icums-theme";
  const systemDark = () => window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;

  // Unfold's Alpine persistence JSON-decodes "adminTheme" on every page; a raw
  // value throws there and leaves the page hidden behind x-cloak. This
  // controller always writes the JSON encoding and reads both encodings.
  const decode = (raw) => {
    if (raw === null) return null;
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed === "string") return parsed;
    } catch (error) { /* raw string written by earlier builds */ }
    return raw;
  };

  const storedTheme = () => {
    const t = decode(localStorage.getItem(adminKey)) ?? decode(localStorage.getItem(legacyKey));
    return t === "dark" || t === "light" ? t : "auto";
  };

  const writeAdmin = (t) => localStorage.setItem(adminKey, JSON.stringify(t));

  const resolveTheme = () => {
    const t = storedTheme();
    return t === "dark" || t === "light" ? t : systemDark() ? "dark" : "light";
  };

  const apply = () => {
    const t = resolveTheme();
    root.dataset.theme = t;
    root.classList.toggle("dark", t === "dark");
    root.classList.toggle("light", t === "light");
    document.querySelectorAll("[data-theme-choice]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === t));
    });
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-pressed", String(t === "dark"));
      const label = button.querySelector("[data-theme-label]");
      if (label) label.textContent = t === "dark" ? "Light theme" : "Dark theme";
    });
  };

  const setTheme = (t) => {
    if (t === "system") {
      localStorage.removeItem(adminKey);
      localStorage.removeItem(legacyKey);
    } else {
      writeAdmin(t);
      localStorage.setItem(legacyKey, t);
    }
    apply();
  };

  // Heal a raw adminTheme left by earlier builds so Unfold's JSON.parse
  // survives, and migrate the legacy icums-theme preference.
  const rawAdmin = localStorage.getItem(adminKey);
  if (rawAdmin !== null) {
    let isJsonString = false;
    try { isJsonString = typeof JSON.parse(rawAdmin) === "string"; } catch (error) {}
    if (!isJsonString) {
      const t = decode(rawAdmin);
      if (t === "dark" || t === "light") writeAdmin(t);
      else localStorage.removeItem(adminKey);
    }
  } else if (localStorage.getItem(legacyKey)) {
    const legacy = decode(localStorage.getItem(legacyKey));
    if (legacy === "dark" || legacy === "light") writeAdmin(legacy);
  }

  // Student/tutor dashboard theme picker
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-choice]");
    if (button) setTheme(button.dataset.themeChoice);
  });

  // Guest header toggle
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    setTheme(resolveTheme() === "dark" ? "light" : "dark");
  });

  // Unfold's own switcher writes adminTheme directly — mirror it into the
  // app convention so every surface follows the same choice.
  document.addEventListener("click", () => window.setTimeout(apply, 0));

  // Live follow when following the system preference
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (storedTheme() === "auto") apply();
    });
  }

  apply();
})();
