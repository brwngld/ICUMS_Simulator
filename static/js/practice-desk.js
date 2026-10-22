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
    var ucrPassed = [false, false, false];
    var ucrSteps = [
      { title: "Open Single Window", instruction: "Select Single Window in the simulator navigation.", hint: "Use the Single Window link in the top navigation of the workspace.", checks: ["Single Window UCR form is open"] },
      { title: "Select the regime", instruction: "Select Import as the Regime Type.", hint: "Regime Type is at the top of the UCR Details form. Choose IM, Import.", checks: ["Regime Type is IM, Import"] },
      { title: "Enter the exporter details", instruction: "Scroll to Exporter and enter the values from the source UCR.", hint: "Enter each value exactly as shown in the checklist.", checks: ["Exporter name: " + ucrData.exporter_name, "Country: " + ucrData.exporter_country, "Tel. No.: " + ucrData.exporter_phone, "Contact Person: " + ucrData.exporter_contact, "Contact Designation: " + ucrData.exporter_designation] }
    ];
    var ucrTitles = ["Open Single Window", "Select Import", "Enter exporter details"];
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
      if (ucrStep === 0) { return [path === ucrData.create_path && Boolean(doc.querySelector("#ucr-regime"))]; }
      if (ucrStep === 1) { return [path === ucrData.create_path && fieldValue(doc, "#ucr-regime") === "IM"]; }
      if (ucrStep === 2) {
        return [
          fieldValue(doc, "#ucr-exporter-identity") === ucrData.exporter_name,
          fieldValue(doc, "#ucr-exporter-country") === ucrData.exporter_country,
          fieldValue(doc, "#ucr-exporter-phone") === ucrData.exporter_phone,
          fieldValue(doc, "#ucr-exporter-contact") === ucrData.exporter_contact,
          fieldValue(doc, "#ucr-exporter-designation") === ucrData.exporter_designation
        ];
      }
      return [false];
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
      ucrFeedback.textContent = passed ? (ucrStep === ucrSteps.length - 1 ? "Practical complete. All exporter details match the source UCR." : "Check passed. Continue to the next step.") : "Not yet. Complete the unchecked item in the workspace and try again.";
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
      ucrFeedback.textContent = "Complete the step in the workspace, then check your work.";
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
