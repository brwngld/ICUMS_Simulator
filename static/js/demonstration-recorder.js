/* Universal demonstration recorder — Stage A interaction capture.
 *
 * Served only on simulator pages whose server-side binding resolved to a live
 * recording in the capturing state (core.admin_dashboard._demonstration_recording),
 * so everything here runs inside an authorized context by construction. The
 * recorder works on every simulator screen without per-page wiring: capture-
 * phase listeners on the document see controls added after load as readily as
 * those in the original markup.
 *
 * Evidence rules: what a control is (stable semantic identity, visible label)
 * and what was done to it (activated, chosen, toggled, completed, submitted).
 * Never what was typed: text controls report only that they were completed,
 * selections report which option was chosen, and controls whose names suggest
 * secrets — passwords, tokens, credentials, card data — are skipped entirely.
 * The page's route name arrives from the server's own render; it travels as
 * context and is never treated as proof of the originating screen.
 *
 * Delivery: a single-flight FIFO queue flushes in bounded batches, with one
 * idempotency key per event so a lost response can be retried without
 * duplicates. pagehide flushes through fetch keepalive, so the last batch
 * survives navigation and tab close. A refusal (403) disables the recorder for
 * the rest of the page — silently, exactly like every other demonstration
 * boundary: recording never interrupts the instructor's browsing.
 */
