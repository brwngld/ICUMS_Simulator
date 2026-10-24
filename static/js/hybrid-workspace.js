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
  var currentScreen = frame ? frame.getAttribute("src") : "";

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

  function post(path) {
    return fetch(attemptBase + path, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" },
    }).then(function (response) {
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

  /* --- Frame trimming: the framed simulator page is the real page, chrome
         and all. The workspace owns the navigation, so the duplicated
         sidebar and header are folded away inside the frame document — the
         simulator's own templates, CSS and JS are never touched. --- */
  var FRAME_HIDE = [".sim-skip-link", ".sim-brand-side", "aside.guide"];

  function trimBranch(doc, startId, stopId) {
    var node = doc.getElementById(startId);
    while (node && node.parentElement && node.parentElement.id !== stopId) {
      if (node.parentElement === doc.body) {
        return;
      }
      node = node.parentElement;
    }
    if (node && node.parentElement && node.parentElement.id === stopId) {
      node.style.display = "none";
    }
  }

  function trimFrameChrome() {
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
    style.textContent = FRAME_HIDE.map(function (selector) {
      return selector + " { display: none !important; }";
    }).join("\n") + "\n#page { min-height: 0; }\n"
      + "html, body { scrollbar-width: none; }\n"
      + "::-webkit-scrollbar { width: 0; height: 0; display: none; }";
    doc.head.appendChild(style);
    trimBranch(doc, "nav-sidebar", "page");
    trimBranch(doc, "header-inner", "main");
  }

  if (frame) {
    frame.addEventListener("load", trimFrameChrome);
    trimFrameChrome();
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

  /* --- Step navigation. Advancing to a step bound to a different screen
         swaps the iframe's src; consecutive steps sharing a screen leave the
         frame alone, so anything typed into the simulator survives. In
         attempt mode the server owns sequencing: a step that declares
         verification holds the journey until its check passes. --- */
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
    var screenUrl = cards[current].getAttribute("data-screen-url");
    if (screenUrl && frame && screenUrl !== currentScreen) {
      currentScreen = screenUrl;
      frame.setAttribute("src", screenUrl);
    }
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
          show(current + 1);
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
      setFeedback(current, "", "Checking…");
      post("/check/" + current + "/").then(function (result) {
        if (!result.ok) {
          setFeedback(current, "fail", "The check could not run. Try again.");
          return;
        }
        renderResults(current, result.data.results || []);
        if (result.data.passed) {
          satisfied.add(current);
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
    });
  }
  if (hintButton) {
    hintButton.addEventListener("click", function () {
      var hint = root.querySelector('[data-hyb-hint="' + current + '"]');
      if (hint) {
        hint.hidden = false;
        setFeedback(current, "", "");
      } else {
        setFeedback(current, "", "No hint for this step.");
      }
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
