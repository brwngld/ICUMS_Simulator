document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('#commercial-form-mode'); const preview = document.querySelector('#commercial-preview-mode');
  const definitions = {invoice:['COMMERCIAL INVOICE','A final seller-issued document showing the goods supplied and the commercial values payable.'],proforma_invoice:['PROFORMA INVOICE','A quotation issued before purchase or shipment. Prices and totals are provisional and are not a final demand for payment.'],packing_list:['PACKING LIST','A shipment-detail document showing packages, quantities and weights. It contains no prices or commercial totals.']};
  document.querySelectorAll('[data-commercial-mode]').forEach(button => button.addEventListener('click', () => { const live=button.dataset.commercialMode==='preview'; form.hidden=live; preview.hidden=!live; document.querySelectorAll('[data-commercial-mode]').forEach(item=>item.setAttribute('aria-pressed',String(item===button))); refresh(); }));
  function field(name,fallback='Not supplied'){const input=document.querySelector(`#id_${name}`);return input&&input.value.trim()?input.value:fallback}
  function setText(node,text){if(node&&node.textContent!==text)node.textContent=text}
  function setVisible(name,visible){document.querySelectorAll(`.field-${name}`).forEach(node=>node.classList.toggle('commercial-hidden',!visible))}
  function escaped(value){return String(value||'-').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
  function refresh(){
    const type=field('document_type','invoice'); const packing=type==='packing_list'; const definition=definitions[type]||definitions.invoice;
    setText(document.querySelector('[data-document-title]'),definition[0]); setText(document.querySelector('[data-document-explanation]'),definition[1]);
    document.querySelectorAll('[data-preview]').forEach(node=>setText(node,field(node.dataset.preview,node.textContent)));
    ['fob','freight','insurance','unit_price','amount'].forEach(name=>setVisible(name,!packing));
    document.querySelectorAll('[data-price-column]').forEach(node=>node.hidden=packing); document.querySelectorAll('[data-packing-column]').forEach(node=>node.hidden=!packing); document.querySelector('[data-preview-totals]').hidden=packing;
    const rows=[]; document.querySelectorAll('[id$="-description"]').forEach((description,index)=>{const prefix=description.id.replace('description','');const get=suffix=>document.querySelector(`#${prefix}${suffix}`)?.value?.trim()||'';if(!description.value.trim()||document.querySelector(`#${prefix}DELETE`)?.checked)return;const cells=packing?[index+1,description.value,`${get('quantity')} ${get('quantity_unit')}`,`${get('package_count')} ${get('pieces_per_package')}`,`${get('net_weight')} ${get('weight_unit')}`,`${get('gross_weight')} ${get('weight_unit')}`]:[index+1,description.value,`${get('quantity')} ${get('quantity_unit')}`,`${field('currency','USD')} ${get('unit_price')}`,`${field('currency','USD')} ${get('amount')}`];rows.push(`<tr>${cells.map(cell=>`<td>${escaped(cell)}</td>`).join('')}</tr>`)});
    document.querySelector('[data-preview-lines]').innerHTML=rows.join('')||`<tr><td>1</td><td>Add line items in the guided form.</td><td>-</td><td colspan="${packing?3:2}">-</td></tr>`;
  }
  document.addEventListener('input',refresh);document.addEventListener('change',refresh);if(window.django?.jQuery)window.django.jQuery(document).on('formset:added formset:removed',refresh);refresh();
});
