/* Reference Library — instructor portal (Stage R4-D1).
   Fetches from the R4-B lifecycle endpoints, renders the three-state
   lifecycle, and wires promote/approve/retire with CSRF protection. */
(function () {
  "use strict";

  var root = document.getElementById("refLibrary");
  if (!root) return;

  var csrfToken = root.dataset.csrfToken;
  var urls = JSON.parse(root.dataset.urls);

  var els = {
    search: document.getElementById("ref-search"),
    stats: document.getElementById("ref-stats"),
    loading: document.getElementById("ref-loading"),
    error: document.getElementById("ref-error"),
    errorText: document.getElementById("ref-error-text"),
    retry: document.getElementById("ref-retry"),
    empty: document.getElementById("ref-empty"),
    list: document.getElementById("ref-list"),
    cards: document.getElementById("ref-cards"),
    detailDialog: document.getElementById("ref-detail-dialog"),
    detailTitle: document.getElementById("ref-detail-title"),
    detailBody: document.getElementById("ref-detail-body"),
    detailClose: document.getElementById("ref-detail-close"),
    toast: document.getElementById("ref-toast"),
    countWorking: document.getElementById("ref-count-working"),
    countApproved: document.getElementById("ref-count-approved"),
    countRetired: document.getElementById("ref-count-retired"),
  };

  var references = [];
  var searchQuery = "";

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = String(text || "");
    return div.innerHTML;
  }

  function formatDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function stateLabel(s) {
    return s === "working" ? "Working" : s === "approved" ? "Approved" : s === "retired" ? "Retired" : "Temporary";
  }

  function statusLabel(s) {
    return s === "submitted" ? "Submitted" : "Draft";
  }

  function regimeLabel(code) {
    var map = { EX: "Export", IM: "Import", TN: "Transhipment", TR: "Transit", FI: "FZ Inbound", FO: "FZ Outbound", CO: "Other" };
    return map[code] || code;
  }

  function showToast(message, tone) {
    els.toast.hidden = false;
    els.toast.textContent = message;
    els.toast.setAttribute("data-tone", tone || "");
    setTimeout(function () { els.toast.hidden = true; }, 4000);
  }

  function showState(state) {
    els.loading.hidden = state !== "loading";
    els.error.hidden = state !== "error";
    els.empty.hidden = state !== "empty";
    els.list.hidden = state !== "list";
  }

  function fetchJSON(url, options) {
    return fetch(url, options).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) {
          var err = new Error(data.error || "Request failed");
          err.code = data.code || "";
          throw err;
        }
        return data;
      });
    });
  }

  function canEdit(r) { return r.reference_state === "working"; }
  function canApprove(r) { return r.reference_state === "working" && r.status === "submitted"; }
  function canRetire(r) { return r.reference_state === "approved"; }
  function canSelect(r) { return r.reference_state === "approved"; }
  function canPromote(r) { return r.can_promote === true; }

  function renderLibrary() {
    var filtered = references.filter(function (r) {
      if (!searchQuery) return true;
      var q = searchQuery.toLowerCase();
      var number = (r.ucr_no || r.temp_no || "").toLowerCase();
      var exporter = (r.exporter_name || "").toLowerCase();
      var state = (r.reference_state || "").toLowerCase();
      return number.indexOf(q) !== -1 || exporter.indexOf(q) !== -1 || state.indexOf(q) !== -1;
    });

    var counts = { working: 0, approved: 0, retired: 0 };
    references.forEach(function (r) {
      if (counts[r.reference_state] !== undefined) counts[r.reference_state]++;
    });
    els.countWorking.textContent = counts.working;
    els.countApproved.textContent = counts.approved;
    els.countRetired.textContent = counts.retired;

    if (!filtered.length) {
      showState("empty");
      return;
    }

    els.cards.replaceChildren.apply(els.cards, filtered.map(function (r) {
      var card = document.createElement("div");
      card.className = "ref-card";
      card.setAttribute("role", "listitem");

      var main = document.createElement("div");
      main.className = "ref-card-main";
      var number = document.createElement("div");
      number.className = "ref-card-number";
      number.textContent = r.ucr_no || r.temp_no || "—";
      main.append(number);
      var meta = document.createElement("div");
      meta.className = "ref-card-meta";
      meta.innerHTML =
        '<span class="ref-pill ref-pill--' + escapeHtml(r.reference_state || "temporary") + '">' + escapeHtml(stateLabel(r.reference_state)) + "</span>" +
        ' <span class="ref-pill ref-pill--' + escapeHtml(r.status) + '">' + escapeHtml(statusLabel(r.status)) + "</span>" +
        " " + escapeHtml(regimeLabel(r.regime)) + " · " + escapeHtml(r.exporter_name || "");
      main.append(meta);
      card.append(main);

      var actions = document.createElement("div");
      actions.className = "ref-card-actions";
      if (canApprove(r)) {
        var approveBtn = document.createElement("button");
        approveBtn.type = "button";
        approveBtn.className = "ref-button";
        approveBtn.textContent = "Approve";
        approveBtn.addEventListener("click", function () { mutate("approve", r.id); });
        actions.append(approveBtn);
      }
      if (canRetire(r)) {
        var retireBtn = document.createElement("button");
        retireBtn.type = "button";
        retireBtn.className = "ref-button ref-button--danger";
        retireBtn.textContent = "Retire";
        retireBtn.addEventListener("click", function () {
          if (window.confirm("Retire this reference? It becomes immutable and cannot be selected for authoring.")) {
            mutate("retire", r.id);
          }
        });
        actions.append(retireBtn);
      }
      if (canPromote(r)) {
        var keepBtn = document.createElement("button");
        keepBtn.type = "button";
        keepBtn.className = "ref-button ref-button--primary";
        keepBtn.textContent = "Keep as Reference";
        keepBtn.addEventListener("click", function () { mutate("promote", r.id); });
        actions.append(keepBtn);
      }
      var detailBtn = document.createElement("button");
      detailBtn.type = "button";
      detailBtn.className = "ref-button";
      detailBtn.textContent = "Detail";
      detailBtn.addEventListener("click", function () { openDetail(r.id); });
      actions.append(detailBtn);
      card.append(actions);

      return card;
    }));

    showState("list");
  }

  function mutate(action, recordId) {
    var urlFn = urls[action];
    if (!urlFn || typeof urlFn !== "function") return;
    var btn = event && event.target;
    if (btn) btn.disabled = true;
    fetchJSON(urlFn(recordId), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
        "Accept": "application/json",
      },
      body: "{}",
    }).then(function (data) {
      showToast(action.charAt(0).toUpperCase() + action.slice(1) + " succeeded.", "success");
      return load();
    }).catch(function (error) {
      showToast(error.message || "Request failed.", "error");
    }).finally(function () {
      if (btn) btn.disabled = false;
    });
  }

  function openDetail(recordId) {
    fetchJSON(urls.detail(recordId)).then(function (data) {
      var r = data.reference;
      var bannerClass = r.reference_state === "approved" ? "approved" : r.reference_state === "retired" ? "retired" : "working";
      var bannerText = r.reference_state === "approved"
        ? "Approved references are immutable and can be selected for future authoring."
        : r.reference_state === "retired"
          ? "Retired references are read-only and cannot be selected for authoring."
          : r.status === "draft"
            ? "Working draft. Continue editing through the UCR workflow."
            : "Working reference. Submit and then approve when ready.";

      var html = '<div class="ref-state-banner ref-state-banner--' + bannerClass + '">' + escapeHtml(bannerText) + "</div>";
      html += '<dl class="ref-detail-grid">';
      html += "<dt>Temporary no.</dt><dd>" + escapeHtml(r.temp_no || r.number || "—") + "</dd>";
      html += "<dt>UCR no.</dt><dd>" + escapeHtml(r.ucr_no || "—") + "</dd>";
      html += "<dt>State</dt><dd>" + escapeHtml(stateLabel(r.reference_state)) + "</dd>";
      html += "<dt>Status</dt><dd>" + escapeHtml(statusLabel(r.status)) + "</dd>";
      html += "<dt>Regime</dt><dd>" + escapeHtml(regimeLabel(r.regime)) + "</dd>";
      html += "<dt>Exporter</dt><dd>" + escapeHtml(r.exporter_name || "—") + "</dd>";
      html += "<dt>Created</dt><dd>" + formatDate(r.created_at) + "</dd>";
      html += "<dt>Updated</dt><dd>" + formatDate(r.updated_at) + "</dd>";
      html += "</dl>";

      var actionsHtml = "";
      if (canEdit(r) && r.status === "submitted") {
        actionsHtml += '<button type="button" class="ref-button ref-button--primary" data-action="approve" data-id="' + r.id + '">Approve</button> ';
      }
      if (canRetire(r)) {
        actionsHtml += '<button type="button" class="ref-button ref-button--danger" data-action="retire" data-id="' + r.id + '">Retire</button>';
      }
      if (!actionsHtml) {
        actionsHtml = '<p class="ref-library-empty" style="padding:.5rem">No actions available for this reference.</p>';
      }
      html += '<div class="ref-card-actions" style="margin-top:1rem">' + actionsHtml + "</div>";

      els.detailBody.innerHTML = html;
      els.detailTitle.textContent = "Reference " + (r.ucr_no || r.temp_no || "");

      els.detailBody.querySelectorAll("[data-action]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          mutate(btn.dataset.action, btn.dataset.id);
          els.detailDialog.close();
        });
      });

      els.detailDialog.showModal();
    }).catch(function (error) {
      showToast(error.message || "Failed to load detail.", "error");
    });
  }

  function load() {
    showState("loading");
    return fetchJSON(urls.list).then(function (data) {
      references = data.references || [];
      renderLibrary();
    }).catch(function (error) {
      els.errorText.textContent = error.message || "Failed to load references.";
      showState("error");
    });
  }

  els.search.addEventListener("input", function () {
    searchQuery = els.search.value.trim();
    renderLibrary();
  });

  els.retry.addEventListener("click", load);
  els.detailClose.addEventListener("click", function () { els.detailDialog.close(); });

  load();
})();
