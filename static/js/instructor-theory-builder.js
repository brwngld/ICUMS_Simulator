(() => {
  document.querySelectorAll('[data-authoring-tabs]').forEach((tabset) => {
    const tabs = [...tabset.querySelectorAll('[data-authoring-tab]')];
    const scope = tabset.closest('.authoring') || document;
    const panels = [...scope.querySelectorAll('[data-authoring-panel]')];
    const activate = (name, focus = false) => {
      tabs.forEach((tab) => {
        const active = tab.dataset.authoringTab === name;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
        if (active && focus) tab.focus();
      });
      panels.forEach((panel) => {
        if (panel.dataset.authoringPanel === name) {
          panel.removeAttribute('hidden');
        } else {
          panel.setAttribute('hidden', '');
        }
      });
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => activate(tab.dataset.authoringTab));
      tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault();
        const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        activate(tabs[next].dataset.authoringTab, true);
      });
    });
    // Activate the correct tab on page load: honour ?tab= param, then the
    // aria-selected="true" tab, then the first tab as a final fallback.
    const params = new URLSearchParams(location.search);
    const initial = params.get('tab')
      || (tabs.find((t) => t.getAttribute('aria-selected') === 'true') || tabs[0])?.dataset.authoringTab;
    if (initial) activate(initial);
  });
  document.querySelectorAll('.authoring-section-nav [data-authoring-tab]').forEach((shortcut) => {
    shortcut.addEventListener('click', () => {
      document.querySelector(`[data-authoring-tabs] [data-authoring-tab="${shortcut.dataset.authoringTab}"]`)?.click();
      document.querySelectorAll('.authoring-section-nav [data-authoring-tab]').forEach((item) => item.setAttribute('aria-selected', String(item === shortcut)));
    });
  });

  const search = document.querySelector('[data-course-search]');
  const status = document.querySelector('[data-course-status]');
  const filterRows = () => {
    const query = (search?.value || '').trim().toLowerCase();
    const selected = status?.value || 'all';
    document.querySelectorAll('[data-course-row]').forEach((row) => {
      const matchesText = !query || row.textContent.toLowerCase().includes(query);
      const matchesStatus = selected === 'all' || row.dataset.status === selected;
      row.hidden = !(matchesText && matchesStatus);
    });
  };
  search?.addEventListener('input', filterRows);
  status?.addEventListener('change', filterRows);

  const courseModal = document.getElementById('create-course');
  document.querySelector('[data-open-course-modal]')?.addEventListener('click', () => {
    courseModal?.showModal();
    courseModal?.querySelector('input')?.focus();
  });
  document.querySelector('[data-close-course-modal]')?.addEventListener('click', () => courseModal?.close());
  courseModal?.addEventListener('click', (event) => {
    if (event.target === courseModal) courseModal.close();
  });
  document.querySelectorAll('[data-delete-course-form]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(`Delete the draft course “${form.dataset.courseName}” and all of its draft content? This cannot be undone.`)) event.preventDefault();
    });
  });

  const lessonModal = document.getElementById('add-lesson');
  const openLessonModal = () => {
    if (!lessonModal?.open) lessonModal?.showModal();
    lessonModal?.querySelector('input')?.focus();
  };
  document.querySelectorAll('[data-open-lesson-modal]').forEach((button) => button.addEventListener('click', openLessonModal));
  document.querySelector('[data-close-lesson-modal]')?.addEventListener('click', () => lessonModal?.close());
  lessonModal?.addEventListener('click', (event) => {
    if (event.target === lessonModal) lessonModal.close();
  });
  if (new URLSearchParams(location.search).get('add') === 'lesson') openLessonModal();

  document.querySelectorAll('[data-structured-field]').forEach((field) => {
    const source = field.querySelector('.authoring-source-field textarea');
    const list = field.querySelector('[data-structured-list]');
    const addButton = field.querySelector('[data-add-structured-row]');
    if (!source || !list || !addButton) return;
    const type = field.dataset.structuredField;
    const rowPlaceholder = field.dataset.rowPlaceholder || 'Learning objective';
    const values = source.value.split(/\r?\n/).filter((line) => line.trim());
    const rows = values.map((line) => {
      if (type !== 'key-terms') return { value: line.trim() };
      const separator = line.indexOf('::');
      return separator < 0
        ? { term: line.trim(), definition: '' }
        : { term: line.slice(0, separator).trim(), definition: line.slice(separator + 2).trim() };
    });

    const sync = () => {
      source.value = rows.map((row) => type === 'key-terms'
        ? `${row.term.trim()} :: ${row.definition.trim()}`
        : row.value.trim()).filter((line) => line.replace('::', '').trim()).join('\n');
    };
    const render = () => {
      list.replaceChildren();
      rows.forEach((row, index) => {
        const wrapper = document.createElement('div');
        wrapper.className = `authoring-structured-row authoring-structured-row--${type}`;
        const marker = document.createElement('span');
        marker.className = 'authoring-structured-number';
        marker.textContent = index + 1;
        wrapper.append(marker);
        const addInput = (value, placeholder, key) => {
          const input = document.createElement('input');
          input.type = 'text';
          input.value = value;
          input.placeholder = placeholder;
          input.setAttribute('aria-label', placeholder);
          input.addEventListener('input', () => { row[key] = input.value; sync(); });
          wrapper.append(input);
        };
        if (type === 'key-terms') {
          addInput(row.term, 'Term', 'term');
          addInput(row.definition, 'Definition', 'definition');
        } else {
          addInput(row.value, rowPlaceholder, 'value');
        }
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'authoring-structured-remove';
        remove.textContent = 'Remove';
        remove.addEventListener('click', () => { rows.splice(index, 1); sync(); render(); });
        wrapper.append(remove);
        list.append(wrapper);
      });
    };
    source.hidden = true;
    field.classList.add('is-enhanced');
    addButton.addEventListener('click', () => {
      rows.push(type === 'key-terms' ? { term: '', definition: '' } : { value: '' });
      render();
      list.querySelector('.authoring-structured-row:last-child input')?.focus();
    });
    render();
  });
})();

