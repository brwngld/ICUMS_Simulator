document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('#bl-form-mode');
  const preview = document.querySelector('#bl-preview-mode');
  const templateNames = {carrier_grid: 'Carrier Grid BL', ocean_transport: 'Ocean Transport BL', multimodal: 'Multimodal BL'};

  document.querySelectorAll('[data-bl-mode]').forEach(button => button.addEventListener('click', () => {
    const live = button.dataset.blMode === 'preview';
    form.hidden = live;
    preview.hidden = !live;
    document.querySelectorAll('[data-bl-mode]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    refresh();
  }));

  function value(name) {
    const field = document.querySelector(`#id_${name}`);
    return field && field.value.trim() ? field.value : 'Not supplied';
  }

  function setText(node, text) {
    if (node && node.textContent !== text) node.textContent = text;
  }

  function setFieldVisible(inline, name, visible) {
    const boxes = inline.querySelectorAll(`.fieldBox.field-${name}`);
    if (boxes.length) boxes.forEach(box => { box.classList.toggle('bl-field-hidden', !visible); });
    else {
      const row = inline.querySelector(`.form-row.field-${name}`);
      if (row) row.classList.toggle('bl-field-hidden', !visible);
    }
  }

  function updateCargoFields() {
    document.querySelectorAll('.inline-related').forEach(inline => {
      const cargoType = inline.querySelector('[id$="-cargo_type"]')?.value;
      if (!cargoType) return;
      const isVehicle = cargoType === 'vehicle';
      const isSimple = cargoType === 'general' || cargoType === 'personal_effects';
      const isMachinery = cargoType === 'machinery';
      setFieldVisible(inline, 'goods_description', !isVehicle);
      ['vehicle_year', 'vehicle_make', 'vehicle_model', 'vin_or_chassis', 'hs_code'].forEach(name => {
        setFieldVisible(inline, name, isVehicle || isMachinery || (!isSimple && cargoType === 'other'));
      });
      inline.querySelectorAll('.form-row').forEach(row => {
        const boxes = [...row.querySelectorAll('.fieldBox')];
        row.classList.toggle('bl-empty-row', boxes.length > 0 && boxes.every(box => box.classList.contains('bl-field-hidden')));
      });
    });
  }

  function refresh() {
    updateCargoFields();
    document.querySelectorAll('[data-preview]').forEach(node => { setText(node, value(node.dataset.preview)); });
    const selected = document.querySelector('#id_template')?.value || 'carrier_grid';
    preview.classList.remove('template-carrier_grid', 'template-ocean_transport', 'template-multimodal');
    preview.classList.add(`template-${selected}`);
    const banner = document.querySelector('[data-preview-template]');
    if (banner) setText(banner, templateNames[selected] || 'Bill of Lading');
    const lines = [];
    document.querySelectorAll('[id$="-cargo_type"]').forEach(typeField => {
      const prefix = typeField.id.replace('cargo_type', '');
      const get = suffix => document.querySelector(`#${prefix}${suffix}`)?.value?.trim() || '';
      if (!get('container_number') && !get('goods_description') && !get('vin_or_chassis')) return;
      const description = typeField.value === 'vehicle'
        ? `${get('vehicle_year')} ${get('vehicle_make')} ${get('vehicle_model')}\nVIN/Chassis: ${get('vin_or_chassis')}`
        : get('goods_description');
      lines.push(`${get('container_number')} / Seal ${get('seal_number')}\n${get('package_quantity')} ${get('package_type')} - ${description}\nHS ${get('hs_code')} · ${get('gross_weight')} ${get('weight_unit')}`);
    });
    const cargo = document.querySelector('[data-preview-inline="cargo_items"]');
    if (cargo) setText(cargo, lines.join('\n\n') || 'Add cargo items in the guided form to display them here.');
  }

  document.addEventListener('input', refresh);
  document.addEventListener('change', refresh);
  if (window.django?.jQuery) {
    window.django.jQuery(document).on('formset:added formset:removed', refresh);
  }
  refresh();
});