(function () {
  "use strict";

  var script = document.getElementById("demonstration-recorder");
  if (!script || script.getAttribute("data-active") === "1") return;
  script.setAttribute("data-active", "1");

  var endpoint = script.getAttribute("data-endpoint") || "";
  var csrfToken = script.getAttribute("data-csrf") || "";
  var pageRoute = script.getAttribute("data-route") || "";
  if (!endpoint || !window.fetch) return;

  var FLUSH_SIZE = 20;        /* pending events that trigger a flush */
  var FLUSH_DELAY = 2000;     /* …or this many ms after the first pending one */
  var BATCH_LIMIT = 40;       /* the server's own batch ceiling */
  var QUEUE_LIMIT = 60;       /* bounded memory: beyond this, new events drop */
  var MAX_ATTEMPTS = 3;       /* transport retries per batch, then it drops */

  var queue = [];
  var sending = false;
  var flushTimer = null;
  var disabled = false;

  /* Controls whose name, id or placeholder suggests a secret are never
     recorded — not even as "completed". The recorder's payload has no value
     field for anything else, either. */
  var SENSITIVE = /pass(word|wd)?|secret|token|csrf|auth|credential|api[-_]?key|card|cvv|cvc|ssn|social[-_]?sec|pin\b/i;

  var CLICKABLE = "button, a[href], [role='button'], input[type='button'], input[type='submit'], input[type='reset'], summary";

  /* --- Capture scope: the simulator's own surfaces. The Unfold sidebar and
         admin chrome around a simulator page are not the demonstration. --- */
  function inScope(element) {
    if (!element || !element.closest) return false;
    return Boolean(element.closest(".sim-page") || element.closest(".sim-brandbar"));
  }

  function tagName(element) {
    return element.tagName ? String(element.tagName).toLowerCase() : "";
  }

  function clip(text) {
    text = String(text || "").replace(/\s+/g, " ").replace(/[\u0000-\u001f\u007f]/g, "");
    return text.length > 120 ? text.slice(0, 120) : text;
  }

  /* --- Stable semantic identity, in order of preference: the control's own
         id; an explicit recording id; its name inside its form; and only as a
         last resort a short structural path. Never coordinates. --- */
  function identityOf(element) {
    var id = element.getAttribute("id");
    if (id) return "#" + id;
    var marked = element.getAttribute("data-rec-id");
    if (marked) return "[data-rec-id=" + marked + "]";
    var name = element.getAttribute("name");
    if (name) {
      var form = element.closest ? element.closest("form") : null;
      var formName = form ? (form.getAttribute("id") || form.getAttribute("name") || "") : "";
      return (formName ? "form:" + formName + " " : "") + "[name=" + name + "]";
    }
    return structuralPath(element);
  }

  function structuralPath(element) {
    var parts = [];
    var node = element;
    var depth = 0;
    while (node && node.nodeType === 1 && depth < 6) {
      if (node.getAttribute && node.getAttribute("id")) {
        parts.unshift("#" + node.getAttribute("id"));
        return parts.join(" > ");
      }
      var tag = tagName(node);
      var index = 1;
      var sibling = node;
      while ((sibling = sibling.previousElementSibling)) {
        if (tagName(sibling) === tag) index++;
      }
      parts.unshift(tag + ":nth-of-type(" + index + ")");
      node = node.parentElement;
      depth++;
    }
    return parts.join(" > ");
  }

  /* --- Visible text for a control: what it shows the instructor, capped.
         The element's own value is never read. --- */
  function labelOf(element) {
    var text = element.getAttribute("aria-label") || element.getAttribute("title") || "";
    if (!text) {
      var labelledby = element.getAttribute("aria-labelledby");
      if (labelledby) text = textOf(document.getElementById(labelledby));
    }
    if (!text && element.labels && element.labels[0]) text = textOf(element.labels[0]);
    if (!text) {
      var id = element.getAttribute("id");
      if (id && window.CSS && CSS.escape) {
        var label = document.querySelector("label[for='" + CSS.escape(id) + "']");
        if (label) text = textOf(label);
      }
    }
    if (!text) text = textOf(element);
    if (!text) text = element.getAttribute("placeholder") || "";
    return clip(text);
  }

  function textOf(node) {
    return node ? clip(node.textContent) : "";
  }

  /* --- Selection identity: which option was chosen, or the new toggle state.
         Text inputs contribute nothing — "complete" is the whole fact. --- */
  function selectionOf(element) {
    if (tagName(element) === "select") {
      var option = element.options && element.options[element.selectedIndex];
      return option ? clip(option.label || option.value) : "";
    }
    if (element.type === "checkbox") {
      return element.checked ? (element.value || "checked") : "unchecked";
    }
    if (element.type === "radio") {
      return element.checked ? (element.value || "checked") : "";
    }
    return "";
  }

  function kindOf(element) {
    switch (tagName(element)) {
      case "select": return "select";
      case "textarea": return "textarea";
      case "a": return "link";
      case "input": {
        var type = String(element.getAttribute("type") || "text").toLowerCase();
        if (type === "checkbox") return "checkbox";
        if (type === "radio") return "radio";
        if (type === "search") return "search";
        if (type === "button" || type === "submit" || type === "reset") return "button";
        return "input";
      }
      case "form": return "form";
      default: return "button";
    }
  }

  function isSensitive(element) {
    var probe = [
      element.getAttribute("name"), element.getAttribute("id"),
      element.getAttribute("aria-label"), element.getAttribute("placeholder"),
    ].join(" ");
    return SENSITIVE.test(probe);
  }

  /* One innermost actionable control per click: spans inside buttons resolve
     to the button; labels forwarding to checkboxes and the checkboxes
     themselves resolve to nothing here — the change event records that toggle
     once, so one user action never yields two events. */
  function clickableFrom(target) {
    if (!target || !target.closest) return null;
    var control = target.closest(CLICKABLE);
    if (!control || tagName(control) === "label") return null;
    if (control.type === "checkbox" || control.type === "radio") return null;
    return control;
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    var bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    var hex = [];
    for (var i = 0; i < 16; i++) hex.push((bytes[i] + 0x100).toString(16).slice(1));
    return hex.slice(0, 4).join("") + "-" + hex.slice(4, 6).join("") + "-" + hex.slice(6, 8).join("") +
      "-" + hex.slice(8, 10).join("") + "-" + hex.slice(10, 16).join("");
  }

  function enqueue(item) {
    if (disabled || queue.length >= QUEUE_LIMIT) return;
    item.idempotency_key = uuid();
    if (pageRoute) item.route_name = pageRoute;
    queue.push(item);
    if (queue.length >= FLUSH_SIZE) flush();
    else if (!flushTimer) flushTimer = setTimeout(flush, FLUSH_DELAY);
  }

  function flush() {
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
    if (disabled || sending || !queue.length) return;
    var batch = queue.splice(0, BATCH_LIMIT);
    post(batch, JSON.stringify({ events: batch }), 1);
  }

  function post(batch, body, attempt) {
    sending = true;
    fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      credentials: "same-origin",
      body: body,
      keepalive: true,
    }).then(function (response) {
      sending = false;
      if (response.status === 403 || response.status === 401) { disable(); return; }
      if (!response.ok) retryOrDrop(batch, body, attempt);   /* 503s retry; 400s drop */
      else if (queue.length) flush();
    }).catch(function () {
      retryOrDrop(batch, body, attempt);
    });
  }

  function retryOrDrop(batch, body, attempt) {
    if (attempt >= MAX_ATTEMPTS) return;   /* bounded: drop the batch, keep going */
    setTimeout(function () {
      if (!disabled) post(batch, body, attempt + 1);
    }, 400 * attempt);
  }

  function disable() {
    disabled = true;
    queue = [];
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
  }

  /* --- Capture: one listener per event type, on the document, in the capture
         phase. Dynamic interfaces need no re-wiring, and no page handler can
         prevent these observations. --- */

  document.addEventListener("click", function (event) {
    if (disabled) return;
    var control = clickableFrom(event.target);
    if (!control || !inScope(control) || isSensitive(control)) return;
    enqueue({
      action: "activate",
      control_kind: kindOf(control),
      control_id: identityOf(control),
      label: labelOf(control),
    });
  }, true);

  document.addEventListener("change", function (event) {
    if (disabled) return;
    var control = event.target;
    if (!control || control.nodeType !== 1 || !inScope(control) || isSensitive(control)) return;
    var tag = tagName(control);
    var action = null;
    if (tag === "select") action = "choose";
    else if (tag === "textarea") action = "complete";
    else if (tag === "input") {
      var type = String(control.getAttribute("type") || "text").toLowerCase();
      if (type === "checkbox" || type === "radio") action = "toggle";
      else if (type === "button" || type === "submit" || type === "reset") return;
      else action = "complete";
    } else return;
    var item = {
      action: action,
      control_kind: kindOf(control),
      control_id: identityOf(control),
      label: labelOf(control),
    };
    var selection = selectionOf(control);
    if (selection) item.selection = selection;
    enqueue(item);
  }, true);

  document.addEventListener("submit", function (event) {
    if (disabled) return;
    var form = event.target;
    if (!form || tagName(form) !== "form" || !inScope(form)) return;
    enqueue({
      action: "submit",
      control_kind: "form",
      control_id: identityOf(form),
    });
  }, true);

  /* --- Delivery: single-flight FIFO keeps arrival order equal to observation
         order; the server's sequence counter then serializes batches against
         navigations and record outcomes on the one timeline. pagehide and
         hidden tabs flush through keepalive requests that survive unload. --- */

  function flushNow() {
    if (!disabled && queue.length) {
      var batch = queue.splice(0, Math.min(queue.length, BATCH_LIMIT));
      try {
        fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
          credentials: "same-origin",
          body: JSON.stringify({ events: batch }),
          keepalive: true,
        });
      } catch (error) { /* unloading: nothing further is possible */ }
    }
  }

  window.addEventListener("pagehide", flushNow);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") flushNow();
  });
})();