// Live cover preview before the form is submitted. The file input is never
// removed from the DOM so the chosen file survives until save.
(function () {
  const input = document.querySelector('input[name="cover_image"]');
  if (!input) return;
  input.addEventListener('change', function () {
    const file = this.files && this.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
      const dataUrl = e.target.result;
      const zone = document.querySelector('.authoring-image-upload');
      const preview = document.querySelector('.authoring-image-preview');

      function ensureNote(parent, insertBeforeLabel) {
        let note = parent.querySelector('.authoring-image-live-note');
        if (!note) {
          note = document.createElement('p');
          note.className = 'authoring-image-live-note';
          note.style.cssText = 'margin:0;color:var(--au-muted);font-size:.68rem';
          if (insertBeforeLabel) parent.prepend(note);
          else parent.append(note);
        }
        note.textContent = file.name + ' selected — save to apply';
        return note;
      }

      if (zone) {
        let live = zone.querySelector('.authoring-image-live');
        if (!live) {
          live = document.createElement('img');
          live.className = 'authoring-image-live';
          live.alt = 'Selected image';
          live.style.cssText = 'width:100%;max-height:14rem;object-fit:cover;border-radius:.55rem;display:block';
          zone.insertBefore(live, zone.firstChild);
          const icon = zone.querySelector(':scope > span');
          const placeholder = zone.querySelector(':scope > p');
          if (icon) icon.style.display = 'none';
          if (placeholder) placeholder.style.display = 'none';
        }
        live.src = dataUrl;
        ensureNote(zone, false);
      } else if (preview) {
        const img = preview.querySelector('img');
        if (img) img.src = dataUrl;
        ensureNote(preview.querySelector('.authoring-image-actions'), true);
      }

      const asideImg = document.querySelector('.authoring-preview-cover');
      if (asideImg) {
        asideImg.src = dataUrl;
      } else {
        const asidePreview = document.querySelector('.authoring-preview');
        if (asidePreview) {
          const newImg = document.createElement('img');
          newImg.className = 'authoring-preview-cover';
          newImg.src = dataUrl;
          newImg.alt = 'Cover preview';
          asidePreview.insertBefore(newImg, asidePreview.firstChild);
        }
      }
    };
    reader.readAsDataURL(file);
  });
})();
