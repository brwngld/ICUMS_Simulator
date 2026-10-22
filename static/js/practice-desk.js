/*
  Integrated Practice Desk spike: the divider, the panel switch and the guide's
  own fetch. It loads instead of guide-panel.js on this page and talks to the
  same engine endpoints, so a check is still the server's answer about the
  attempt, never the button's.

  Nothing here reloads the simulator frame. Width and pane choice are the desk's
  own state, kept in the tab; unsaved fields inside the frame stay untouched.
*/
(function () {
  "use strict";

  var WIDTH_KEY = "icums.desk.left";
  var MIN_LEFT = 320;
  var MIN_RIGHT = 352;
  var STEP = 24;

  var desk = document.querySelector("[data-desk]");
  if (!desk) {
    return;
  }
  var grid = desk.querySelector("[data-desk-grid]");
  var divider = desk.querySelector("[data-desk-divider]");
  var frame = desk.querySelector("[data-desk-frame]");

  function widthBounds() {
    var box = grid.getBoundingClientRect();
    var reserved = box.width - MIN_RIGHT - divider.offsetWidth;
    if (reserved < MIN_LEFT) {
      return null;
    }
    return { min: MIN_LEFT, max: reserved };
  }

  function setLeftWidth(px) {
    var bounds = widthBounds();
    if (!bounds) {
      return;
    }
    var value = Math.round(Math.min(bounds.max, Math.max(bounds.min, px)));
    grid.style.setProperty("--desk-left", value + "px");
    divider.setAttribute("aria-valuenow", String(value));
    divider.setAttribute("aria-valuemin", String(bounds.min));
    divider.setAttribute("aria-valuemax", String(bounds.max));
    try {
      window.sessionStorage.setItem(WIDTH_KEY, String(value));
    } catch (error) {
      /* storage unavailable in this tab: the width still works for the visit */
    }
  }

  function restoreWidth() {
    var saved;
    try {
      saved = window.sessionStorage.getItem(WIDTH_KEY);
    } catch (error) {
      return;
    }
    if (saved) {
      setLeftWidth(Number(saved));
    }
  }

  if (divider) {
    divider.addEventListener("pointerdown", function (event) {
      divider.setPointerCapture(event.pointerId);
      divider.classList.add("is-dragging");
      event.preventDefault();
    });
    divider.addEventListener("pointermove", function (event) {
      if (!divider.hasPointerCapture(event.pointerId)) {
        return;
      }
      setLeftWidth(event.clientX - grid.getBoundingClientRect().left);
    });
    function release(event) {
      divider.classList.remove("is-dragging");
      if (divider.hasPointerCapture(event.pointerId)) {
        divider.releasePointerCapture(event.pointerId);
      }
    }
    divider.addEventListener("pointerup", release);
    divider.addEventListener("pointercancel", release);
    divider.addEventListener("dblclick", function () {
      setLeftWidth(grid.getBoundingClientRect().width * 0.35);
    });
    divider.addEventListener("keydown", function (event) {
      if (["ArrowLeft", "ArrowRight", "Home"].indexOf(event.key) === -1) {
        return;
      }
      event.preventDefault();
      if (event.key === "Home") {
        setLeftWidth(grid.getBoundingClientRect().width * 0.35);
        return;
      }
      setLeftWidth(grid.firstElementChild.getBoundingClientRect().width + (event.key === "ArrowRight" ? STEP : -STEP));
    });
  }

  /* The framed simulator page is the real thing, chrome and all. The desk owns
     the navigation, so the duplicated sidebar and Unfold header are folded away
     inside the frame document - its own templates, CSS and JS are never
     touched. Unfold nests the sidebar and the header several levels deep, so the
     branch actually holding them is found by walking up to #page and #main:
     hiding #nav-sidebar alone leaves its fixed-position wrapper, and a ":has()"
     rule would match every ancestor up to #page and blank the whole page. */
  var FRAME_HIDE = [".sim-top-nav", ".sim-brandbar", ".sim-skip-link", "aside.guide"];

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
    if (!doc || !doc.head || doc.getElementById("desk-embed-style")) {
      return;
    }
    var style = doc.createElement("style");
    style.id = "desk-embed-style";
    style.textContent = FRAME_HIDE.map(function (selector) {
      return selector + " { display: none !important; }";
    }).join("\n") + "\n#page { min-height: 0; }";
    doc.head.appendChild(style);
    trimBranch(doc, "nav-sidebar", "page");
    trimBranch(doc, "header-inner", "main");
  }

  if (frame) {
    frame.addEventListener("load", trimFrameChrome);
    trimFrameChrome();
  }

  /* /test reference exercise. The checks read the real, same-origin simulator
     document: progress is awarded for what is visible in the workspace, not
     merely for pressing the button. */
  var ucrGuide = desk.querySelector("[data-ucr-guide]");
  var ucrDataNode = document.getElementById("desk-ucr-guide-data");
  if (ucrGuide && ucrDataNode && frame) {
    var ucrData = JSON.parse(ucrDataNode.textContent);
    var ucrStep = 0;
    var ucrPassed = [false, false, false, false, false];
    var ucrSteps = [
      { title: "Find the UCR search", instruction: "Open the Search UCR page in the workspace.", hint: "The practical opens the Search UCR workspace automatically.", checks: ["Search UCR page is open"] },
      { title: "Search the training record", instruction: "Enter the training UCR number and run the search.", hint: "Copy the Training UCR shown above into UCR No. or Temp. No., then select Search.", checks: ["Exact UCR number entered", "Matching submitted result is displayed"] },
      { title: "Open the declaration", instruction: "Select the matching UCR result to open its declaration details.", hint: "Select the UCR number in the first column of the result table.", checks: ["Correct UCR detail page is open"] },
      { title: "Verify the declaration", instruction: "Review the parties, movement details and supporting documents against the checklist.", hint: "Scroll through the declaration. The values are read directly from the open record.", checks: ["UCR, regime and declarant match", "Exporter and importer match", "Origin, destination and transport match", "Required documents and references match"] },
      { title: "Practical complete", instruction: "You found the submitted UCR and verified its core declaration data.", hint: "All earlier checks must be complete.", checks: ["All practical checks passed"] }
    ];
    var ucrTitles = ["Open UCR search", "Search the UCR", "Open the record", "Verify details", "Complete"];
    var ucrCheckButton = ucrGuide.querySelector("[data-ucr-check]");
    var ucrNextButton = ucrGuide.querySelector("[data-ucr-next]");
    var ucrFeedback = ucrGuide.querySelector("[data-ucr-feedback]");

    function ucrFrameDocument() {
      try { return frame.contentDocument; } catch (error) { return null; }
    }
    function fieldValue(doc, selector) {
      var field = doc && doc.querySelector(selector);
      return field ? String(field.value || field.textContent || "").trim() : "";
    }
    function includesValue(actual, expected) {
      return String(actual).toLowerCase().indexOf(String(expected).toLowerCase()) !== -1;
    }
    function validateUcrStep() {
      var doc = ucrFrameDocument();
      var path = framedPath();
      if (!doc) { return [false]; }
      if (ucrStep === 0) { return [path === ucrData.search_path]; }
      if (ucrStep === 1) {
        var links = Array.prototype.slice.call(doc.querySelectorAll(".ucr-result-link"));
        return [fieldValue(doc, "#ucr-number") === ucrData.ucr, links.some(function (link) { return link.textContent.trim() === ucrData.ucr && includesValue(link.closest("tr").textContent, ucrData.status); })];
      }
      if (ucrStep === 2) { return [path === ucrData.detail_path && fieldValue(doc, "#ucr-temp") === ucrData.ucr]; }
      if (ucrStep === 3) {
        var rows = Array.prototype.slice.call(doc.querySelectorAll("#document-rows tr[data-existing-row]"));
        var documentsOkay = ucrData.documents.every(function (expected) {
          return rows.some(function (row) {
            return fieldValue(row, "[data-document-code]") === expected.code && includesValue(fieldValue(row, "input:not([data-document-code]):not([data-document-name])"), expected.reference);
          });
        });
        return [
          fieldValue(doc, "#ucr-temp") === ucrData.ucr && fieldValue(doc, "#ucr-regime") === ucrData.regime && fieldValue(doc, "#ucr-declarant") === ucrData.declarant,
          includesValue(fieldValue(doc, "#ucr-exporter-identity"), ucrData.exporter) && includesValue(fieldValue(doc, "#ucr-importer-identity"), ucrData.importer),
          includesValue(fieldValue(doc, "#ucr-origin"), ucrData.origin) && includesValue(fieldValue(doc, "#ucr-destination"), ucrData.destination) && fieldValue(doc, "#ucr-mode") === ucrData.transport,
          documentsOkay
        ];
      }
      return [ucrPassed.slice(0, 4).every(Boolean)];
    }
    function renderUcrGuide(results) {
      var step = ucrSteps[ucrStep];
      ucrGuide.querySelector("[data-ucr-step-number]").textContent = String(ucrStep + 1);
      ucrGuide.querySelector("[data-ucr-step-title]").textContent = step.title;
      ucrGuide.querySelector("[data-ucr-step-instruction]").textContent = step.instruction;
      ucrGuide.querySelector("[data-ucr-checks]").innerHTML = step.checks.map(function (label, index) {
        return '<li class="' + (results && results[index] ? "done" : "") + '">' + label + "</li>";
      }).join("");
      Array.prototype.forEach.call(desk.querySelectorAll("[data-ucr-progress]"), function (bar, index) {
        bar.className = index < ucrStep ? "done" : (index === ucrStep ? "now" : "");
      });
      var journey = desk.querySelector("[data-ucr-journey]");
      if (journey) {
        journey.innerHTML = ucrTitles.map(function (label, index) {
          return '<li class="' + (index < ucrStep ? "done" : (index === ucrStep ? "now" : "")) + '">' + label + "</li>";
        }).join("");
      }
      ucrNextButton.disabled = !ucrPassed[ucrStep] || ucrStep === ucrSteps.length - 1;
      ucrCheckButton.disabled = ucrStep === ucrSteps.length - 1 && ucrPassed[ucrStep];
    }
    ucrCheckButton.addEventListener("click", function () {
      var results = validateUcrStep();
      var passed = results.every(Boolean);
      ucrPassed[ucrStep] = passed;
      ucrFeedback.textContent = passed ? (ucrStep === 4 ? "Practical complete. Every validation passed." : "Check passed. Continue to the next step.") : "Not yet. Complete the unchecked item in the workspace and try again.";
      ucrFeedback.setAttribute("data-tone", passed ? "pass" : "fail");
      renderUcrGuide(results);
    });
    ucrGuide.querySelector("[data-ucr-hint]").addEventListener("click", function () {
      ucrFeedback.textContent = ucrSteps[ucrStep].hint;
      ucrFeedback.setAttribute("data-tone", "");
    });
    ucrNextButton.addEventListener("click", function () {
      if (!ucrPassed[ucrStep] || ucrStep >= ucrSteps.length - 1) { return; }
      ucrStep += 1;
      if (ucrStep === 4) { ucrPassed[4] = ucrPassed.slice(0, 4).every(Boolean); }
      ucrFeedback.textContent = ucrStep === 4 ? "Run the final check to confirm completion." : "Complete the step in the workspace, then check your work.";
      ucrFeedback.setAttribute("data-tone", "");
      renderUcrGuide();
    });
    frame.addEventListener("load", function () { renderUcrGuide(); });
    renderUcrGuide();
  }

  /* The step card's buttons post to the engine's own endpoints, so a pass is
     always the server's answer about the attempt and never the button's. A check
     or hint comes back as the panel fragment and only its result is written into
     the card, leaving the simulator frame and its unsaved fields alone; a check
     that passed redraws the card, because that is what unlocks the next step. An
     action has no fragment of its own: its answer is the page the learner is sent
     to next, and the desk follows it. */
  var guide = desk.querySelector("[data-desk-guide]");
  var select = desk.querySelector("[data-desk-page-select]");
  var pages = {};

  if (select) {
    Array.prototype.forEach.call(select.options, function (option) {
      pages[option.value] = option.getAttribute("data-desk-href");
    });
  }

  function deskHref(simPath) {
    var params = new URLSearchParams(window.location.search);
    params.set("sim", simPath);
    return window.location.pathname + "?" + params.toString();
  }

  function framedPath() {
    try {
      return frame && frame.contentWindow ? frame.contentWindow.location.pathname : "";
    } catch (error) {
      return "";
    }
  }

  function notice(body) {
    var line = desk.querySelector("[data-guide-feedback]");
    if (!line || !body) {
      return "";
    }
    var message = body.getAttribute("data-notice") || "";
    var tone = body.getAttribute("data-notice-tone") || "";
    line.textContent = message;
    line.setAttribute("data-tone", tone);
    return tone;
  }

  if (guide) {
    guide.addEventListener("submit", function (event) {
      var form = event.target;
      event.preventDefault();
      var isAction = (form.getAttribute("action") || "").indexOf("/actions/") > -1;
      var button = form.querySelector("button");
      if (button) {
        button.disabled = true;
      }
      form.setAttribute("aria-busy", "true");
      fetch(form.action, {
        method: "post",
        body: new FormData(form),
        headers: isAction ? {} : { "X-Guide-Panel": "1" },
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("guide request refused");
          }
          return response.text().then(function (html) {
            return { html: html, redirected: response.redirected, url: response.url };
          });
        })
        .then(function (answer) {
          if (!isAction) {
            var body = new DOMParser().parseFromString(answer.html, "text/html").querySelector("[data-guide-body]");
            if (!body) {
              window.location.reload();
              return;
            }
            if (notice(body) === "pass") {
              window.location.reload();
              return;
            }
            return;
          }
          var landed = answer.redirected ? new URL(answer.url, window.location.href).pathname : "";
          if (landed && landed !== framedPath() && pages[landed]) {
            window.location.assign(deskHref(landed));
            return;
          }
          window.location.reload();
        })
        .catch(function () {
          if (button) {
            button.disabled = false;
          }
          form.removeAttribute("aria-busy");
          form.submit();
        });
    });
  }

  if (select) {
    select.addEventListener("change", function () {
      var option = select.options[select.selectedIndex];
      var href = option && option.getAttribute("data-desk-href");
      if (href) {
        window.location.assign(href);
      }
    });
  }

  var paneButtons = desk.querySelectorAll("[data-desk-pane-button]");

  function showPane(name) {
    grid.setAttribute("data-desk-pane", name);
    Array.prototype.forEach.call(paneButtons, function (button) {
      button.setAttribute("aria-pressed", String(button.getAttribute("data-desk-pane-button") === name));
    });
  }

  Array.prototype.forEach.call(paneButtons, function (button) {
    button.addEventListener("click", function () {
      showPane(button.getAttribute("data-desk-pane-button"));
    });
  });

  if (window.matchMedia("(max-width: 62rem)").matches) {
    showPane("theory");
  }

  var expand = desk.querySelector("[data-desk-expand]");
  if (expand) {
    expand.addEventListener("click", function () {
      var open = desk.hasAttribute("data-desk-expanded");
      if (open) {
        desk.removeAttribute("data-desk-expanded");
      } else {
        desk.setAttribute("data-desk-expanded", "");
      }
      expand.setAttribute("aria-pressed", String(!open));
    });
  }

  restoreWidth();
}());
