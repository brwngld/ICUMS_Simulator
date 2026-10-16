/*
  Guide panel behaviour: check the step without reloading the simulator page,
  and remember whether the student left the panel open.

  Every control in the panel is a real form and works without this file: it
  posts and comes back to the same simulator page. The fetch is what lets a
  student who is mid-declaration keep their unsaved work while still seeing the
  result of a check, so a failure here falls straight back to the form post.
*/
(function () {
  "use strict";

  var OPEN_KEY = "icums.guide.open";

  function rememberOpenState(details) {
    var saved;
    try {
      saved = window.localStorage.getItem(OPEN_KEY);
    } catch (error) {
      return;
    }
    if (saved !== null) {
      details.open = saved === "1";
    }
    details.addEventListener("toggle", function () {
      try {
        window.localStorage.setItem(OPEN_KEY, details.open ? "1" : "0");
      } catch (error) {
        /* storage unavailable: the panel still opens and closes normally */
      }
    });
  }

  function announce(body) {
    var feedback = document.querySelector("[data-guide-feedback]");
    if (!feedback) {
      return;
    }
    feedback.textContent = body.getAttribute("data-notice") || "";
    feedback.setAttribute("data-tone", body.getAttribute("data-notice-tone") || "");
  }

  function refresh(form) {
    var button = form.querySelector("button");
    if (button) {
      button.disabled = true;
    }
    form.setAttribute("aria-busy", "true");
    fetch(form.action, { method: "post", body: new FormData(form) })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("guide request refused");
        }
        return response.text();
      })
      .then(function (html) {
        var next = new DOMParser().parseFromString(html, "text/html").querySelector("[data-guide-body]");
        var current = document.querySelector("[data-guide-body]");
        if (!next || !current) {
          window.location.reload();
          return;
        }
        current.replaceWith(next);
        announce(next);
      })
      .catch(function () {
        if (button) {
          button.disabled = false;
        }
        form.removeAttribute("aria-busy");
        form.submit();
      });
  }

  document.addEventListener("submit", function (event) {
    var form = event.target.closest ? event.target.closest("[data-guide-fetch]") : null;
    if (!form) {
      return;
    }
    event.preventDefault();
    refresh(form);
  });

  document.addEventListener("DOMContentLoaded", function () {
    var details = document.querySelector(".guide-shell");
    if (details) {
      rememberOpenState(details);
    }
  });
}());
