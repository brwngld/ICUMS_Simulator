(() => {
  document.querySelectorAll('[data-completion-form]').forEach((form) => {
    form.addEventListener('submit', () => {
      const button = form.querySelector('button[type="submit"]');
      if (!button) return;
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      button.textContent = 'Saving…';
    });
  });
})();
