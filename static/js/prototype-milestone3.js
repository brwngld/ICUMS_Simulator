/* Milestone 3 of the UI-first prototype: the mock Demonstration Studio and
 * the mock student experience preview.
 *
 * Everything lives in this browser tab (sessionStorage) — no recording
 * endpoint is ever called, the feature flag is not queried, and the
 * simulator frames are plain GET browsing. Proposed steps come from the
 * scripted sample in hybrid/prototype_data.py; applying them merges into the
 * Milestone 2 lesson store (protoM2Lessons) so the lesson editor and the
 * student preview pick them up on the next screen. Nothing is saved. */
(function () {
  "use strict";

  var STUDIO_KEY = "protoM3Studio";

  function readStore() {
    try { return JSON.parse(sessionStorage.getItem(STUDIO_KEY)) || {}; }
    catch (e) { return {}; }
  }
  function writeStore(store) {
    try { sessionStorage.setItem(STUDIO_KEY, JSON.stringify(store)); }
    catch (e) { /* private mode: the prototype just won't persist */ }
  }
  function entryFor(slug, reset) {
    var store = readStore();
    if (reset || !store[slug]) {
      store[slug] = { state: "idle", revealed: 0, proposals: null, applied: 0 };
      writeStore(store);
    }
    return store[slug];
  }
  function saveEntry(slug, entry) {
    var store = readStore();
    store[slug] = entry;
    writeStore(store);
  }
  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function seed(id) {
    var el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }
  // The server renders the seeded mock lesson; a lesson created in this
  // browser tab only exists in Milestone 2's store, so every page that names
  // the lesson asks the store first. Without this a new lesson opens in the
  // Studio as “Untitled prototype lesson”.
  function lessonFor(root) {
    var slug = root.getAttribute("data-slug");
    return (window.protoM2Get && window.protoM2Get(slug)) || seed("proto-lesson-seed") || {};
  }
  function paintLesson(lesson, kindLabel) {
    var set = function (id, text) {
      var el = document.getElementById(id);
      if (el) el.textContent = text;
    };
    set("proto3-lesson-title", lesson.title);
    set("proto3-crumb-lesson", lesson.title);
    set("proto3-lesson-code", lesson.slug);
    set("proto3-lesson-kind", kindLabel ||
      (lesson.kind === "guided" ? "Guided Material Study" : "Interactive Practical"));
    set("proto-student-title", lesson.title);
    var flag = document.getElementById("proto3-lesson-browser");
    if (flag) flag.hidden = !lesson.created;
  }

  /* ------------------------------------------------------------------ *
   * Studio: mock lifecycle, scripted capture, generated guidance.
   * ------------------------------------------------------------------ */
  function initStudio() {
    var root = document.getElementById("proto-studio");
    if (!root) return;
    var lesson = lessonFor(root);
    paintLesson(lesson);
    var slug = root.getAttribute("data-slug");
    var events = seed("proto-demo-events") || [];
    if (!document.getElementById("proto3-grid")) return;  // Guided lesson: explanation only.
    var entry = entryFor(slug, false);

    var el = function (id) { return document.getElementById(id); };
    var status = el("proto3-status");
    var eventsHost = el("proto3-events");
    var count = el("proto3-count");
    var revealBtn = el("proto3-reveal");
    var goReview = el("proto3-goreview");
    var proposalHost = el("proto3-proposal-list");
    var applyBtn = el("proto3-apply");

    // Tabs — same contract as the shipped studio's own script.
    var show = function (tab) {
      root.querySelectorAll(".view").forEach(function (view) {
        view.classList.toggle("hidden", view.id !== tab);
      });
      root.querySelectorAll(".tab").forEach(function (button) {
        var active = button.getAttribute("data-tab") === tab;
        button.classList.toggle("active", active);
        button.setAttribute("aria-selected", String(active));
      });
    };
    root.querySelectorAll(".tab").forEach(function (button) {
      button.addEventListener("click", function () { show(button.getAttribute("data-tab")); });
    });
    root.querySelectorAll("[data-show]").forEach(function (button) {
      button.addEventListener("click", function () { show(button.getAttribute("data-show")); });
    });

    // Expand mode — the simulator takes the whole row.
    var expand = el("proto3-expand");
    expand.addEventListener("click", function () {
      var wide = el("proto3-grid").classList.toggle("proto3-wide");
      el("proto3-aside").hidden = wide;
      expand.textContent = wide ? "Restore timeline" : "Expand simulator";
    });

    var renderControls = function () {
      var state = entry.state;
      el("proto3-start").disabled = state === "recording" || state === "paused";
      el("proto3-pause").disabled = state !== "recording";
      el("proto3-pause").hidden = state === "paused";
      el("proto3-resume").hidden = state !== "paused";
      el("proto3-stop").disabled = state !== "recording" && state !== "paused";
      el("proto3-reset").disabled = state === "idle";
      revealBtn.disabled = state !== "recording" || entry.revealed >= events.length;
      if (entry.revealed >= events.length && events.length) {
        revealBtn.textContent = "Sample complete — stop the recording";
        revealBtn.disabled = true;
      }
    };

    var renderStatus = function () {
      if (entry.state === "recording") {
        status.className = "status live";
        status.innerHTML = '<span class="recordingDot"></span>Mock recording — the timeline replays a scripted sample. Nothing from the simulator is captured.';
      } else if (entry.state === "paused") {
        status.className = "status";
        status.textContent = "Paused — the scripted sample pauses with the mock session.";
      } else if (entry.state === "stopped") {
        status.className = "status success";
        status.textContent = "Stopped — " + entry.revealed + " sample event(s) shown. Nothing was saved.";
      } else {
        status.className = "status";
        status.textContent = "Idle — mock recording has not started.";
      }
      count.textContent = entry.revealed + (entry.revealed === 1 ? " event" : " events");
    };

    var eventRow = function (event, index) {
      var row = document.createElement("div");
      row.className = "event proto3-event";
      row.innerHTML =
        '<span class="num">' + (index + 1) + '</span><div><span class="eventTitle">' +
        esc(event.label) + ' <span class="proto-flag">mock example</span></span>' +
        '<span class="proto3-code">' + esc(event.code) + ' · ' + esc(event.screen) + '</span></div>';
      return row;
    };

    var renderEvents = function () {
      eventsHost.replaceChildren();
      if (!entry.revealed) {
        eventsHost.className = "empty";
        eventsHost.textContent = "No sample events shown yet.";
        return;
      }
      eventsHost.className = "";
      for (var i = 0; i < entry.revealed; i++) eventsHost.appendChild(eventRow(events[i], i));
    };

    var buildProposals = function () {
      var list = [];
      for (var i = 0; i < entry.revealed; i++) {
        var p = events[i].proposal;
        if (!p) continue;
        list.push({
          screen: p.screen, title: p.title, instruction: p.instruction,
          outcome: p.outcome, hint: p.hint || "",
          condition: p.condition ? { kind: p.condition.kind, detail: p.condition.detail, on: true } : null,
          accepted: true,
        });
      }
      return list;
    };

    var reviewNote = function (message, isError) {
      var note = el("proto3-review-status");
      note.hidden = !message;
      note.className = isError ? "status" : "status success";
      note.textContent = message || "";
    };

    var proposalRow = function (p, index) {
      var row = document.createElement("div");
      row.className = "proto3-proposal" + (p.accepted ? "" : " rejected");
      var condition = p.condition
        ? '<div class="proto3-condition"><label><input type="checkbox" data-p-action="condition-on" data-index="' + index + '"' + (p.condition.on ? " checked" : "") + '> add verification</label>' +
          '<select data-p-field="condition-kind" data-index="' + index + '">' +
          '<option value="saved_record"' + (p.condition.kind === "saved_record" ? " selected" : "") + '>Saved record</option>' +
          '<option value="screen_opened"' + (p.condition.kind === "screen_opened" ? " selected" : "") + '>Screen opened</option></select>' +
          '<input type="text" data-p-field="condition-detail" data-index="' + index + '" value="' + esc(p.condition.detail) + '">' +
          '<span></span></div>'
        : '<p class="helper">No verification proposed for this step.</p>';
      row.innerHTML =
        '<div class="proto3-proposal-top"><label><input type="checkbox" data-p-action="accept" data-index="' + index + '"' + (p.accepted ? " checked" : "") + '></label>' +
        '<span class="proto3-screen">' + esc(p.screen) + '</span>' +
        '<span class="proto3-tools">' +
        '<button type="button" data-p-action="up" data-index="' + index + '"' + (index === 0 ? " disabled" : "") + ' aria-label="Move up">↑</button>' +
        '<button type="button" data-p-action="down" data-index="' + index + '"' + (index === entry.proposals.length - 1 ? " disabled" : "") + ' aria-label="Move down">↓</button>' +
        '<button type="button" data-p-action="remove" data-index="' + index + '">Remove</button></span></div>' +
        '<p class="proto3-label">Title</p><input type="text" data-p-field="title" data-index="' + index + '" value="' + esc(p.title) + '">' +
        '<p class="proto3-label">Instruction</p><textarea data-p-field="instruction" data-index="' + index + '" rows="2">' + esc(p.instruction) + '</textarea>' +
        '<p class="proto3-label">Expected outcome</p><textarea data-p-field="outcome" data-index="' + index + '" rows="2">' + esc(p.outcome) + '</textarea>' +
        '<p class="proto3-label">Hint <span class="proto-flag">real field · not editable in the shipped review</span></p><textarea data-p-field="hint" data-index="' + index + '" rows="1">' + esc(p.hint) + '</textarea>' +
        condition;
      return row;
    };

    var renderProposals = function () {
      el("proto3-captured-count").textContent = String(entry.revealed);
      if (!entry.proposals) {
        proposalHost.className = "empty";
        proposalHost.textContent = "No proposed steps yet. Stop a mock recording to review its sample events.";
        applyBtn.hidden = true;
        goReview.disabled = true;
        return;
      }
      el("proto3-proposed-count").textContent = String(entry.proposals.length);
      proposalHost.className = "";
      proposalHost.replaceChildren.apply(proposalHost, entry.proposals.map(proposalRow));
      applyBtn.hidden = entry.proposals.length === 0 || entry.applied > 0;
      goReview.disabled = entry.state !== "stopped";
    };

    var render = function () {
      renderStatus();
      renderControls();
      renderEvents();
      renderProposals();
      el("proto3-editor-link").textContent = entry.applied
        ? "Continue in this lesson’s Practical Activities →"
        : "Return to this lesson’s Practical Activities";
    };

    // Delegated editing of the proposal rows.
    proposalHost.addEventListener("input", function (event) {
      var field = event.target.getAttribute("data-p-field");
      if (!field || !entry.proposals) return;
      var p = entry.proposals[parseInt(event.target.getAttribute("data-index"), 10)];
      if (!p) return;
      if (field.indexOf("condition") === 0) {
        if (!p.condition) return;
        p.condition[field === "condition-kind" ? "kind" : "detail"] = event.target.value;
      } else {
        p[field] = event.target.value;
      }
      saveEntry(slug, entry);
    });
    proposalHost.addEventListener("change", function (event) {
      var field = event.target.getAttribute("data-p-field");
      if (field === "condition-kind" && entry.proposals) {
        var p = entry.proposals[parseInt(event.target.getAttribute("data-index"), 10)];
        if (p && p.condition) p.condition.kind = event.target.value;
        saveEntry(slug, entry);
      }
    });
    proposalHost.addEventListener("click", function (event) {
      var action = event.target.getAttribute("data-p-action");
      if (!action || !entry.proposals) return;
      var index = parseInt(event.target.getAttribute("data-index"), 10);
      var list = entry.proposals;
      if (action === "accept") list[index].accepted = event.target.checked;
      else if (action === "condition-on") list[index].condition.on = event.target.checked;
      else if (action === "remove") list.splice(index, 1);
      else if (action === "up" || action === "down") {
        var to = index + (action === "up" ? -1 : 1);
        if (to < 0 || to >= list.length) return;
        var tmp = list[index]; list[index] = list[to]; list[to] = tmp;
      }
      saveEntry(slug, entry);
      renderProposals();
    });

    el("proto3-start").addEventListener("click", function () {
      if (entry.state === "idle") { entry.revealed = 0; entry.proposals = null; }
      entry.state = "recording";
      saveEntry(slug, entry); render();
    });
    el("proto3-pause").addEventListener("click", function () { entry.state = "paused"; saveEntry(slug, entry); render(); });
    el("proto3-resume").addEventListener("click", function () { entry.state = "recording"; saveEntry(slug, entry); render(); });
    el("proto3-stop").addEventListener("click", function () {
      entry.state = "stopped";
      entry.proposals = buildProposals();
      saveEntry(slug, entry); render();
    });
    el("proto3-reset").addEventListener("click", function () {
      if (!window.confirm("Discard this mock recording? Nothing has been saved anywhere.")) return;
      entry = entryFor(slug, true);
      saveEntry(slug, entry);
      reviewNote("");
      render();
    });
    revealBtn.addEventListener("click", function () {
      if (entry.state !== "recording" || entry.revealed >= events.length) return;
      entry.revealed += 1;
      saveEntry(slug, entry);
      window.protoToast("Mock event " + entry.revealed + " added to the timeline");
      render();
    });
    goReview.addEventListener("click", function () { show("review"); });

    applyBtn.addEventListener("click", function () {
      var accepted = (entry.proposals || []).filter(function (p) { return p.accepted; });
      if (!accepted.length) { reviewNote("Accept at least one proposed step first.", true); return; }
      lesson.steps = (lesson.steps || []).concat(accepted.map(function (p) {
        return {
          title: p.title.trim(), instruction: p.instruction.trim(),
          outcome: p.outcome.trim(), hint: p.hint.trim(),
          verifications: (p.condition && p.condition.on)
            ? [{ kind: p.condition.kind, detail: p.condition.detail }] : [],
          from_demo: true,
        };
      }));
      window.protoM2Put(lesson);
      entry.applied = accepted.length;
      saveEntry(slug, entry);
      reviewNote("Added " + accepted.length + " mock step(s) to “" + lesson.title + "” in this browser tab.", false);
      applyBtn.hidden = true;
      render();
      if (window.protoToast) window.protoToast("Applied " + accepted.length + " step(s) to the lesson");
    });

    render();
  }

  /* ------------------------------------------------------------------ *
   * Student experience preview — the shipped workspace design, tab-local.
   * ------------------------------------------------------------------ */
  function initStudent() {
    var root = document.getElementById("proto-student");
    if (!root) return;
    var lesson = lessonFor(root);
    if (!lesson || !lesson.title) return;
    paintLesson(lesson);
    var steps = lesson.steps || [];
    var current = 0;

    var left = document.getElementById("proto3-left");
    var html = "";
    if (lesson.summary) html += '<article class="hyb-card"><div class="lrn-copy"><p>' + esc(lesson.summary) + "</p></div></article>";
    html += '<article class="hyb-card"><p class="hyb-card-label">Theory</p><div class="hyb-card-body"><div class="lrn-copy">' +
      (lesson.theory_html || "<p>Theory not written yet.</p>") + "</div></div></article>";
    if (steps.length) {
      html += '<article class="hyb-card"><p class="hyb-card-label">Practical journey · <span id="proto3-progress">Step 1 of ' + steps.length +
        '</span></p><ol class="hyb-journey" id="proto3-journey">' +
        steps.map(function (s, i) {
          return '<li data-journey="' + i + '"' + (i === 0 ? ' class="now"' : "") + "><span>" + (i + 1) +
            "</span><small>" + esc(s.title || "Untitled step") + "</small></li>";
        }).join("") + "</ol></article>";
      steps.forEach(function (s, i) {
        html += '<article class="hyb-card hyb-card-step" data-step-card="' + i + '"' + (i === 0 ? "" : " hidden") + ">" +
          '<p class="hyb-card-label">Step ' + (i + 1) + " of " + steps.length + "</p>" +
          '<h2 class="hyb-card-title">' + esc(s.title || "Untitled step") + "</h2>" +
          (s.instruction ? '<div class="hyb-card-text"><strong>What to do</strong><div class="lrn-copy"><p>' + esc(s.instruction) + "</p></div></div>" : "") +
          (s.outcome ? '<div class="hyb-outcome"><strong>Expected outcome</strong><div class="lrn-copy"><p>' + esc(s.outcome) + "</p></div></div>" : "") +
          (s.hint ? '<div class="hyb-hint" data-hint="' + i + '" hidden><strong>Hint</strong><div class="lrn-copy"><p>' + esc(s.hint) + "</p></div></div>" : "") +
          '<p class="hyb-feedback" data-feedback="' + i + '">Complete the step in the simulator, then check your work — in this prototype the check is labelled and verifies nothing.</p></article>';
      });
    } else {
      html += '<article class="hyb-card"><p class="hyb-card-label">Practical journey</p><div class="lrn-copy"><p>This lesson has no practical steps yet.</p></div></article>';
    }
    left.innerHTML = html;
    document.getElementById("proto3-actions").hidden = !steps.length;

    var showStep = function (index) {
      current = Math.max(0, Math.min(steps.length - 1, index));
      left.querySelectorAll("[data-step-card]").forEach(function (card) {
        card.hidden = parseInt(card.getAttribute("data-step-card"), 10) !== current;
      });
      left.querySelectorAll("[data-journey]").forEach(function (item) {
        var i = parseInt(item.getAttribute("data-journey"), 10);
        item.className = i < current ? "done" : i === current ? "now" : "";
      });
      var progress = document.getElementById("proto3-progress");
      if (progress) progress.textContent = "Step " + (current + 1) + " of " + steps.length;
      document.getElementById("proto3-prev").disabled = current === 0;
      document.getElementById("proto3-next").disabled = current === steps.length - 1;
    };
    if (steps.length) showStep(0);

    document.getElementById("proto3-prev").addEventListener("click", function () { showStep(current - 1); });
    document.getElementById("proto3-next").addEventListener("click", function () { showStep(current + 1); });
    document.getElementById("proto3-hint").addEventListener("click", function () {
      var hint = left.querySelector('[data-hint="' + current + '"]');
      if (hint) hint.hidden = !hint.hidden;
      else window.protoToast("This step has no hint (hint editing lives in the studio review)");
    });
    document.getElementById("proto3-check").addEventListener("click", function () {
      var feedback = left.querySelector('[data-feedback="' + current + '"]');
      if (!feedback) return;
      feedback.className = "hyb-feedback proto3-check-note";
      feedback.textContent = "Mock check only — the real workspace verifies this step against simulator records through a lesson attempt. This prototype opened no attempt and verified nothing.";
    });

    // Panel buttons — mirrors the shipped workspace switch: it sets an
    // attribute on the grid and the CSS hides the other pane only below the
    // desktop breakpoint, so a wide screen always shows both.
    var grid = document.getElementById("proto3-split");
    grid.setAttribute("data-proto-pane-mode", "theory");
    document.querySelectorAll("[data-proto-pane]").forEach(function (button) {
      button.addEventListener("click", function () {
        var pane = button.getAttribute("data-proto-pane");
        grid.setAttribute("data-proto-pane-mode", pane);
        document.querySelectorAll("[data-proto-pane]").forEach(function (other) {
          other.setAttribute("aria-pressed", String(other === button));
        });
      });
    });

    // Divider — same drag contract as the shipped workspace handle.
    var divider = document.getElementById("proto3-divider");
    var apply = function (pct) {
      grid.style.setProperty("--hyb-left", Math.min(70, Math.max(20, pct)) + "%");
    };
    var dragging = false;
    divider.addEventListener("pointerdown", function (event) {
      dragging = true; divider.setPointerCapture(event.pointerId);
    });
    divider.addEventListener("pointermove", function (event) {
      if (!dragging) return;
      var rect = grid.getBoundingClientRect();
      apply(((event.clientX - rect.left) / rect.width) * 100);
    });
    divider.addEventListener("pointerup", function () { dragging = false; });
    divider.addEventListener("dblclick", function () { apply(35); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initStudio();
    initStudent();
  });
})();
