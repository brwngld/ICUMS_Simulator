/* Record confirmation for practical journeys: the picker on a journey page and
the one inside a workspace step card are the same behaviour, so it lives here
once. Nothing is decided in the browser — the endpoint re-derives eligibility
from the server's own ledger and freshness rules, and this file only reports
what it answers. */
(() => {
  const messages = (form) => form.querySelector("[data-attribution-message]");

  document.querySelectorAll("[data-record-select]").forEach((button) => {
    const panel = document.getElementById(button.getAttribute("aria-controls"));
    if (!panel) return;
    button.addEventListener("click", () => {
      const opening = panel.hidden;
      panel.hidden = !opening;
      button.setAttribute("aria-expanded", String(opening));
      if (opening) panel.querySelector("input, button")?.focus();
    });
  });

  document.querySelectorAll("[data-attribution-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const status = messages(form);
      const submit = form.querySelector('button[type="submit"]');
      const selected = form.querySelector('input[name="record_choice"]:checked');
      if (!selected) {
        status.textContent = "Select a record before continuing.";
        status.dataset.tone = "fail";
        return;
      }
      submit.disabled = true;
      status.textContent = "Saving record selection…";
      status.dataset.tone = "pending";
      try {
        const response = await fetch(form.dataset.endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": form.querySelector('[name="csrfmiddlewaretoken"]').value,
          },
          body: JSON.stringify({[selected.dataset.attributionKey]: selected.value}),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "The record could not be attributed.");
        status.textContent = payload.message;
        status.dataset.tone = "pass";
        window.location.reload();
      } catch (error) {
        status.textContent = error.message;
        status.dataset.tone = "fail";
        submit.disabled = false;
      }
    });
  });
})();
