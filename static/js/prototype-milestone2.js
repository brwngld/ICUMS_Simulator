/* Milestone 2 of the UI-first prototype: lesson authoring mock.
 *
 * All state lives in this browser tab (sessionStorage) — the server never
 * receives any of it. Shared by the module workspace (merging browser-made
 * lessons into the grid), the lesson editor (both provisional kinds) and the
 * instructor preview. Nothing here posts to a production endpoint. */
(function () {
  "use strict";

  var STORE_KEY = "protoM2Lessons";

  function readStore() {
    try { return JSON.parse(sessionStorage.getItem(STORE_KEY)) || {}; }
    catch (e) { return {}; }
  }
  function writeStore(store) {
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify(store)); }
    catch (e) { /* private mode: the prototype just won't persist */ }
  }
  window.protoM2Get = function (slug) { return readStore()[slug] || null; };
  window.protoM2Put = function (lesson) {
    var store = readStore();
    store[lesson.slug] = lesson;
    writeStore(store);
  };

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function slugify(value) {
    return String(value || "").toLowerCase()
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) ||
      "lesson-" + Date.now().toString(36);
  }
  function blankLesson(slug, title, kind) {
    return {
      slug: slug, kind: kind, title: title, summary: "", objectives: [],
      theory_html: "", materials: [], checks: [],
      procedure: kind === "interactive" ? "Unique Consignment Reference" : "",
      steps: [], created: true,
    };
  }
  window.protoM2Blank = blankLesson;
  window.protoM2Slugify = slugify;

  /* ------------------------------------------------------------------ *
   * Module workspace: browser-made lessons appear as extra rows.
   * ------------------------------------------------------------------ */
  function initModule() {
    var grid = document.getElementById("proto-lesson-grid");
    if (!grid) return;
    var seeded = {};
    grid.querySelectorAll("[data-slug]").forEach(function (row) {
      seeded[row.getAttribute("data-slug")] = true;
    });
    var store = readStore();
    Object.keys(store).forEach(function (slug) {
      if (seeded[slug]) refreshSeededCard(slug, store[slug]);
      else grid.prepend(lessonCard(store[slug]));
    });
    var stat = document.getElementById("proto-stat-lessons");
    if (stat) stat.textContent = grid.querySelectorAll("[data-slug]").length;

    var dialog = document.getElementById("lesson-dialog");
    if (dialog) {
      dialog.querySelector("form").addEventListener("submit", function () {
        var title = dialog.querySelector("input[name=title]").value.trim();
        var kind = dialog.querySelector("select[name=lesson_type]").value
          .toLowerCase().indexOf("guided") === 0 ? "guided" : "interactive";
        if (!title) return;
        var lesson = blankLesson(slugify(title), title, kind);
        window.protoM2Put(lesson);
        grid.prepend(lessonCard(lesson));
        var stat = document.getElementById("proto-stat-lessons");
        if (stat) stat.textContent = grid.querySelectorAll("[data-slug]").length;
      });
    }
  }

  // A seeded row keeps its own markup but must show what this tab saved for
  // it — otherwise a lesson edited or filled from the Studio looks unchanged.
  function refreshSeededCard(slug, lesson) {
    var card = document.querySelector('#proto-lesson-grid [data-slug="' + CSS.escape(slug) + '"]');
    if (!card) return;
    var steps = card.querySelector("[data-row-steps]");
    if (steps) steps.textContent = lesson.steps.length;
    var theory = card.querySelector("[data-row-theory]");
    if (theory) {
      theory.textContent = lesson.theory_html && lesson.theory_html.replace(/<[^>]+>/g, "").trim()
        ? "theory written" : "theory not written yet";
    }
    var title = card.querySelector("h3");
    if (title && !title.querySelector(".proto-flag")) {
      title.insertAdjacentHTML("beforeend", ' <span class="proto-flag">edited in this tab</span>');
    }
  }

  function lessonCard(lesson) {    var card = document.createElement("article");
    card.className = "authoring-card ws-course-card";
    card.setAttribute("data-slug", lesson.slug);
    var kindLabel = lesson.kind === "guided" ? "Guided Practical" : "Interactive Practical";
    var kindChip = lesson.kind === "guided" ? "ws-chip--retired" : "ws-chip--draft";
    var theory = lesson.theory_html && lesson.theory_html.replace(/<[^>]+>/g, "").trim()
      ? "theory written" : "theory not written yet";
    var href = EDITOR_URL + "?lesson=" + encodeURIComponent(lesson.slug) +
      "&kind=" + lesson.kind;
    card.innerHTML =
      '<div class="ws-course-top"><div>' +
      '<h3>' + esc(lesson.title) + ' <span class="proto-flag">browser-only</span></h3>' +
      '<p class="ws-course-code">Lesson code · <code>' + esc(lesson.slug) + '</code></p>' +
      '</div><span class="ws-chip ' + kindChip + '">' + kindLabel + '</span></div>' +
      '<div class="ws-course-meta">' +
      '<span><b>' + lesson.steps.length + '</b> step' + (lesson.steps.length === 1 ? "" : "s") + '</span>' +
      '<span>' + theory + '</span>' +
      (lesson.kind === "guided" ? '<span>Demonstration Studio applies to Interactive Practical lessons</span>' : "") + '</div>' +
      '<div class="ws-course-foot">' +
      (lesson.kind === "interactive" && STUDIO_URL
        ? '<a class="authoring-secondary" href="' + STUDIO_URL + "?lesson=" +
          encodeURIComponent(lesson.slug) + "&kind=interactive\">Open Demonstration Studio</a>"
        : "") +
      '<a class="authoring-primary" href="' + href + '">Full editor</a>' +
      '<button class="authoring-secondary" type="button" data-proto-remove="' + esc(lesson.slug) + '">Remove</button>' +
      '</div>';
    return card;
  }

  var EDITOR_URL = "";
  var gridRemove = function () {
    document.addEventListener("click", function (event) {
      var btn = event.target.closest("[data-proto-remove]");
      if (!btn) return;
      var slug = btn.getAttribute("data-proto-remove");
      var store = readStore();
      delete store[slug];
      writeStore(store);
      var card = document.querySelector('#proto-lesson-grid [data-slug="' + CSS.escape(slug) + '"]');
      if (card) card.remove();
      if (window.protoToast) window.protoToast('Removed “' + slug + '” from this browser tab');
    });
  };

  /* ------------------------------------------------------------------ *
   * Lesson editor.
   * ------------------------------------------------------------------ */
  var state = null;

  function seedFromPage() {
    var el = document.getElementById("proto-lesson-seed");
    return el ? JSON.parse(el.textContent) : null;
  }

  function initEditor() {
    var root = document.getElementById("proto-editor");
    if (!root) return;
    var seed = seedFromPage();
    state = window.protoM2Get(seed.slug) || seed;
    root.dataset.slug = state.slug;
    // A lesson created in this tab is unknown to the server, so the page it
    // opens on must be re-titled from the store rather than left on the
    // placeholder the mock view rendered.
    document.querySelectorAll("#proto-editor-title, #proto-head-title").forEach(function (slot) {
      slot.textContent = state.title;
    });

    // Simple fields.
    root.querySelectorAll("[data-field]").forEach(function (input) {
      var path = input.getAttribute("data-field").split(".");
      input.value = state[path[0]] || "";
      input.addEventListener("input", function () { state[path[0]] = input.value; });
    });
    var titleOut = document.getElementById("proto-head-title");
    var titleIn = root.querySelector('[data-field="title"]');
    if (titleOut && titleIn) {
      titleIn.addEventListener("input", function () { titleOut.textContent = titleIn.value || state.title; });
    }

    // Theory editor: the shared production component (rich-text-editor.js)
    // enhances #id_form-body — this script must have run first, so it seeds
    // the textarea here and reads the serialised mirror back on every action
    // that persists or reviews state.
    var theoryTextarea = document.getElementById("id_form-body");
    if (theoryTextarea) theoryTextarea.value = state.theory_html || "";

    renderList("objectives");
    renderList("materials");
    renderList("checks");
    renderList("steps");

    // Mock upload: reads names from the picked files, never touches a server.
    var fileInput = document.getElementById("proto-material-file");
    var uploadBtn = document.getElementById("proto-material-upload");
    if (uploadBtn && fileInput) {
      uploadBtn.addEventListener("click", function () { fileInput.click(); });
      fileInput.addEventListener("change", function () {
        Array.prototype.forEach.call(fileInput.files, function (file) {
          state.materials.push({
            name: file.name,
            size_display: file.size > 1048576
              ? (file.size / 1048576).toFixed(1) + " MB"
              : Math.max(1, Math.round(file.size / 1024)) + " KB",
          });
        });
        fileInput.value = "";
        renderList("materials");
        if (window.protoToast) window.protoToast("Attached " + state.materials.length + " material(s) in this tab only");
      });
    }

    // Structural buttons.
    root.addEventListener("click", function (event) {
      if (event.target.closest('[data-authoring-tab="review"]')) renderReview();
      var btn = event.target.closest("[data-list-action]");
      if (!btn) return;
      var list = btn.getAttribute("data-list");
      var action = btn.getAttribute("data-list-action");
      var index = parseInt(btn.getAttribute("data-index"), 10);
      var rows = state[list];
      if (action === "add") {
        if (list === "objectives") rows.push("");
        if (list === "materials") { rows.push({ name: "Untitled document", size_display: "—" }); }
        if (list === "checks") rows.push({ prompt: "", options: ["", "", "", ""], answer_index: 0 });
        if (list === "steps") rows.push({ title: "", instruction: "", outcome: "", hint: "", verifications: [] });
        if (list === "verifications") {
          var step = rows[index];
          step.verifications.push({ kind: "saved_record", detail: "" });
          renderList("steps");
          return;
        }
      } else if (action === "remove") {
        if (list === "verifications") state.steps[btn.getAttribute("data-step")].verifications.splice(index, 1);
        else rows.splice(index, 1);
      } else if (action === "up" || action === "down") {
        var to = index + (action === "up" ? -1 : 1);
        if (to < 0 || to >= rows.length) return;
        var tmp = rows[index]; rows[index] = rows[to]; rows[to] = tmp;
      }
      renderList(list === "verifications" ? "steps" : list);
    });

    // Text edits inside lists.
    root.addEventListener("input", function (event) {
      var input = event.target.closest("[data-list][data-index]");
      if (!input) return;
      var list = input.getAttribute("data-list");
      var index = parseInt(input.getAttribute("data-index"), 10);
      var field = input.getAttribute("data-item-field");
      var row = state[list][index];
      if (row == null) return;
      if (list === "objectives") state.objectives[index] = input.value;
      else if (list === "materials") row[field] = input.value;
      else if (list === "checks") {
        if (field === "prompt") row.prompt = input.value;
        if (field === "option") row.options[parseInt(input.getAttribute("data-option"), 10)] = input.value;
      } else if (list === "steps") {
        if (field === "detail") row.verifications[parseInt(input.getAttribute("data-vindex"), 10)].detail = input.value;
        else row[field] = input.value;
      }
    });
    root.addEventListener("change", function (event) {
      var sel = event.target.closest('select[data-list="steps"]');
      if (sel) {
        var step = state.steps[parseInt(sel.getAttribute("data-index"), 10)];
        step.verifications[parseInt(sel.getAttribute("data-vindex"), 10)].kind = sel.value;
      }
      var answer = event.target.closest('input[type="radio"][data-list="checks"]');
      if (answer) {
        state.checks[parseInt(answer.getAttribute("data-index"), 10)].answer_index =
          parseInt(answer.getAttribute("data-option"), 10);
      }
      var proc = event.target.closest('[data-field="procedure"]');
      if (proc) state.procedure = proc.value;
    });

    // Save + navigation.
    root.querySelectorAll("[data-proto-save]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (theoryTextarea) state.theory_html = theoryTextarea.value;
        window.protoM2Put(state);
        if (window.protoToast) window.protoToast(btn.getAttribute("data-proto-save"));
      });
    });
    var back = document.getElementById("proto-back-to-module");
    if (back) {
      back.addEventListener("click", function (event) {
        event.preventDefault();
        if (theoryTextarea) state.theory_html = theoryTextarea.value;
        window.protoM2Put(state);
        location.href = back.getAttribute("href");
      });
    }
    var preview = document.getElementById("proto-open-preview");
    if (preview) {
      preview.addEventListener("click", function (event) {
        event.preventDefault();
        if (theoryTextarea) state.theory_html = theoryTextarea.value;
        window.protoM2Put(state);
        location.href = preview.getAttribute("href") + "?lesson=" +
          encodeURIComponent(state.slug) + "&kind=" + state.kind;
      });
    }
    // Leaving by any other route (the Demonstration Studio link, back
    // forward, closing the tab) must not quietly drop the unsaved theory.
    window.addEventListener("pagehide", function () {
      if (theoryTextarea) state.theory_html = theoryTextarea.value;
      window.protoM2Put(state);
    });
    renderReview();
  }

  function renderList(list) {
    var host = document.querySelector('[data-list-host="' + list + '"]');
    if (!host || !state) return;
    host.innerHTML = "";
    state[list].forEach(function (row, index) {
      host.appendChild(listRow(list, row, index));
    });
    if (!state[list].length) {
      var empty = document.createElement("p");
      empty.className = "ws-empty-note";
      empty.textContent = listEmptyText(list);
      host.appendChild(empty);
    }
    if (list === "steps") renderReview();
  }

  function listEmptyText(list) {
    if (list === "objectives") return "No objectives yet — add the first one.";
    if (list === "materials") return "No supporting documents attached yet.";
    if (list === "checks") return "No knowledge checks yet — they stay optional.";
    return "No practical steps yet.";
  }

  function moveButtons(list, index, count) {
    return '<span class="ws-move">' +
      '<button type="button" class="proto-move" data-list="' + list + '" data-list-action="up" data-index="' + index + '"' + (index === 0 ? " disabled" : "") + ' aria-label="Move up">↑</button>' +
      '<button type="button" class="proto-move" data-list="' + list + '" data-list-action="down" data-index="' + index + '"' + (index === count - 1 ? " disabled" : "") + ' aria-label="Move down">↓</button>' +
      '</span>';
  }
  function removeButton(list, index) {
    return '<button type="button" class="authoring-secondary" data-list="' + list + '" data-list-action="remove" data-index="' + index + '">Remove</button>';
  }

  function listRow(list, row, index) {
    var el = document.createElement("div");
    el.className = "proto-item";
    if (list === "objectives") {
      el.innerHTML = '<input type="text" data-list="objectives" data-index="' + index + '" placeholder="e.g. Identify the parties named on the document" value="' + esc(row) + '">' +
        moveButtons(list, index, state.objectives.length) + removeButton(list, index);
    } else if (list === "materials") {
      el.innerHTML = '<span class="proto-item-icon" aria-hidden="true">📄</span>' +
        '<input type="text" data-list="materials" data-item-field="name" data-index="' + index + '" value="' + esc(row.name) + '">' +
        '<span class="proto-item-size">' + esc(row.size_display) + '</span>' +
        removeButton(list, index);
    } else if (list === "checks") {
      var opts = row.options.map(function (opt, oi) {
        return '<label class="proto-option"><input type="radio" name="answer-' + index + '" data-list="checks" data-index="' + index + '" data-option="' + oi + '"' + (oi === row.answer_index ? " checked" : "") + '>' +
          '<input type="text" data-list="checks" data-item-field="option" data-index="' + index + '" data-option="' + oi + '" value="' + esc(opt) + '" placeholder="Option ' + (oi + 1) + '"></label>';
      }).join("");
      el.innerHTML = '<div class="proto-check-head">Question ' + (index + 1) + moveButtons(list, index, state.checks.length) + removeButton(list, index) + '</div>' +
        '<input type="text" data-list="checks" data-item-field="prompt" data-index="' + index + '" placeholder="Question text" value="' + esc(row.prompt) + '">' +
        '<div class="proto-options">' + opts + '</div>' +
        '<p class="helptext">Mark the radio button of the correct option.</p>';
    } else if (list === "steps") {
      var ver = row.verifications.map(function (v, vi) {
        return '<div class="proto-verification">' +
          '<select data-list="steps" data-index="' + index + '" data-vindex="' + vi + '">' +
          '<option value="saved_record"' + (v.kind === "saved_record" ? " selected" : "") + '>Saved-record check</option>' +
          '<option value="screen_opened"' + (v.kind === "screen_opened" ? " selected" : "") + '>Navigation check</option></select>' +
          '<input type="text" data-list="steps" data-item-field="detail" data-index="' + index + '" data-vindex="' + vi + '" placeholder="e.g. Consignment application — status Draft" value="' + esc(v.detail) + '">' +
          '<button type="button" class="authoring-secondary" data-list="verifications" data-list-action="remove" data-index="' + vi + '" data-step="' + index + '">Remove</button></div>';
      }).join("");
      el.innerHTML = '<div class="proto-step-head"><span class="proto-step-num">' + (index + 1) + '</span>' +
        '<input type="text" data-list="steps" data-item-field="title" data-index="' + index + '" placeholder="Step title" value="' + esc(row.title) + '">' +
        (row.from_demo ? '<span class="proto-flag">from mock demo</span>' : "") +
        moveButtons(list, index, state.steps.length) + removeButton(list, index) + '</div>' +
        '<label>Instruction<input type="text" data-list="steps" data-item-field="instruction" data-index="' + index + '" value="' + esc(row.instruction) + '"></label>' +
        '<label>Expected outcome<input type="text" data-list="steps" data-item-field="outcome" data-index="' + index + '" value="' + esc(row.outcome) + '"></label>' +
        '<label>Hint <span class="proto-flag">real field</span><input type="text" data-list="steps" data-item-field="hint" data-index="' + index + '" placeholder="Optional hint the learner can reveal" value="' + esc(row.hint) + '"></label>' +
        '<div class="proto-verifications">' + (ver || '<p class="helptext">No verification yet — a step can be instruction-only.</p>') + '</div>' +
        '<button type="button" class="authoring-secondary" data-list="verifications" data-list-action="add" data-index="' + index + '">+ Add verification</button>';
    }
    return el;
  }

  function renderReview() {
    var host = document.getElementById("proto-review-checklist");
    if (!host || !state) return;
    var theory = document.getElementById("id_form-body");
    if (theory) state.theory_html = theory.value;
    var hasTheory = !!(state.theory_html && state.theory_html.replace(/<[^>]+>/g, "").trim());
    var items = [
      { ok: !!state.title.trim(), label: "Lesson title" },
      { ok: !!state.summary.trim(), label: "Summary shown to learners" },
      { ok: hasTheory, label: "Theory written" },
      { ok: state.objectives.length > 0, label: "Learning objectives (proposed field)" },
    ];
    if (state.kind === "guided") {
      items.push({ ok: state.materials.length > 0, label: "At least one supporting material" });
      items.push({ ok: true, label: "Knowledge checks — optional (" + state.checks.length + " added)" });
    } else {
      items.push({ ok: !!state.procedure, label: "Simulator procedure selected" });
      items.push({ ok: state.steps.length > 0, label: "At least one practical step (" + state.steps.length + ")" });
      var incomplete = state.steps.filter(function (s) { return !s.title.trim() || !s.instruction.trim() || !s.outcome.trim(); }).length;
      items.push({ ok: incomplete === 0 && state.steps.length > 0, label: incomplete ? incomplete + " step(s) missing title/instruction/outcome" : "Every step has an instruction and expected outcome" });
    }
    host.innerHTML = items.map(function (item) {
      return '<li class="' + (item.ok ? "proto-ok" : "proto-missing") + '">' +
        '<span aria-hidden="true">' + (item.ok ? "✓" : "!") + '</span> ' + esc(item.label) + '</li>';
    }).join("");
    var chip = document.getElementById("proto-review-state");
    if (chip) {
      var missing = items.filter(function (i) { return !i.ok; }).length;
      chip.textContent = missing ? "Not publish-ready · " + missing + " item(s)" : "Prototype-ready";
      chip.className = "ws-chip " + (missing ? "ws-chip--draft" : "ws-chip--published");
    }
  }

  /* ------------------------------------------------------------------ *
   * Instructor preview: the student-workspace shape, browser-side only.
   * ------------------------------------------------------------------ */
  function initPreview() {
    var root = document.getElementById("proto-preview");
    if (!root) return;
    var seed = seedFromPage();
    var lesson = window.protoM2Get(seed.slug) || seed;
    document.getElementById("proto-preview-title").textContent = lesson.title;
    document.getElementById("proto-preview-kind").textContent =
      lesson.kind === "guided" ? "Guided Practical" : "Interactive Practical";

    var left = document.getElementById("proto-preview-left");
    var html = '<p class="authoring-eyebrow">Theory &amp; Practical · ' +
      (lesson.kind === "guided" ? "Guided Practical" : "Interactive Practical") + '</p>' +
      '<h2>' + esc(lesson.title) + '</h2>' +
      (lesson.summary ? '<p class="proto-preview-summary">' + esc(lesson.summary) + '</p>' : "");
    if (lesson.objectives.length) {
      html += '<h3>What you will be able to do</h3><ul>' +
        lesson.objectives.filter(Boolean).map(function (o) { return "<li>" + esc(o) + "</li>"; }).join("") + "</ul>";
    }
    if (lesson.theory_html) {
      html += '<h3>Theory &amp; guide</h3><div class="proto-theory-render">' + lesson.theory_html + "</div>";
    } else {
      html += '<p class="ws-empty-note">Theory not written yet.</p>';
    }
    if (lesson.kind === "interactive") {
      html += '<h3>Steps</h3><ol class="proto-preview-steps">' +
        lesson.steps.map(function (s) {
          return '<li><b>' + esc(s.title || "Untitled step") + '</b>' +
            (s.instruction ? '<p>' + esc(s.instruction) + '</p>' : "") +
            (s.outcome ? '<p class="proto-outcome">Expected: ' + esc(s.outcome) + '</p>' : "") +
            "</li>";
        }).join("") + "</ol>";
    } else {
      html += '<h3>Knowledge checks</h3>';
      html += lesson.checks.length
        ? lesson.checks.map(function (c, ci) {
            return '<div class="proto-check-render"><b>' + esc(c.prompt || "Untitled question") + '</b><ul>' +
              c.options.map(function (o, oi) {
                return "<li" + (oi === c.answer_index ? ' class="proto-answer"' : "") + ">" + esc(o) + "</li>";
              }).join("") + "</ul></div>";
          }).join("")
        : '<p class="ws-empty-note">No knowledge checks for this lesson.</p>';
    }
    left.innerHTML = html;

    var right = document.getElementById("proto-preview-right");
    if (lesson.kind === "guided") {
      right.innerHTML = '<h3>Supporting materials</h3>' + (lesson.materials.length
        ? lesson.materials.map(function (m) {
            return '<div class="proto-material-card"><span aria-hidden="true">📄</span><div><b>' + esc(m.name) + '</b><p>' + esc(m.size_display) + ' · mock viewer — files stay in this tab</p></div></div>';
          }).join("")
        : '<p class="ws-empty-note">No materials attached yet.</p>');
    }

    // Resizable divider — mirrors the real workspace handle, browser-only.
    var divider = document.getElementById("proto-divider");
    var split = document.getElementById("proto-split");
    if (divider && split) {
      var apply = function (pct) {
        pct = Math.min(70, Math.max(20, pct));
        split.style.setProperty("--proto-left", pct + "%");
      };
      var dragging = false;
      divider.addEventListener("pointerdown", function (event) {
        dragging = true;
        divider.setPointerCapture(event.pointerId);
      });
      divider.addEventListener("pointermove", function (event) {
        if (!dragging) return;
        var rect = split.getBoundingClientRect();
        apply(((event.clientX - rect.left) / rect.width) * 100);
      });
      divider.addEventListener("pointerup", function () { dragging = false; });
      divider.addEventListener("dblclick", function () { apply(35); });
    }
  }

  var EDITOR_URL = "";
  var STUDIO_URL = "";
  document.addEventListener("DOMContentLoaded", function () {
    var meta = document.getElementById("proto-urls");
    if (meta) {
      var urls = JSON.parse(meta.textContent);
      EDITOR_URL = urls.editor || "";
      STUDIO_URL = urls.studio || "";
    }
    initModule();
    gridRemove();
    initEditor();
    initPreview();
  });
})();
