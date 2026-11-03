# UI 4 — simulator embedding and recording feasibility

Date reviewed: 2026-11-02

## Executive decision

The actual Django simulator can be reused in the Demonstration Studio through a same-origin iframe. The repository already has the essential per-response framing mechanism: simulator GET responses loaded with `Sec-Fetch-Dest: iframe` receive `X-Frame-Options: SAMEORIGIN`, while the site-wide default remains `DENY` (`config/settings/base.py`, `scenarios/views.py::_frame_for_practice_desk`). Session authentication, cookies, CSRF tokens, redirects and ordinary simulator navigation therefore remain first-party and compatible.

Embedding is **not ready to implement safely yet** because simulator writes are owned by `request.user`. In an instructor frame, a save or submit would create ordinary instructor-owned UCR, BOE, consignment or MDA records. A demonstration-session data boundary must be implemented and tested before the iframe is allowed to perform writes.

The revised standalone prototype demonstrates the required recording lifecycle but does not embed or imitate the real simulator. Its simulator area is explicitly a placeholder; all recording behaviour is browser-only and says that nothing is saved or verified.

## Evidence from the current application

### Routes and navigation

- Simulator URLs are under the same Django origin and `/practical/` namespace. `scenarios/urls.py` exposes the portal, Single Window, UCR, consignment, MDA, BOE, clearance and supporting search/detail routes.
- `templates/core/base_simulator.html` owns the simulator chrome and navigation, so framing actual route responses reuses the interface without duplication.
- Guided authoring already uses an approved target registry, `scenarios.bindings.SIMULATOR_BINDING_ROUTES`. It is a suitable starting allowlist for initial frame entry and navigation capture, but it does not cover every route reachable during a complete workflow.
- Full in-frame navigation is feasible because links and POST redirects remain in the iframe. The parent should reject any frame navigation outside the simulator path allowlist.

### Authentication and permissions

- `simulator_access_required` admits authenticated staff, superusers, Instructor-group and Administrator-group users without the separate student simulator credential.
- `lesson_demonstration_studio` is login-protected, calls `_require_instructor`, resolves a draft lesson, and accepts GET only.
- Student review mode is view-only and its write guards must not be reused as demonstration mode; it represents another student's data, not isolated instructor demonstration data.
- Every framed route used by the studio must pass an explicit route audit. Routes that are public, omit `simulator_access_required`, or are unrelated to authoring must not enter the frame allowlist.

### Session and CSRF

- Parent and iframe are same-origin, so they use the same authenticated Django session.
- Simulator forms render Django CSRF tokens. Same-origin form POSTs retain the CSRF cookie and Origin/Referer relationship; no CSRF exemption is needed.
- `SESSION_COOKIE_HTTPONLY` and `CSRF_COOKIE_HTTPONLY` are enabled. Production also enables secure cookies and HTTPS redirect. No weakening is required.
- The implementation must keep the iframe on the application origin. A different subdomain would change cookie/SameSite and CSRF assumptions and is outside this proposal.

### Framing protections

- The global `X_FRAME_OPTIONS` value is `DENY`.
- `_frame_for_practice_desk` changes only eligible simulator GET responses whose browser request destination is an iframe to `SAMEORIGIN`.
- This pattern is appropriate for UI 4 and must remain per-view/per-response. Do not change the global header and do not add a broad CSP `frame-ancestors` rule.
- Add a studio-specific frame-entry allowlist rather than treating every `/practical/` response as a valid Demonstration Studio destination.
- Add CSP `frame-src 'self'` on the studio response if CSP is introduced, and keep framed responses limited to `frame-ancestors 'self'`. Header behaviour must be tested at the deployed proxy as well as in Django tests.

### Scrolling and responsive sizing

- Use an iframe inside the approved simulator panel with a bounded responsive height, for example `clamp(34rem, 72vh, 58rem)`, `width: 100%`, and its own scroll context.
- The iframe document should retain its own responsive simulator layout. The studio must not clone the simulator navigation or resize the frame based on unrestricted child messages.
- Provide a same-origin “open simulator in new tab” recovery link for unusually small screens and accessibility, subject to copy approval when production work begins.

### Cross-window communication

- No current simulator code uses `postMessage` for this workflow.
- Do not add a wildcard message listener or accept child-supplied event names, selectors, URLs or payloads.
- Prefer server-side event capture for successful writes and outcomes. For navigation and approved selections, the same-origin parent may bind narrowly to the framed document after each load using a versioned selector/route allowlist. This requires no general cross-window message bus.
- If `postMessage` becomes necessary later, both sides must require the exact origin, verify `event.source === iframe.contentWindow`, validate a small versioned schema, reject unknown event types/fields, and never accept record IDs or text values that the server has not authorized for the active demonstration session.

