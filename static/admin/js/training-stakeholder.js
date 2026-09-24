document.addEventListener('DOMContentLoaded', () => {
  const mode = document.querySelector('#id_generation_mode');
  const code = document.querySelector('#id_code');
  if (!mode || !code) return;
  const row = code.closest('.form-row') || code.closest('.field-code') || code.parentElement;
  function update() {
    const automatic = mode.value === 'auto';
    row.hidden = automatic;
    code.required = !automatic;
    if (automatic) code.value = '';
  }
  mode.addEventListener('change', update);
  update();
});
