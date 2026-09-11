document.addEventListener('DOMContentLoaded', () => {
  function setFieldVisible(inline, name, visible) {
    const boxes = inline.querySelectorAll(`.fieldBox.field-${name}`);
    if (boxes.length) {
      boxes.forEach(box => box.classList.toggle('bl-field-hidden', !visible));
      return;
    }
    const row = inline.querySelector(`.form-row.field-${name}`);
    if (row) row.classList.toggle('bl-field-hidden', !visible);
  }

  function updateInline(inline) {
    const cargoType = inline.querySelector('[id$="-cargo_type"]')?.value;
    if (!cargoType) return;
    const isVehicle = cargoType === 'vehicle';
    const isSimple = cargoType === 'general' || cargoType === 'personal_effects';
    const showTechnical = isVehicle || cargoType === 'machinery' || cargoType === 'other';
    setFieldVisible(inline, 'goods_description', !isVehicle);
    ['vehicle_year', 'vehicle_make', 'vehicle_model', 'vin_or_chassis', 'hs_code'].forEach(name => setFieldVisible(inline, name, showTechnical && !isSimple));
    inline.querySelectorAll('.form-row').forEach(row => {
      const boxes = [...row.querySelectorAll('.fieldBox')];
      row.classList.toggle('bl-empty-row', boxes.length > 0 && boxes.every(box => box.classList.contains('bl-field-hidden')));
    });
  }

  function updateAllCargoFields() {
    document.querySelectorAll('.inline-related').forEach(updateInline);
  }

  document.addEventListener('change', event => {
    if (event.target.matches('[id$="-cargo_type"]')) updateInline(event.target.closest('.inline-related'));
  });
  if (window.django?.jQuery) {
    window.django.jQuery(document).on('formset:added', (_event, row) => updateInline(row.get ? row.get(0) : row));
  }
  updateAllCargoFields();
});
