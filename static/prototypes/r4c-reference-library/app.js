(() => {
  "use strict";

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  let references = structuredClone ? structuredClone(REFERENCES) : JSON.parse(JSON.stringify(REFERENCES));
  let demonstrations = structuredClone ? structuredClone(DEMONSTRATION_UCRS) : JSON.parse(JSON.stringify(DEMONSTRATION_UCRS));

  const state = {
    filter: "all",
    search: "",
    sort: "updated_desc",
    detailId: null,
    confirmAction: null,
  };

  const els = {
    statsTotal: document.getElementById("stat-total"),
    statsWorking: document.getElementById("stat-working"),
    statsApproved: document.getElementById("stat-approved"),
    statsRetired: document.getElementById("stat-retired"),
    libraryContent: document.getElementById("library-content"),
    loadingMessage: document.getElementById("loading-message"),
    searchInput: document.getElementById("search-input"),
    sortSelect: document.getElementById("sort-select"),
    tabs: document.querySelectorAll(".proto-tab"),
    detailOverlay: document.getElementById("detail-overlay"),
    detailDrawer: document.getElementById("detail-drawer"),
    detailBody: document.getElementById("detail-body"),
    addDialogOverlay: document.getElementById("add-dialog-overlay"),
    addDialogContent: document.getElementById("add-dialog-content"),
    confirmDialogOverlay: document.getElementById("confirm-dialog-overlay"),
    confirmTitle: document.getElementById("confirm-title"),
    confirmMessage: document.getElementById("confirm-message"),
    confirmActionBtn: document.getElementById("confirm-action"),
    toastRegion: document.getElementById("toast-region"),
    addReferenceBtn: document.getElementById("btn-add-reference"),
  };

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  const formatDate = (iso) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDateOnly = (iso) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  const stateLabel = (referenceState) => {
    switch (referenceState) {
      case REFERENCE_STATE.WORKING: return "Working";
      case REFERENCE_STATE.APPROVED: return "Approved";
      case REFERENCE_STATE.RETIRED: return "Retired";
      default: return "Temporary";
    }
  };

  const statusLabel = (status) => {
    switch (status) {
      case UCR_STATUS.DRAFT: return "Draft";
      case UCR_STATUS.SUBMITTED: return "Submitted";
      default: return status || "—";
    }
  };

  const regimeLabel = (code) => {
    switch (code) {
      case "IM": return "Import";
      case "EX": return "Export";
      default: return code || "—";
    }
  };

  const escapeHtml = (text) => {
    const div = document.createElement("div");
    div.textContent = text ?? "";
    return div.innerHTML;
  };

  const generateId = (prefix = "id") => `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

  const focusableSelectors = "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])";

  // ---------------------------------------------------------------------------
  // Filtering / sorting
  // ---------------------------------------------------------------------------

  function filteredReferences() {
    let list = references.filter((r) => {
      if (state.filter !== "all" && r.reference_state !== REFERENCE_STATE[state.filter.toUpperCase()]) return false;
      if (!state.search) return true;
      const q = state.search.toLowerCase();
      return (
        (r.ucr_no || "").toLowerCase().includes(q) ||
        (r.temp_no || "").toLowerCase().includes(q) ||
        (r.exporter_name || "").toLowerCase().includes(q) ||
        (r.importer_name || "").toLowerCase().includes(q) ||
        (r.owner_name || "").toLowerCase().includes(q) ||
        regimeLabel(r.regime).toLowerCase().includes(q)
      );
    });

    list.sort((a, b) => {
      switch (state.sort) {
        case "updated_asc": return new Date(a.updated_at) - new Date(b.updated_at);
        case "updated_desc": return new Date(b.updated_at) - new Date(a.updated_at);
        case "ucr_asc": return (a.ucr_no || a.temp_no || "").localeCompare(b.ucr_no || b.temp_no || "");
        case "ucr_desc": return (b.ucr_no || b.temp_no || "").localeCompare(a.ucr_no || a.temp_no || "");
        case "created_desc": return new Date(b.created_at) - new Date(a.created_at);
        default: return 0;
      }
    });

    return list;
  }

  // ---------------------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------------------

  function renderStats() {
    const counts = references.reduce((acc, r) => {
      acc.total += 1;
      if (r.reference_state === REFERENCE_STATE.WORKING) acc.working += 1;
      if (r.reference_state === REFERENCE_STATE.APPROVED) acc.approved += 1;
      if (r.reference_state === REFERENCE_STATE.RETIRED) acc.retired += 1;
      return acc;
    }, { total: 0, working: 0, approved: 0, retired: 0 });

    els.statsTotal.textContent = counts.total;
    els.statsWorking.textContent = counts.working;
    els.statsApproved.textContent = counts.approved;
    els.statsRetired.textContent = counts.retired;
  }

  function renderLibrary() {
    const list = filteredReferences();

    if (list.length === 0) {
      els.libraryContent.innerHTML = `
        <div class="proto-empty">
          <p class="proto-empty__title">No references found</p>
          <p>Try a different filter or search term.</p>
        </div>
      `;
      return;
    }

    const tableRows = list.map((r) => `
      <tr data-id="${escapeHtml(r.id)}" tabindex="0" role="button" aria-label="Open details for ${escapeHtml(r.temp_no)}">
        <td class="proto-table__cell--nowrap proto-table__cell--ucr">${escapeHtml(r.ucr_no || r.temp_no)}</td>
        <td><span class="proto-pill proto-pill--${r.reference_state || "temporary"}">${stateLabel(r.reference_state)}</span></td>
        <td><span class="proto-pill proto-pill--${r.status}">${statusLabel(r.status)}</span></td>
        <td>${escapeHtml(regimeLabel(r.regime))}</td>
        <td>${escapeHtml(r.exporter_name)}</td>
        <td>${escapeHtml(r.importer_name)}</td>
        <td class="proto-table__cell--nowrap">${escapeHtml(r.owner_name)}</td>
        <td class="proto-table__cell--nowrap">${formatDateOnly(r.updated_at)}</td>
        <td>
          <div class="proto-actions">
            ${renderRowActions(r)}
          </div>
        </td>
      </tr>
    `).join("");

    const cards = list.map((r) => `
      <article class="proto-card" data-id="${escapeHtml(r.id)}" tabindex="0" role="button" aria-label="Open details for ${escapeHtml(r.temp_no)}">
        <div class="proto-card__head">
          <div>
            <h3 class="proto-card__title">${escapeHtml(r.ucr_no || r.temp_no)}</h3>
            <p class="proto-card__meta">${escapeHtml(r.exporter_name)} → ${escapeHtml(r.importer_name)}</p>
          </div>
          <span class="proto-pill proto-pill--${r.reference_state || "temporary"}">${stateLabel(r.reference_state)}</span>
        </div>
        <div class="proto-card__row"><span class="proto-card__label">Status</span><span class="proto-card__value"><span class="proto-pill proto-pill--${r.status}">${statusLabel(r.status)}</span></span></div>
        <div class="proto-card__row"><span class="proto-card__label">Regime</span><span class="proto-card__value">${escapeHtml(regimeLabel(r.regime))}</span></div>
        <div class="proto-card__row"><span class="proto-card__label">Owner</span><span class="proto-card__value">${escapeHtml(r.owner_name)}</span></div>
        <div class="proto-card__row"><span class="proto-card__label">Updated</span><span class="proto-card__value">${formatDateOnly(r.updated_at)}</span></div>
        <div class="proto-card__actions">
          ${renderRowActions(r)}
        </div>
      </article>
    `).join("");

    els.libraryContent.innerHTML = `
      <div class="proto-table-wrap">
        <table class="proto-table">
          <thead>
            <tr>
              <th>UCR / Temp no.</th>
              <th>Reference state</th>
              <th>UCR status</th>
              <th>Regime</th>
              <th>Exporter</th>
              <th>Importer</th>
              <th>Owner</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${tableRows}
          </tbody>
        </table>
      </div>
      <div class="proto-cards" aria-label="Reference cards">
        ${cards}
      </div>
    `;
  }

  function renderRowActions(r) {
    const actions = [];
    if (r.reference_state === REFERENCE_STATE.WORKING) {
      if (r.status === UCR_STATUS.DRAFT) {
        actions.push(`<button type="button" class="proto-button proto-button--small" data-action="edit" data-id="${escapeHtml(r.id)}">Continue as draft</button>`);
      }
      if (r.status === UCR_STATUS.SUBMITTED) {
        actions.push(`<button type="button" class="proto-button proto-button--small" data-action="approve" data-id="${escapeHtml(r.id)}">Approve</button>`);
      }
    }
    if (r.reference_state === REFERENCE_STATE.APPROVED) {
      actions.push(`<button type="button" class="proto-button proto-button--small" data-action="select" data-id="${escapeHtml(r.id)}">Select reference</button>`);
      actions.push(`<button type="button" class="proto-button proto-button--small proto-button--danger" data-action="retire" data-id="${escapeHtml(r.id)}">Retire</button>`);
    }
    return actions.join("");
  }

  function renderDetail(referenceId) {
    const r = references.find((x) => x.id === referenceId);
    if (!r) return;

    const immutable = [REFERENCE_STATE.APPROVED, REFERENCE_STATE.RETIRED].includes(r.reference_state);
    const sourceHtml = r.source_session
      ? `
        <h3 class="proto-section-title">Source demonstration</h3>
        <div class="proto-source-card">
          <p><strong>${escapeHtml(r.source_session.lesson_title)}</strong></p>
          <p>Programme: ${escapeHtml(r.source_session.programme)}</p>
          <p>Instructor: ${escapeHtml(r.source_session.instructor)}</p>
          <p>Recorded: ${formatDate(r.source_session.started_at)} — ${formatDate(r.source_session.stopped_at)}</p>
        </div>
      `
      : `<h3 class="proto-section-title">Source demonstration</h3><p class="proto-muted">No source demonstration recorded.</p>`;

    const actions = [];
    if (r.reference_state === REFERENCE_STATE.WORKING) {
      if (r.status === UCR_STATUS.DRAFT) {
        actions.push(`<button type="button" class="proto-button proto-button--primary" data-action="edit" data-id="${escapeHtml(r.id)}">Continue as draft</button>`);
      }
      if (r.status === UCR_STATUS.SUBMITTED) {
        actions.push(`<button type="button" class="proto-button proto-button--primary" data-action="approve" data-id="${escapeHtml(r.id)}">Approve reference</button>`);
      }
    }
    if (r.reference_state === REFERENCE_STATE.APPROVED) {
      actions.push(`<button type="button" class="proto-button proto-button--primary" data-action="select" data-id="${escapeHtml(r.id)}">Select reference</button>`);
      actions.push(`<button type="button" class="proto-button proto-button--danger" data-action="retire" data-id="${escapeHtml(r.id)}">Retire reference</button>`);
    }

    const bannerClass = r.reference_state === REFERENCE_STATE.APPROVED
      ? "approved"
      : r.reference_state === REFERENCE_STATE.RETIRED
        ? "retired"
        : "working";

    const bannerText = r.reference_state === REFERENCE_STATE.APPROVED
      ? "Approved references are immutable and can be selected for future authoring."
      : r.reference_state === REFERENCE_STATE.RETIRED
        ? "Retired references are read-only and cannot be selected for authoring."
        : r.status === UCR_STATUS.DRAFT
          ? "Working draft. Continue editing through the UCR workflow."
          : "Working reference. Submit and then approve when ready.";

    els.detailBody.innerHTML = `
      <div class="proto-state-banner proto-state-banner--${bannerClass}">
        ${escapeHtml(bannerText)}
      </div>
      <h3 class="proto-section-title">Reference details</h3>
      <dl class="proto-detail-grid">
        <dt>Temporary no.</dt><dd>${escapeHtml(r.temp_no)}</dd>
        <dt>UCR no.</dt><dd>${escapeHtml(r.ucr_no || "—")}</dd>
        <dt>Reference state</dt><dd><span class="proto-pill proto-pill--${r.reference_state || "temporary"}">${stateLabel(r.reference_state)}</span></dd>
        <dt>UCR status</dt><dd><span class="proto-pill proto-pill--${r.status}">${statusLabel(r.status)}</span></dd>
        <dt>Regime</dt><dd>${escapeHtml(regimeLabel(r.regime))}</dd>
        <dt>Exporter</dt><dd>${escapeHtml(r.exporter_name)}</dd>
        <dt>Importer</dt><dd>${escapeHtml(r.importer_name)}</dd>
        <dt>Owner</dt><dd>${escapeHtml(r.owner_name)}</dd>
        <dt>Created</dt><dd>${formatDate(r.created_at)}</dd>
        <dt>Updated</dt><dd>${formatDate(r.updated_at)}</dd>
        <dt>Submitted</dt><dd>${formatDate(r.submitted_at)}</dd>
      </dl>
      ${sourceHtml}
      ${immutable ? "" : `<div class="proto-detail-actions">${actions.join("")}</div>`}
      ${immutable && actions.length ? `<div class="proto-detail-actions">${actions.join("")}</div>` : ""}
    `;

    document.getElementById("detail-title").textContent = `Reference ${r.ucr_no || r.temp_no}`;
  }

  function renderAddDialog() {
    const eligible = demonstrations.filter((d) => d.eligible);
    const ineligible = demonstrations.filter((d) => !d.eligible);

    const renderItem = (d, eligible) => `
      <div class="proto-dialog-item ${eligible ? "" : "is-ineligible"}">
        <label>
          <input type="radio" name="selected-demo" value="${escapeHtml(d.id)}" ${eligible ? "" : "disabled"}>
          <div>
            <strong>${escapeHtml(d.temp_no)}</strong>
            <p class="proto-dialog-item__meta">${escapeHtml(d.lesson_title)} · ${formatDate(d.recorded_at)} · ${statusLabel(d.status)}${d.ucr_no ? " · " + escapeHtml(d.ucr_no) : ""}</p>
            ${d.ineligible_reason ? `<p class="proto-dialog-item__meta" style="color:var(--proto-danger)">${escapeHtml(d.ineligible_reason)}</p>` : ""}
          </div>
        </label>
      </div>
    `;

    els.addDialogContent.innerHTML = `
      ${eligible.length ? `<p class="proto-section-title">Eligible demonstrations</p>${eligible.map((d) => renderItem(d, true)).join("")}` : ""}
      ${ineligible.length ? `<p class="proto-section-title" style="margin-top:1rem">Unavailable</p>${ineligible.map((d) => renderItem(d, false)).join("")}` : ""}
      ${!demonstrations.length ? `<p class="proto-empty">No demonstration UCRs are available.</p>` : ""}
    `;
  }

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  function openDetail(referenceId) {
    state.detailId = referenceId;
    renderDetail(referenceId);
    els.detailOverlay.hidden = false;
    els.detailOverlay.setAttribute("aria-hidden", "false");
    trapFocus(els.detailDrawer);
    setTimeout(() => els.detailDrawer.focus(), 0);
  }

  function closeDetail() {
    els.detailOverlay.hidden = true;
    els.detailOverlay.setAttribute("aria-hidden", "true");
    state.detailId = null;
  }

  function openAddDialog() {
    renderAddDialog();
    els.addDialogOverlay.hidden = false;
    els.addDialogOverlay.setAttribute("aria-hidden", "false");
    trapFocus(document.getElementById("add-dialog"));
  }

  function closeAddDialog() {
    els.addDialogOverlay.hidden = true;
    els.addDialogOverlay.setAttribute("aria-hidden", "true");
  }

  function confirmAction(title, message, action, confirmLabel = "Confirm", variant = "primary") {
    els.confirmTitle.textContent = title;
    els.confirmMessage.textContent = message;
    els.confirmActionBtn.textContent = confirmLabel;
    els.confirmActionBtn.className = `proto-button ${variant === "danger" ? "proto-button--danger" : ""}`;
    state.confirmAction = action;
    els.confirmDialogOverlay.hidden = false;
    els.confirmDialogOverlay.setAttribute("aria-hidden", "false");
    trapFocus(document.getElementById("confirm-dialog"));
    setTimeout(() => els.confirmActionBtn.focus(), 0);
  }

  function closeConfirmDialog() {
    els.confirmDialogOverlay.hidden = true;
    els.confirmDialogOverlay.setAttribute("aria-hidden", "true");
    state.confirmAction = null;
  }

  function performConfirm() {
    if (state.confirmAction) state.confirmAction();
    closeConfirmDialog();
  }

  function approveReference(referenceId) {
    const r = references.find((x) => x.id === referenceId);
    if (!r) return;
    if (r.reference_state !== REFERENCE_STATE.WORKING || r.status !== UCR_STATUS.SUBMITTED) {
      showToast("Only submitted working references can be approved.", "info");
      return;
    }
    r.reference_state = REFERENCE_STATE.APPROVED;
    r.updated_at = new Date().toISOString();
    refresh();
    showToast(`Reference ${r.ucr_no || r.temp_no} approved.`, "success");
  }

  function retireReference(referenceId) {
    const r = references.find((x) => x.id === referenceId);
    if (!r) return;
    if (r.reference_state !== REFERENCE_STATE.APPROVED) {
      showToast("Only approved references can be retired.", "info");
      return;
    }
    r.reference_state = REFERENCE_STATE.RETIRED;
    r.updated_at = new Date().toISOString();
    refresh();
    showToast(`Reference ${r.ucr_no || r.temp_no} retired.`, "success");
  }

  function continueAsDraft(referenceId) {
    const r = references.find((x) => x.id === referenceId);
    if (!r) return;
    if (r.reference_state !== REFERENCE_STATE.WORKING || r.status !== UCR_STATUS.DRAFT) {
      showToast("Only working draft references can be continued.", "info");
      return;
    }
    showToast(`Opening UCR editor for ${r.ucr_no || r.temp_no} (prototype only).`, "info");
  }

  function selectReference(referenceId) {
    const r = references.find((x) => x.id === referenceId);
    if (!r) return;
    if (r.reference_state !== REFERENCE_STATE.APPROVED) {
      showToast("Only approved references can be selected for authoring.", "info");
      return;
    }
    showToast(`Selected ${r.ucr_no || r.temp_no} for authoring (prototype only).`, "info");
  }

  function keepAsReference(demoId) {
    const demo = demonstrations.find((d) => d.id === demoId);
    if (!demo || !demo.eligible) {
      showToast("This demonstration cannot be kept as a reference.", "info");
      return;
    }

    const newRef = {
      id: generateId("ref"),
      temp_no: demo.temp_no,
      ucr_no: demo.ucr_no || "",
      status: demo.status,
      reference_state: REFERENCE_STATE.WORKING,
      regime: "IM",
      exporter_name: "To be confirmed",
      importer_name: "To be confirmed",
      owner_name: "Kwame Asante",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      submitted_at: demo.status === UCR_STATUS.SUBMITTED ? demo.recorded_at : null,
      source_session: {
        id: generateId("sess"),
        lesson_title: demo.lesson_title,
        programme: "Customs Clearance Fundamentals",
        started_at: demo.recorded_at,
        stopped_at: demo.recorded_at,
        instructor: "Kwame Asante",
      },
    };

    references.unshift(newRef);
    demo.eligible = false;
    demo.ineligible_reason = "This demonstration has already been retained as a reference.";
    closeAddDialog();
    refresh();
    showToast(`Kept ${demo.temp_no} as a working reference.`, "success");
  }

  function refresh() {
    renderStats();
    renderLibrary();
    if (state.detailId) renderDetail(state.detailId);
  }

  // ---------------------------------------------------------------------------
  // Toast
  // ---------------------------------------------------------------------------

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `proto-toast proto-toast--${type}`;
    toast.textContent = message;
    els.toastRegion.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  // ---------------------------------------------------------------------------
  // Focus management
  // ---------------------------------------------------------------------------

  let focusTrapCleanup = null;

  function trapFocus(container) {
    if (focusTrapCleanup) focusTrapCleanup();

    const focusables = Array.from(container.querySelectorAll(focusableSelectors));
    const first = focusables[0];
    const last = focusables[focusables.length - 1];

    const handleKey = (e) => {
      if (e.key !== "Tab") return;
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    container.addEventListener("keydown", handleKey);
    focusTrapCleanup = () => container.removeEventListener("keydown", handleKey);
  }

  // ---------------------------------------------------------------------------
  // Theme
  // ---------------------------------------------------------------------------

  function initTheme() {
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.body.setAttribute("data-theme", prefersDark ? "dark" : "light");
  }

  // ---------------------------------------------------------------------------
  // Events
  // ---------------------------------------------------------------------------

  function onActionClick(action, id) {
    switch (action) {
      case "approve":
        confirmAction(
          "Approve reference",
          "Approved references become immutable and can be selected for future authoring. This cannot be undone.",
          () => approveReference(id),
          "Approve",
          "primary"
        );
        break;
      case "retire":
        confirmAction(
          "Retire reference",
          "Retired references are read-only and cannot be selected for authoring. This cannot be undone.",
          () => retireReference(id),
          "Retire",
          "danger"
        );
        break;
      case "edit":
        continueAsDraft(id);
        break;
      case "select":
        selectReference(id);
        break;
    }
  }

  function bindEvents() {
    els.searchInput.addEventListener("input", (e) => {
      state.search = e.target.value.trim();
      renderLibrary();
    });

    els.sortSelect.addEventListener("change", (e) => {
      state.sort = e.target.value;
      renderLibrary();
    });

    els.tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        els.tabs.forEach((t) => {
          t.classList.remove("is-active");
          t.setAttribute("aria-selected", "false");
        });
        tab.classList.add("is-active");
        tab.setAttribute("aria-selected", "true");
        state.filter = tab.dataset.filter;
        renderLibrary();
      });
    });

    els.libraryContent.addEventListener("click", (e) => {
      const actionBtn = e.target.closest("[data-action]");
      if (actionBtn) {
        e.stopPropagation();
        onActionClick(actionBtn.dataset.action, actionBtn.dataset.id);
        return;
      }
      const row = e.target.closest("[data-id]");
      if (row) openDetail(row.dataset.id);
    });

    els.detailBody.addEventListener("click", (e) => {
      const actionBtn = e.target.closest("[data-action]");
      if (actionBtn) {
        e.stopPropagation();
        onActionClick(actionBtn.dataset.action, actionBtn.dataset.id);
      }
    });

    els.libraryContent.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        const row = e.target.closest("[data-id]");
        if (row) {
          e.preventDefault();
          openDetail(row.dataset.id);
        }
      }
    });

    els.detailOverlay.addEventListener("click", (e) => {
      if (e.target.closest("[data-close='detail']")) closeDetail();
    });

    els.addDialogOverlay.addEventListener("click", (e) => {
      if (e.target.closest("[data-close='add']")) closeAddDialog();
    });

    els.addReferenceBtn.addEventListener("click", openAddDialog);

    els.addDialogContent.addEventListener("change", (e) => {
      if (e.target.name === "selected-demo") {
        keepAsReference(e.target.value);
      }
    });

    els.confirmDialogOverlay.addEventListener("click", (e) => {
      if (e.target.closest("[data-close='confirm']")) closeConfirmDialog();
      if (e.target.closest("#confirm-action")) performConfirm();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (!els.confirmDialogOverlay.hidden) closeConfirmDialog();
        else if (!els.addDialogOverlay.hidden) closeAddDialog();
        else if (!els.detailOverlay.hidden) closeDetail();
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------

  function init() {
    initTheme();
    bindEvents();

    // Simulate a short loading delay to demonstrate the loading state.
    setTimeout(() => {
      els.loadingMessage.remove();
      refresh();
    }, 400);
  }

  init();
})();
