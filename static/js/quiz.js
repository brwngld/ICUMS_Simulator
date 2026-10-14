/* Theory assessment quiz stepper. The questions are server-rendered inside a
   single form; this script only pages between them, tracks progress, and
   builds the review step before the existing submit posts everything. */
(() => {
  const form = document.querySelector("#quiz-form");
  if (!form) return;
  const cards = [...form.querySelectorAll("[data-quiz-card]")];
  const reviewCard = form.querySelector('[data-quiz-card="review"]');
  const questions = cards.filter((card) => card !== reviewCard);
  const prev = form.querySelector("#quiz-prev");
  const next = form.querySelector("#quiz-next");
  const reviewBtn = form.querySelector("#quiz-review-btn");
  const submit = form.querySelector("#quiz-submit");
  const hint = form.querySelector("#quiz-hint");
  const counter = document.querySelector("#quiz-counter");
  const fill = document.querySelector("#quiz-progress-fill");
  const progress = document.querySelector(".quiz-progress");
  const reviewList = document.querySelector("#quiz-review");
  const position = document.querySelector("#quiz-position");
  const dotsHost = document.querySelector("#quiz-dots");
  const total = questions.length;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let current = 0; // index into questions; review is "current === total"
  const marked = new Set();
  const dots = questions.map((card, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quiz-dot";
    button.textContent = String(index + 1);
    button.setAttribute("aria-label", `Go to question ${index + 1}`);
    button.addEventListener("click", () => show(index));
    dotsHost.append(button);
    const mark = card.querySelector("[data-mark-review]");
    mark.addEventListener("click", () => {
      if (marked.has(index)) marked.delete(index); else marked.add(index);
      mark.classList.toggle("is-marked", marked.has(index));
      mark.textContent = marked.has(index) ? "♥ Marked for review" : "♡ Mark for review";
      updateIndicators();
    });
    return button;
  });

  const answered = (card) => [...card.querySelectorAll("input[type=radio]")].some((input) => input.checked);
  const answeredCount = () => questions.filter(answered).length;
  let saveTimer;

  function saveProgress() {
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(() => {
      const data = new FormData(form);
      data.set("action", "save_progress");
      fetch(form.action || window.location.href, {
        method: "POST",
        body: data,
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      }).catch(() => {
        hint.textContent = "Your answer is selected locally, but could not be saved yet.";
      });
    }, 150);
  }

  function refreshReview() {
    reviewList.replaceChildren();
    questions.forEach((card, index) => {
      const prompt = card.querySelector("legend").childNodes[card.querySelector("legend").childNodes.length - 1].textContent.trim();
      const selected = card.querySelector("input[type=radio]:checked");
      const label = selected ? selected.closest(".quiz-option").querySelector("span:last-child").textContent : "Not answered yet";
      const li = document.createElement("li");
      li.className = `${selected ? "is-answered" : "is-missing"}${marked.has(index) ? " is-marked" : ""}`;
      const open = document.createElement("button");
      open.type = "button";
      open.className = "quiz-review-open";
      open.textContent = `${index + 1}. ${prompt}`;
      open.addEventListener("click", () => show(index));
      const choice = document.createElement("span");
      choice.className = "quiz-review-choice";
      choice.textContent = `${selected ? "Answered" : "Unanswered"}${marked.has(index) ? " · Marked for review" : ""}`;
      choice.title = selected ? label : "Not answered";
      li.append(open, choice);
      reviewList.append(li);
    });
  }

  function updateIndicators() {
    dots.forEach((dot, index) => {
      dot.classList.toggle("answered", answered(questions[index]));
      dot.classList.toggle("marked", marked.has(index));
      dot.classList.toggle("current", current === index);
    });
  }

  function show(target) {
    current = Math.min(Math.max(target, 0), total); // total === review step
    cards.forEach((card) => { card.hidden = true; });
    const active = current === total ? reviewCard : questions[current];
    active.hidden = false;
    if (current === total) {
      refreshReview();
      counter.textContent = `Review your answers · ${answeredCount()} of ${total} answered`;
      progress.setAttribute("aria-valuenow", String(answeredCount()));
      position.textContent = "Review";
    } else {
      counter.textContent = `Question ${current + 1} of ${total} · ${answeredCount()} answered`;
      progress.setAttribute("aria-valuenow", String(current + 1));
      position.textContent = `${current + 1} / ${total}`;
    }
    prev.hidden = current === 0;
    next.hidden = current >= total - 1;
    reviewBtn.hidden = current !== total - 1;
    submit.hidden = current !== total;
    const ratio = current === total ? answeredCount() / total : (current + 1) / total;
    fill.style.width = `${Math.round(ratio * 100)}%`;
    updateIndicators();
    hint.textContent = "";
    submit.disabled = answeredCount() < total;
    if (current === total) {
      const missing = total - answeredCount();
      hint.textContent = missing ? `${missing} question${missing > 1 ? "s" : ""} still unanswered — answer every question to submit.` : "All questions answered. Submit when you are ready.";
    }
    if (!reduceMotion) {
      active.classList.remove("quiz-enter");
      void active.offsetWidth; // restart the transition
      active.classList.add("quiz-enter");
    }
    active.scrollIntoView({ block: "nearest" });
    const focusTarget = active.querySelector("input[type=radio]") || active.querySelector("button") || active;
    if (focusTarget) focusTarget.focus({ preventScroll: true });
  }

  prev.addEventListener("click", () => show(current - 1));
  next.addEventListener("click", () => {
    if (!answered(questions[current])) {
      hint.textContent = "Choose an answer before moving on — you can come back and change it.";
      return;
    }
    show(current + 1);
  });
  reviewBtn.addEventListener("click", () => show(total));
  questions.forEach((card) => {
    card.querySelectorAll("input[type=radio]").forEach((input) => {
      input.addEventListener("change", () => {
        saveProgress();
        const ratio = answeredCount() / total;
        fill.style.width = `${Math.round((current === total ? ratio : Math.max(ratio, (current + 1) / total)) * 100)}%`;
        counter.textContent = `Question ${current + 1} of ${total} · ${answeredCount()} answered`;
        updateIndicators();
        if (hint.textContent.startsWith("Choose an answer")) hint.textContent = "";
      });
    });
  });
  form.addEventListener("submit", (event) => {
    if (answeredCount() < total) {
      event.preventDefault();
      hint.textContent = "Answer every question before submitting.";
      show(questions.findIndex((card) => !answered(card)));
    }
  });

  show(0);
})();