## Recording architecture proposal

### Event taxonomy and allowlist

Only the following event families may be recorded:

| Family | Examples | Capture source | Stored payload |
|---|---|---|---|
| Navigation | Open Single Window; open UCR create; open saved record detail | iframe load plus resolved Django route name | route name, safe screen label |
| Meaningful selection | Choose regime `IM`; choose transport mode | explicit field-selector manifest | field semantic key and approved choice code; never arbitrary text |
| Record creation/update | UCR draft created; BOE draft updated | server-side service/view after successful transaction | record kind, opaque demonstration record reference, operation |
| Save/submit outcome | draft saved; submit accepted/rejected | server-side outcome after validation/commit | outcome code, status, safe validation category |
| Verification-relevant change | record reaches submitted/assessed state | model/service transition hook | record kind, from/to status, verification capability key |

Never capture passwords, simulator credentials, CSRF/session tokens, headers, cookies, uploaded file contents, names/addresses, free-text descriptions, unrelated clicks, keystrokes or DOM snapshots. Free-text fields may produce a semantic event such as `goods_description_completed` with no value and, if useful, a coarse non-sensitive flag such as `present: true`.

### Lifecycle

1. Instructor opens a draft lesson’s studio. No recording exists yet.
2. **Start Recording** creates a server-side `DemonstrationSession` in `recording` state and issues a random, session-bound identifier. Repeated starts are idempotent or rejected.
3. **Pause** changes state to `paused`; capture endpoints and server hooks ignore new events while paused. Simulator use may continue.
4. **Resume** returns the same session to `recording` without resetting sequence numbers.
5. **Stop** seals the event stream as `stopped`; no additional events may be appended. It does not create lesson steps.
6. The instructor reviews the ordered timeline, selects events, groups them and explicitly creates editable lesson-step drafts.
7. **Discard** requires confirmation, marks the session discarded, removes or schedules deletion of demonstration records, and makes captured events unavailable to normal authoring queries. Use a retention job for any audit tombstone required by policy.

### Attribution and ordering

- `DemonstrationSession` belongs to the instructor and one draft `HybridLesson`; store created/started/paused/stopped/discarded timestamps and state.
- Bind the active session to the authenticated Django session with a signed value and verify instructor, lesson and state on every capture.
- Allocate event sequence numbers inside a database transaction using a row lock on the demonstration session. Store server timestamp as supporting metadata, not as the primary order.
- Client-generated IDs may be used only as idempotency keys. They must not determine authorization or ordering.

### Review and conversion

- Timeline entries are immutable facts. Instructor selection/grouping is separate review metadata.
- “Create lesson-step drafts” copies approved summaries into draft authoring records; it must never copy captured free text because none is retained.
- Draft conversion is explicit and idempotent. Store provenance from each draft to selected event IDs so a reviewer can see why it was proposed.
- The instructor must edit and approve title, instruction, expected outcome, route binding and verification conditions through the existing lesson authoring validation. Captured events do not prove that a lesson is publish-ready and do not count as student verification.

### Data isolation

The safest model is explicit demonstration scope, not inference from staff ownership.

- Add a nullable `demonstration_session` foreign key (or an equivalent dedicated demonstration-record relation) to each simulator record type that can be created in a recording: initially UCR, consignment, MDA and BOE.
- Require demonstration-mode writes to set that scope server-side. Do not accept it from form input.
- Normal student and instructor simulator querysets must exclude demonstration-scoped rows unless the request is authorized for that exact session.
- Demonstration lookups must require both normal ownership rules and the active session scope. Raw primary keys are insufficient authorization.
- Demonstration records must not create `SimulatorRecordCreation`, journey attribution, completion, assessment or student verification evidence. Existing post-save capture signals must explicitly ignore demonstration-scoped rows.
- Files created during a demonstration need the same scope and discard/retention cleanup.
- Do not implement demonstration isolation with a long-lived transaction spanning browser requests, a name prefix, a client flag, or cleanup alone.

### Proposed schema (not implemented)

- `DemonstrationSession`: UUID, lesson FK, instructor FK, state, timestamps, event counter/version.
- `DemonstrationEvent`: session FK, sequence, event type, route name, safe semantic key, sanitized JSON payload, server timestamp, idempotency key; unique `(session, sequence)` and `(session, idempotency_key)`.
- `DemonstrationDraftGroup`: session FK, ordering, instructor label/instructions/outcome draft, review status.
- `DemonstrationDraftEvent`: group/event join table preserving selected-event order.
- Demonstration scope on supported simulator records, or dedicated demonstration tables if product policy requires physical separation.

