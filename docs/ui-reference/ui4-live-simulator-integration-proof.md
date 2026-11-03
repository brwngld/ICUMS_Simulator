# UI 4 — live simulator integration proof

Date: 2026-11-02

## Result

The development Demonstration Studio now renders the existing Django Cargo Tracking Dashboard in a same-origin iframe. No simulator UI is copied into the studio. The iframe loads the real view, template, shared navigation, Unfold shell and simulator stylesheets.

The proof is development-only. In non-DEBUG settings the view does not provide a simulator frame URL.

## Actual URLs and implementation

- Demonstration Studio: `/instructor/hybrid/lessons/<lesson UUID>/demonstration-studio/`
- Initial iframe URL: `/practical/portal/`
- Cargo navigation verified in-frame: `/practical/cargo/direct-delivery/`
- Dashboard view: `scenarios.views.simulator_portal`
- Dashboard template: `templates/scenarios/portal.html`
- Shared simulator shell/navigation: `templates/core/base_simulator.html`
- Simulator styles: `static/css/simulator-portal.css`, `static/css/dash.css`, Unfold assets loaded by the shared shell
- Studio view: `hybrid.instructor_views.lesson_demonstration_studio`
- Studio template: `templates/hybrid/demonstration_studio.html`
- Studio frame sizing: `static/css/demonstration-studio.css`

The initial frame visibly contains the real `Cargo tracking dashboard` header, service-area top navigation, fictional cargo search, Cargo services cards, Codes and Information panels, training exchange rates, notices and practice-activity panel.

## Development-only safety boundary

`scenarios.middleware.DemonstrationFrameSafetyMiddleware` is installed but becomes active only when all of these are true:

1. Django `DEBUG` is true.
2. The request path begins with `/practical/`.
3. The authenticated user is staff, superuser, Instructor or Administrator.
4. The browser identifies the document destination as an iframe with `Sec-Fetch-Dest: iframe`.

For that narrow request class:

- Only `/practical/portal/`, `/practical/cargo/`, `/practical/clearance/` and `/practical/single-window/` route families are allowed.
- Only GET and HEAD are accepted. POST and every other method are rejected before the simulator view runs.
- Responses receive `X-Frame-Options: SAMEORIGIN`.
- Responses receive `Content-Security-Policy: frame-ancestors 'self'`.
- Responses receive `Cache-Control: no-store`.

Normal top-level simulator traffic is unchanged. Student iframe traffic is unchanged. The global `X_FRAME_OPTIONS = "DENY"` setting remains unchanged. The proof does not rely on disabled controls or iframe sandbox attributes for write protection.

This boundary is intentionally conservative. It allows instructors to navigate and inspect existing GET screens, but any form or action requiring a write fails server-side. It must not be presented as a recording or demonstration-data implementation.

## Verification performed

- Focused Django suite: 8 tests passed.
- Real development server launched with `config.settings.local`.
- Authenticated instructor opened the real Demonstration Studio.
- Frame resolved to `/practical/portal/` and displayed the actual dashboard.
- Real Cargo top-navigation link opened `/practical/cargo/direct-delivery/` inside the same iframe and returned to the portal through the real simulator logo.
- Frame scrolling reached the lower notices/activity content while the outer studio `window.scrollY` remained unchanged.
- Recording controls remained visible beside the frame at desktop width and below it at tablet width.
- Server tests confirmed frame POST returns 405, an unapproved instructor-frame route returns 403, and equivalent student traffic remains unchanged.

The embedded dashboard emits an existing `chart.getContext is not a function` console warning from the shared Unfold/chart assets because the portal's practice-activity visual uses an SVG element with the `chart` class. The visible SVG chart renders and the warning predates this iframe proof; no simulator template or shared asset was changed to address it in this task.

## Screenshots

- `screenshots/ui4-live-frame-desktop.png` — actual dashboard, top navigation, search, Cargo services and recording controls.
- `screenshots/ui4-live-frame-independent-scroll.png` — iframe scrolled to the real Training notices and Practice activity panels while the studio shell and controls remain fixed.
- `screenshots/ui4-live-frame-tablet.png` — responsive tablet layout with the real simulator and recording controls.

## Remaining work before safe recording

1. Replace the broad development route-family prefixes with a versioned, product-approved route-name manifest for every supported workflow.
2. Design and approve demonstration-session data isolation. Current record writes still use `request.user`; no write may be enabled until demonstration records cannot enter student searches, verification, journey attribution, reports or ordinary instructor data.
3. Add demonstration-session lifecycle, event allowlist, sanitization, sequencing, idempotency and retention as described in `ui4-embedding-recording-feasibility.md`.
4. Decide how read-only transitions to scoped writes route by route. Removing the GET/HEAD restriction globally is not acceptable.
5. Add explicit authorization tests for every newly approved route and record family.
6. Resolve or formally accept the existing dashboard chart console warning.
7. Obtain approval for production copy/template/CSS changes under the theme and copy lock before promoting this development proof.

No recording persistence, demonstration record, database migration or database schema change was added. Nothing was committed, pushed or deployed.
