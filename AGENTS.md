# Working agreements

## Message intent: classify before acting (2026-11-11)

Every message from Bernard has an intent. **Classify it before doing
anything.** The intents are:

- **Question** — answer it. Do not implement, do not edit files, do not
  start solving. Just answer.
- **Statement** — acknowledge it. It may be context, a decision, or
  thinking out loud. Do not treat it as a work order.
- **Comment** — note it. It may be feedback on something already done.
  Do not act on it unless Bernard explicitly asks for a change.
- **Command** — do exactly what is commanded, nothing more. "Stop"
  means stop. "Fix X" means fix X, not fix X and also Y and Z.
- **Request** — do what is requested. If the scope is unclear, ask
  **before** implementing. Never assume scope.
- **Design discussion** — engage with the ideas. Do not jump to code.
  Wait for an explicit "build it" or "proceed."

**When in doubt about what a message wants, ask for clarification
before implementing.** Never guess intent and start editing.

A question mark usually means a question. A declarative sentence
usually means a statement. Read the message, decide the intent, act
according to that intent — and only that intent.

## Theme, styling and copy are LOCKED (2026-10-09)

The visual theme — colours, fonts, font sizes, spacing, dark/light
palettes — and all user-facing writing (labels, headings, copy) are
frozen as of 2026-10-09 (sidebar unification). Per Bernard's
instruction, **no change to
the theme or to user-facing text may be made without his explicit
approval first.** Propose the change and wait for a yes; do not edit
stylesheets, inline styles, theme scripts, or template copy on your own
initiative.

This covers, at minimum: `static/css/app.css`, `static/js/theme.js`,
the `UNFOLD` settings block, and the markup/copy of every template under
`templates/`. Bug fixes that must touch these files still require
approval of the intended visual/textual outcome before the edit.
