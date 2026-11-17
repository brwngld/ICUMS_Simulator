/* Theory & Practical workspace: data-driven step navigation beside the live
   simulator, wired to the server-side attempt. The step texts, order and
   screens come from the hybrid curriculum rows via the server-rendered
   cards; the server's attempt snapshot decides where the learner resumes,
   which steps are satisfied, and whether the next step may open. Without an
   attempt (instructor preview) the same UI runs inertly and writes nothing.
   The divider drag, frame trimming and pane switch fork the /test Practice
   Desk's behaviour so the desk spike stays untouched. */
(function () {
  "use strict";

  var LEFT_KEY = "icums.hybrid.left";
  var MIN_LEFT = 320;
  var MIN_RIGHT = 352;
  var STEP = 24;

  var root = document.querySelector("[data-hyb]");
  if (!root) {
    return;
  }
  var grid = root.querySelector("[data-hyb-grid]");
  var divider = root.querySelector("[data-hyb-divider]");
  var frame = root.querySelector("[data-hyb-frame]");
  var cards = Array.prototype.slice.call(root.querySelectorAll("[data-hyb-step-card]"));
  var journeyItems = Array.prototype.slice.call(root.querySelectorAll("[data-hyb-journey-item]"));
  var progress = root.querySelector("[data-hyb-progress]");
  var prevButton = root.querySelector("[data-hyb-prev]");
  var nextButton = root.querySelector("[data-hyb-next]");
  var checkButton = root.querySelector("[data-hyb-check]");
  var hintButton = root.querySelector("[data-hyb-hint]");
  var acknowledgeButton = root.querySelector("[data-hyb-acknowledge]");
  var current = 0;

  /* --- Attempt mode: the server's snapshot is the only state that matters.
         Without it (preview) the workspace is a faithful, write-free demo. --- */
  var attemptBase = root.getAttribute("data-attempt-base") || "";
  var attemptData = null;
  var dataNode = document.getElementById("hybrid-attempt-data");
  if (attemptBase && dataNode) {
    try {
      attemptData = JSON.parse(dataNode.textContent);
    } catch (error) {
      attemptData = null;
    }
  }
  var attemptMode = Boolean(attemptBase && attemptData && attemptData.id);
  var satisfied = new Set(attemptMode && Array.isArray(attemptData.satisfied) ? attemptData.satisfied : []);

  function csrfToken() {
    var input = document.querySelector("#hyb-csrf input[name='csrfmiddlewaretoken']");
    return input ? input.value : "";
  }

  /* Signing into the simulator inside the frame performs a Django login, which
     rotates the CSRF token the page was rendered with; every attempt call would
     then be refused until a manual reload. The frame is same-origin, so each of
     its loads can lift the fresh token from a re-fetch of this very page and
     keep the pane's controls working without a reload. The refresh never
     touches authentication state — it only re-reads what the server renders. */
  var tokenRefresh = null;
  function refreshCsrfToken() {
    if (tokenRefresh) return tokenRefresh;
    tokenRefresh = fetch(window.location.href, {
      credentials: "same-origin",
      headers: { Accept: "text/html" },
    }).then(function (response) {
      return response.ok ? response.text() : "";
    }).then(function (html) {
      var match = html.match(/name="csrfmiddlewaretoken" value="([^"]+)"/);
      var input = document.querySelector("#hyb-csrf input[name='csrfmiddlewaretoken']");
      if (match && input) {
        input.value = match[1];
      }
    }).catch(function () {
      /* keep the current token; a failed refresh leaves the page as it was */
    }).finally(function () {
      tokenRefresh = null;
    });
    return tokenRefresh;
  }
  if (frame) {
    frame.addEventListener("load", refreshCsrfToken);
  }

  function post(path, body) {
    var options = {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" },
    };
    if (body) {
      options.headers["Content-Type"] = "application/json";
      options.body = body;
    }
    return fetch(attemptBase + path, options).then(function (response) {
      return response.json().then(function (data) {
        return { ok: response.ok, data: data };
      }).catch(function () {
        return { ok: response.ok, data: {} };
      });
    });
  }

  /* --- Resizable divider. Same geometry as the desk: a 35% default, a
         320px floor on the left pane and 352px reserved for the simulator,
         persisted per tab so a reload keeps the learner's split. --- */
  function leftMax() {
    return grid.getBoundingClientRect().width - MIN_RIGHT - divider.getBoundingClientRect().width;
  }

  function setLeftWidth(px) {
    var max = leftMax();
    if (max < MIN_LEFT) {
      return;
    }
    var width = Math.max(MIN_LEFT, Math.min(Math.round(px), max));
    grid.style.setProperty("--hyb-left", width + "px");
    divider.setAttribute("aria-valuenow", String(width));
    divider.setAttribute("aria-valuemin", String(MIN_LEFT));
    divider.setAttribute("aria-valuemax", String(max));
    try {
      sessionStorage.setItem(LEFT_KEY, String(width));
    } catch (error) { /* storage unavailable; the drag still works */ }
  }

  function resetWidth() {
    grid.style.removeProperty("--hyb-left");
    try {
      sessionStorage.removeItem(LEFT_KEY);
    } catch (error) { /* ignore */ }
  }

  function restoreWidth() {
    var raw = null;
    try {
      raw = sessionStorage.getItem(LEFT_KEY);
    } catch (error) { /* ignore */ }
    var parsed = raw ? parseInt(raw, 10) : NaN;
    if (!isNaN(parsed)) {
      setLeftWidth(parsed);
    }
  }

  if (divider && grid) {
    divider.addEventListener("pointerdown", function (event) {
      event.preventDefault();
      divider.setPointerCapture(event.pointerId);
      document.body.classList.add("hyb-resizing");
    });
    divider.addEventListener("pointermove", function (event) {
      if (!divider.hasPointerCapture(event.pointerId)) {
        return;
      }
      var rect = grid.getBoundingClientRect();
      setLeftWidth(event.clientX - rect.left);
    });
    ["pointerup", "pointercancel"].forEach(function (type) {
      divider.addEventListener(type, function () {
        document.body.classList.remove("hyb-resizing");
      });
    });
    divider.addEventListener("dblclick", resetWidth);
    divider.addEventListener("keydown", function (event) {
      if (event.key === "Home") {
        event.preventDefault();
        resetWidth();
      } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        var first = grid.firstElementChild.getBoundingClientRect().width;
        setLeftWidth(first + (event.key === "ArrowRight" ? STEP : -STEP));
      }
    });
    restoreWidth();
  }

  /* --- Frame embedding: the framed page is the real simulator, chrome and
         all — its own header, service menu and navigation stay exactly as
         the standalone page renders them, because the student drives the
         simulator themselves. The only adjustment is the page-height rule so
         the document scrolls naturally inside the pane. --- */
  function embedFrameStyle() {
    if (!frame) {
      return;
    }
    var doc;
    try {
      doc = frame.contentDocument;
    } catch (error) {
      return;
    }
    if (!doc || !doc.head || doc.getElementById("hyb-embed-style")) {
      return;
    }
    var style = doc.createElement("style");
    style.id = "hyb-embed-style";
    style.textContent = "#page { min-height: 0; }";
    doc.head.appendChild(style);
  }

  if (frame) {
    frame.addEventListener("load", embedFrameStyle);
    embedFrameStyle();
  }

  /* --- Stage-evidence capture: the workspace watches the iframe's UCR form
         for regime selection and section completion, and posts signals to
         the attempt so stage-evidence conditions can verify them. The
         simulator form is untouched — this is observation, not modification.
         Only active when an attempt is bound (not in instructor preview). --- */
  function watchStageEvidence() {
    if (!frame || !attemptMode) return;
    var doc;
    try { doc = frame.contentDocument; } catch (e) { return; }
    if (!doc || !doc.getElementById("ucr-regime")) return;

    var regimeWatched = doc.getElementById("ucr-regime").__stageWatched;
    if (!regimeWatched) {
      doc.getElementById("ucr-regime").__stageWatched = true;
      doc.getElementById("ucr-regime").addEventListener("change", function () {
        var value = this.value;
        if (value) post("/stage-evidence/", JSON.stringify({ stage: "regime_selected", value: value }));
      });
    }

    if (doc.__sectionsWatched) return;
    doc.__sectionsWatched = true;
    var SECTION_FIELDS = {
      provider: ["ucr-provider-country", "ucr-provider-address", "ucr-provider-contact", "ucr-provider-phone", "ucr-provider-email"],
      exporter: ["ucr-exporter-name", "ucr-exporter-country", "ucr-exporter-address", "ucr-exporter-phone", "ucr-exporter-contact", "ucr-exporter-contact-no", "ucr-exporter-designation"],
      importer: ["ucr-importer-country", "ucr-importer-address", "ucr-importer-phone", "ucr-importer-contact", "ucr-importer-contact-no", "ucr-importer-designation"],
      consignment: ["ucr-goods", "ucr-origin", "ucr-destination", "ucr-mode"]
    };
    function checkSections() {
      var completed = [];
      for (var section in SECTION_FIELDS) {
        var ids = SECTION_FIELDS[section];
        var allFilled = ids.every(function (id) {
          var el = doc.getElementById(id);
          return el && el.value && el.value.trim() !== "";
        });
        if (allFilled) completed.push(section);
      }
      if (completed.length === Object.keys(SECTION_FIELDS).length && !doc.__sectionsBeaconSent) {
        doc.__sectionsBeaconSent = true;
        post("/stage-evidence/", JSON.stringify({ stage: "sections_completed" }));
      }
    }
    doc.addEventListener("input", checkSections, true);
    doc.addEventListener("change", checkSections, true);
  }
  if (frame) {
    frame.addEventListener("load", function () { setTimeout(watchStageEvidence, 300); });
    watchStageEvidence();
  }

  /* --- Feedback and journey state --- */
  function setFeedback(index, tone, html) {
    var feedback = root.querySelector('[data-hyb-feedback="' + index + '"]');
    if (!feedback) {
      return;
    }
    if (tone) {
      feedback.setAttribute("data-tone", tone);
    } else {
      feedback.removeAttribute("data-tone");
    }
    feedback.innerHTML = html;
  }

  /* Server sentences are plain text, so they never reach the card as markup. */
  function setFeedbackText(index, tone, text) {
    var feedback = root.querySelector('[data-hyb-feedback="' + index + '"]');
    if (!feedback) {
      return;
    }
    if (tone) {
      feedback.setAttribute("data-tone", tone);
    } else {
      feedback.removeAttribute("data-tone");
    }
    feedback.textContent = text;
  }

  function renderResults(index, results) {
    var items = results.map(function (result) {
      return '<li class="' + (result.passed ? "passed" : "failed") + '"><strong>' +
        (result.passed ? "✓" : "✗") + " " + result.label + "</strong> — " + result.message + "</li>";
    });
    setFeedback(index, "", '<ul class="hyb-results">' + items.join("") + "</ul>");
  }

  function updateJourney() {
    journeyItems.forEach(function (item, position) {
      item.classList.toggle("now", position === current);
      item.classList.toggle("done", satisfied.has(position));
      var bubble = item.querySelector("span");
      if (bubble) {
        bubble.textContent = satisfied.has(position) ? "✓" : String(position + 1);
      }
    });
    if (progress) {
      progress.textContent = "Step " + (current + 1) + " of " + cards.length;
    }
  }

  /* --- Step navigation. The student drives the simulator: advancing a step
         never moves the frame — the step card names the screen the work
         happens on, and the learner navigates the real simulator themselves
         (or opens it in a new tab). In attempt mode the server owns
         sequencing: a step that declares verification holds the journey
         until its check passes — on every attempt, first pass or practice
         alike; the practice flag only marks the repeat, it never unlocks
         anything. --- */
  function refreshButtons() {
    if (prevButton) {
      prevButton.disabled = current === 0;
    }
    if (nextButton) {
      var atEnd = current >= cards.length - 1;
      nextButton.disabled = atEnd || (attemptMode && !satisfied.has(current));
    }
  }

  function show(index) {
    if (!cards.length) {
      return;
    }
    current = Math.max(0, Math.min(index, cards.length - 1));
    cards.forEach(function (card) {
      card.hidden = Number(card.getAttribute("data-hyb-step-card")) !== current;
    });
    updateJourney();
    refreshButtons();
    cards[current].scrollIntoView({ block: "nearest" });
    if (attemptMode) {
      post("/open/" + current + "/");
    }
  }

  if (prevButton) {
    prevButton.addEventListener("click", function () { show(current - 1); });
  }
  if (nextButton) {
    nextButton.addEventListener("click", function () {
      if (current >= cards.length - 1) {
        return;
      }
      if (!attemptMode) {
        show(current + 1);
        return;
      }
      post("/advance/" + current + "/").then(function (result) {
        if (result.ok && result.data.allowed) {
          var held = result.data.journey_moved === false && result.data.journey_message;
          show(current + 1);
          /* The lesson moved; the journey did not. Its own sentence names what
             is still outstanding, so the learner hears the reason instead of
             finding the next check refusing. */
          if (held) {
            setFeedbackText(current, "pending", result.data.journey_message);
          }
        } else {
          setFeedback(current, "fail", result.data.message || "The next step is locked for now.");
        }
      });
    });
  }
  if (checkButton) {
    checkButton.addEventListener("click", function () {
      if (!attemptMode) {
        setFeedback(current, "pending", "Verification is not connected in this preview.");
        return;
      }
      var index = current;
      /* The opening request and the check are posted independently, so the
         check can arrive while the server is still recording the opening.
         That refusal is explicitly retryable; wait it out a couple of times
         before surfacing anything to the learner. */
      function check(retriesLeft) {
        post("/check/" + index + "/").then(function (result) {
          if (!result.ok && result.data.code === "opening_pending" && retriesLeft > 0) {
            window.setTimeout(function () { check(retriesLeft - 1); }, 250);
            return;
          }
          if (!result.ok) {
            setFeedback(index, "fail", result.data.error || "The check could not run. Try again.");
            return;
          }
          renderResults(index, result.data.results || []);
          if (result.data.passed) {
            satisfied.add(index);
            updateJourney();
            refreshButtons();
          }
          if (result.data.lesson_complete) {
            var journey = root.querySelector("[data-hyb-journey]");
            if (journey && !journey.parentElement.querySelector(".hyb-done-note")) {
              var note = document.createElement("p");
              note.className = "hyb-done-note";
              note.textContent = "Lesson complete — every step is verified and the theory is acknowledged.";
              journey.parentElement.appendChild(note);
            }
          }
        });
      }
      setFeedback(index, "", "Checking…");
      check(2);
    });
  }
  if (hintButton) {
    hintButton.addEventListener("click", function () {
      if (!attemptMode) {
        setFeedback(current, "", "Hints are available when you start the lesson.");
        return;
      }
      // Read the iframe's form state so the server can name specific missing fields
      var formState = {};
      try {
        var doc = frame.contentDocument;
        if (doc) {
          var inputs = doc.querySelectorAll("input[id^='ucr-'], select[id^='ucr-'], textarea[id^='ucr-']");
          for (var i = 0; i < inputs.length; i++) {
            if (inputs[i].id) formState[inputs[i].id] = inputs[i].value || "";
          }
        }
      } catch (e) { /* iframe not accessible — hint still works from server state */ }
      var hint = root.querySelector('[data-hyb-hint="' + current + '"]');
      if (hint) hint.hidden = false;
      setFeedback(current, "", "Checking…");
      post("/hint/" + current + "/", JSON.stringify(formState)).then(function (result) {
        if (result.ok && result.data.hint) {
          setFeedbackText(current, "pending", result.data.hint);
        } else {
          setFeedback(current, "", result.data.error || "No hint available for this step.");
        }
      });
    });
  }
  if (acknowledgeButton) {
    acknowledgeButton.addEventListener("click", function () {
      post("/acknowledge-theory/").then(function (result) {
        if (result.ok && result.data.ok) {
          acknowledgeButton.outerHTML = '<span class="dash-pill is-ok">Theory acknowledged ✓</span>';
        }
      });
    });
  }

  /* --- Narrow screens: one pane at a time, chosen from the header. --- */
  Array.prototype.forEach.call(root.querySelectorAll("[data-hyb-pane-button]"), function (button) {
    button.addEventListener("click", function () {
      if (!grid) {
        return;
      }
      grid.setAttribute("data-hyb-pane", button.getAttribute("data-hyb-pane-button"));
      Array.prototype.forEach.call(root.querySelectorAll("[data-hyb-pane-button]"), function (other) {
        other.setAttribute("aria-pressed", String(other === button));
      });
    });
  });

  show(attemptMode ? attemptData.current_index : 0);
})();