Do not create `PracticalStep` rows at recording time. Conversion should occur only after instructor review and should feed the existing editor’s draft/validation path.

## Required permissions

- Start/view/pause/resume/stop/discard: instructor who owns the session, Administrator, or explicitly assigned co-author if co-authoring is later approved.
- Convert events: same authorization plus edit permission on the draft lesson/version.
- View demonstration simulator records: exact active session only; no cross-instructor or cross-lesson access by guessed UUID.
- Students have no demonstration endpoints, events, drafts or records in their querysets.
- Publishing remains governed by current lesson readiness and edition rules.

## Implementation stages

1. **Security foundation:** models/migrations, permissions, state machine, signed active-session binding, scoped record manager/query helpers, retention policy.
2. **Isolation adapter:** apply demonstration scope to UCR first; suppress learner attribution/evidence; prove discard and cross-user denial. Expand only after the pattern passes review.
3. **Real iframe:** replace the production mock with the actual portal/approved route in a same-origin iframe; retain global `DENY`; add studio-specific route allowlist and responsive frame treatment.
4. **Server event stream:** capture navigation and UCR create/update/save/submit outcomes with sanitization, sequencing and idempotency.
5. **Selection capture:** add the smallest selector manifest for meaningful enum/radio choices; never read text values. Extend route by route.
6. **Review UI:** lifecycle controls, timeline, selection/grouping, discard confirmation and empty/error/retry states.
7. **Draft conversion:** create editable draft groups, map them through the existing activity editor, require instructor approval, then add other simulator record families.
8. **Hardening and rollout:** CSP/proxy verification, accessibility, concurrency, cleanup, audit logging, feature flag and staged instructor pilot.

## Test plan

### Framing and navigation

- Normal simulator response remains `X-Frame-Options: DENY`.
- Approved iframe GET receives `SAMEORIGIN`; non-approved routes remain denied.
- Cross-origin framing is blocked; studio CSP permits only self.
- Portal links, nested navigation, POST-redirect-GET and independent scrolling work inside the frame at desktop/tablet/mobile widths.
- Authentication expiry and simulator-login redirects stay inside a safe first-party flow.

### CSRF and sessions

- Valid framed form POST succeeds with the existing CSRF token.
- Missing/invalid token and foreign Origin fail.
- Secure/HttpOnly cookies remain configured in production.
- Starting, pausing or discarding one recording cannot affect another browser session.

### Authorization and isolation

- Student/non-instructor cannot open a studio or recording endpoint.
- Instructor A cannot read or mutate instructor B’s demonstration session or records.
- Demonstration records never appear in student searches, review mode, verification, journey attribution, reports or ordinary instructor simulator searches.
- Normal simulator records cannot be attached to a demonstration by client input.
- Discard removes scoped data according to retention policy without touching ordinary records.

### Capture safety

- Every allowed event schema accepts only documented fields and enum values; unknown types/keys are rejected.
- Password, token, cookie, CSRF value, free text and uploaded content never persist, including in logs and error traces.
- Paused/stopped/discarded sessions reject append attempts.
- Concurrent events receive unique monotonic sequence numbers; retries deduplicate by idempotency key.
- Failed/rolled-back writes do not produce success events. `transaction.on_commit` events do.

### Review and conversion

- Selection and grouping do not mutate immutable events.
- Conversion is explicit, authorized and idempotent.
- Generated drafts remain unpublished and fail readiness checks until required fields/verification are approved.
- Deleting/discarding a recording cannot delete already instructor-approved lesson content without a separate confirmed authoring action.

### Prototype acceptance

- Idle, recording, paused, stopped and review states render.
- Captures occur only while recording.
- Pause suppresses capture; resume continues sequence; stop enables selection; discard requires confirmation.
- All status and toast text continues to say simulated/not saved/not verified.

## Decisions requiring approval before production implementation

1. Approve explicit demonstration scope on simulator records versus physically separate demonstration record tables. Explicit scope is the smaller change; separate tables provide stronger physical separation at much higher duplication cost.
2. Approve the retention rule for discarded/stopped demonstration sessions and any uploaded files.
3. Approve the initial record-family rollout (recommended: UCR only before consignment, MDA and BOE).
4. Approve the exact navigation/field allowlist for each supported workflow.
5. Approve production copy and any template/CSS changes under the 2026-10-09 theme/copy lock.
6. Decide whether co-authors/administrators may resume or convert another instructor’s recording.

No production view, model, simulator template, database schema or locked stylesheet was changed for this revision.
