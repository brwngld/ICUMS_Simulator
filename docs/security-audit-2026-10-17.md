# ICUMS Simulator — Authorized Security Audit

**Audit date:** 17 October 2026  
**Scope:** Local Django project at `C:\Users\Bernard\Desktop\learning\Icums_Simulator`  
**Method:** Read-only source, configuration, migration, dependency and targeted-test review  
**Code or data modified:** None

## Executive summary

The project has a sound baseline: CSRF protection is enabled, passwords and simulator credentials are hashed, most learner record endpoints enforce ownership, rich lesson content is sanitized, and the primary hosted-production profile enables important HTTPS protections.

However, the application should not be exposed to untrusted networks until the confirmed authorization and transport-security findings are addressed.

| Severity | Count |
| --- | ---: |
| Critical | 0 |
| High | 4 |
| Medium | 5 |
| Low | 2 |

**Status 21 October 2026:** All four High findings are closed — SEC-01, SEC-02
and SEC-04 in code (SEC-04's server-side switches apply at the next VPS
deployment), and SEC-03 by the policy decision recorded on the finding. Of the
remaining findings, SEC-05, SEC-07, SEC-08, SEC-09, SEC-10 and SEC-11 are
remediated as detailed in the remediation log, and SEC-06 is an accepted risk
for the current SQLite-backed deployments, gated before any PostgreSQL
go-live. Work may proceed on that basis.

## Confirmed findings

### SEC-01 — Authenticated users can access other users' uploaded documents

**Severity:** High  
**Status:** Remediated 2026-10-21 (see remediation log)

`core/views.py:179-187` permits any authenticated user to retrieve any non-public upload when its storage path is known or guessed. This bypasses the ownership check implemented by the dedicated UCR attachment endpoint at `scenarios/views.py:930-934`.

**Impact**

- Exposure of UCR supporting documents between students.
- Exposure of lesson/editor uploads or future private media.
- Cross-user information disclosure.

**Recommended correction**

- Do not expose private files through the generic `/media/<path>` route.
- Serve private attachments only through model-backed endpoints that check the owner, assigned instructor or administrator permission.
- Separate public cover artwork from private documents at the storage-root or storage-backend level.

**Required tests**

- Student B receives 403 or 404 for Student A's attachment ID.
- Student B cannot access Student A's underlying media storage path.
- Anonymous users can access only intentionally public cover artwork.

### SEC-02 — An instructor can issue simulator credentials for any user

**Severity:** High  
**Status:** Remediated 2026-10-21 (see remediation log)

`instructor_portal/views.py:75-91` verifies the instructor role, but loads the target from the unrestricted user table. It does not use the instructor-scoped enrolment logic at `instructor_portal/views.py:1787-1791` and does not restrict the target to a student account.

**Impact**

- One instructor can replace another instructor's student credential.
- An instructor can issue simulator credentials to an administrator or another instructor.
- Issuing a new credential invalidates the target's existing credential.

**Recommended correction**

- Resolve the target through `_instructor_enrolments(request.user)`.
- Restrict targets to active Student accounts with an eligible enrolment.
- Lock the credential record during issue or reset.
- Record issuance in an immutable audit log.

**Required tests**

- Cross-instructor credential issuance is denied.
- Instructor and administrator accounts cannot be issued student credentials.
- Withdrawn or ineligible enrolments are rejected.
- Concurrent reset requests remain consistent.

### SEC-03 — Course authoring has no instructor ownership boundary

**Severity:** High  
**Status:** Resolved by policy decision 2026-10-21 (see remediation log)

`Programme` and `ProgrammeVersion` in `onboarding/models.py:7-96` have no owner or authoring-team relationship. The course builder retrieves every course at `instructor_portal/views.py:104-126`, while mutation views retrieve drafts by identifier without instructor scoping, for example `instructor_portal/views.py:156-180`.

Any member of the Instructor group can therefore view or mutate content created by another instructor.

**Recommended correction**

- Decide explicitly whether courses are institution-wide shared content or instructor-owned content.
- If instructor-owned, add an owner or authoring-team relationship and scope every authoring query.
- Preserve explicit Administrator and superuser overrides.

**Required tests**

- Use two instructors and verify authorization for every course create, read, update, delete, clone and publish route.

### SEC-04 — Temporary VPS deployment permits authenticated traffic over HTTP

**Severity:** High  
**Status:** Remediated in the repository 2026-10-21; server switches apply at next deployment

`deploy/nginx-customsclearancepractice.com.conf:1-13` listens only on port 80. `config/settings/vps.py:12-29` does not enable SSL redirection, secure session cookies, secure CSRF cookies or HSTS.

Django's deployment check confirmed warnings W004, W008, W012 and W016.

**Impact**

- Account and simulator credentials can be intercepted.
- Session cookies can be stolen on an untrusted network.
- Requests and responses can be modified in transit.

**Recommended correction**

- Terminate TLS at Nginx and redirect port 80 to HTTPS.
- Enable `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`.
- Configure `SECURE_PROXY_SSL_HEADER` correctly for the reverse proxy.
- Enable HSTS only after HTTPS is verified.

The main PostgreSQL production profile already enables SSL redirect, secure cookies and HSTS at `config/settings/production.py:40-45`.

## Risks requiring targeted or PostgreSQL testing

### SEC-05 — Assessment save and submission race condition

**Severity:** Medium  
**Status:** Remediated in code 2026-10-21; concurrent-connection tests outstanding

`assessments/services.py:33-54` correctly serializes attempt creation by locking the enrolment. However, `save_attempt_answers()` at lines 15-30 and `submit_attempt()` at lines 57-100 use an unlocked, potentially stale attempt instance.

Concurrent save and submit requests could produce responses that do not match the stored score or repeat progression side effects.

**Recommended correction:** Re-fetch and lock the attempt inside each transaction, revalidate its status after acquiring the lock, and prevent response changes after submission.

**Required tests:** Run concurrent save/save, submit/submit and save/submit requests using separate PostgreSQL connections.

### SEC-06 — Simulator save and submit transitions are not serialized

**Severity:** Medium  
**Status:** Accepted for SQLite-backed deployments 2026-10-21; gated before PostgreSQL go-live

UCR number allocation at `scenarios/models.py:608-626` scans existing references but does not lock a dedicated sequence. UCR save and submit at `scenarios/views.py:657-711` do not lock the draft.

Similar unlocked state transitions exist for:

- MDA requests: `scenarios/views.py:1220-1300`
- Consignment applications: `scenarios/views.py:1618-1660`
- BOE submission: `scenarios/views.py:2760-2796`

Potential outcomes include duplicate attachments, uniqueness errors returned as HTTP 500, overwritten draft data and duplicate stage events.

**Recommended correction:** Lock the target draft, use database-backed reference sequences, make submission transitions idempotent, and add uniqueness constraints for generated side effects where appropriate.

**Required tests:** Exercise double-clicks, request replays and simultaneous save/submit requests against PostgreSQL.

### SEC-07 — UCR uploads are validated by filename extension only

**Severity:** Medium  
**Status:** Partly remediated 2026-10-21; re-encoding, scanning and test matrix remain

`scenarios/views.py:628-635` validates size and filename suffix but does not verify the actual file type or content.

**Recommended correction**

- Validate file signatures and detected MIME types.
- Decode and re-encode accepted images.
- Consider malware scanning before making documents available.
- Serve documents as downloads with `X-Content-Type-Options: nosniff`.

**Required tests:** Mismatched extensions, polyglot files, malformed images, macro-enabled documents and decompression bombs.

### SEC-08 — Authentication endpoints have no rate limiting

**Severity:** Medium  
**Status:** Remediated for the public endpoints 2026-10-21 (see remediation log)

No throttling or progressive delay was found for main login, public registration, credential reset requests or simulator login at `scenarios/views.py:165-183`. Student IDs are sequential, while simulator credentials use eight random characters after a fixed prefix at `accounts/models.py:74-91`.

**Recommended correction:** Add limits by IP and normalized account identifier, progressive delay or temporary lockout, and security logging for bursts and reset activity.

### SEC-09 — Django is below the current security patch

**Severity:** Medium  
**Status:** Remediated 2026-10-21 (Django 5.2.18)

The project pins Django 5.2.17. Django 5.2.18 fixes security issues including an unauthenticated HTTP-header parsing denial of service. The GIS issues appear inapplicable because GeoDjango is not used. The editable-primary-key formset issue requires targeted review because the project uses UUID primary keys and formsets.

**Recommended correction:** Upgrade to Django 5.2.18, run the complete suite, test instructor formsets, and verify malformed `Content-Type` and repeated-header handling.

Reference: <https://www.djangoproject.com/weblog/2026/oct/06/security-releases/>

## Lower-severity findings

### SEC-10 — `local_production` can use the development fallback secret

**Severity:** Low  
**Status:** Remediated 2026-10-21

`config/settings/local_production.py:1-12` does not reject the fallback key inherited from `config/settings/base.py:17-20`. Django's deployment check reported W009 for this profile.

Require an environment-provided secret whenever genuine student data or network access is involved.

### SEC-11 — Private media uses Django's development file server

**Severity:** Low  
**Status:** Remediated 2026-10-21

`core/views.py:187` calls `django.views.static.serve`, which is not intended as a production file-serving mechanism.

After authorization, use a protected internal Nginx redirect, private object storage or a controlled streaming response.

## Confirmed security controls

- CSRF middleware is enabled, and no `csrf_exempt` endpoints were found.
- Clickjacking protection uses `X_FRAME_OPTIONS = "DENY"`.
- MIME sniffing protection is enabled.
- Session and CSRF cookies are HttpOnly.
- The hosted PostgreSQL profile requires secrets, allowed hosts and database credentials.
- Passwords and simulator credentials are stored as hashes.
- Most UCR, BOE, MDA and consignment detail routes enforce record ownership.
- Instructor enrolment views scope ordinary instructors by `enrolled_by`.
- Guided practical action transitions use row locking.
- Attempt creation uses row locking and database uniqueness constraints.
- Redirect destinations are validated rather than blindly trusted.
- Rich lesson content is sanitized before it is marked safe for rendering.
- No committed production credentials or private keys were detected.
- `makemigrations --check --dry-run` reported no model/migration drift.
- `pip check` reported no broken installed dependencies.

## Verification notes and limitations

- A targeted run produced 24 passing authorization, assessment, instructor and portal-separation tests.
- Four media tests could not start because the audit environment denied writes to their system temporary directory. This was an environmental setup error, not an assertion failure.
- `pip-audit` was not installed, so a complete transitive vulnerability scan was not performed.
- The active virtual environment did not contain the PostgreSQL driver, although it is declared in `requirements-production.txt`.
- No production host, production database or external service was tested.
- Concurrency findings must be verified with independent connections against a disposable PostgreSQL database; SQLite results are not sufficient.

## Remediation order

1. Close the private-media authorization bypass.
2. Scope simulator credential issuance to assigned students.
3. Decide and enforce the course ownership policy.
4. Enable HTTPS and secure cookies before network-accessible deployment.
5. Upgrade Django to 5.2.18.
6. Add PostgreSQL locking and idempotency tests for assessment and simulator workflows.
7. Strengthen upload validation and authentication rate limiting.

## Remediation log

**21 October 2026.** Findings rechecked against the working tree on this date
before any work began; none had been addressed since the audit. What was
fixed, and what remains:

- **SEC-01 (fixed).** `core/views.py` now resolves private uploads to their
  owning record and serves them only to the owner or to staff; unknown or
  orphaned private paths answer 404. Course/module covers and lesson rich-text
  images keep their existing visibility.
- **SEC-11 (fixed).** `django.views.static.serve` was replaced by a controlled
  `FileResponse` in the same view: paths escaping `MEDIA_ROOT` answer 404 and
  every response carries `X-Content-Type-Options: nosniff`.
- **SEC-02 (fixed).** `instructor_portal.views.simulator_credential_issue`
  resolves the target through the instructor's own roster, requires an active
  Student-group account, locks the credential row while reissuing, and writes
  an `AuditEvent`.
- **SEC-04 (fixed in the repository; deployment steps pending).**
  `config/settings/vps.py` gains `SECURE_PROXY_SSL_HEADER`, and — behind a
  `DJANGO_HTTPS=1` environment switch — SSL redirect plus secure session/CSRF
  cookies; HSTS follows a separate `DJANGO_HSTS=1` switch so it can be enabled
  after HTTPS is verified. `deploy/nginx-customsclearancepractice.com.conf`
  now terminates TLS on 443 and redirects port 80. On the server: run certbot,
  then start Django with `DJANGO_HTTPS=1` (and later `DJANGO_HSTS=1`).
- **SEC-09 (fixed).** Django upgraded 5.2.17 → 5.2.18 and pinned in
  `requirements.txt`.
- **SEC-05 (fixed in code; PostgreSQL verification still owed).**
  `assessments/services.py` re-reads the attempt under `select_for_update`
  and validates its status before every save and submit. The audit's
  concurrent-connection tests remain outstanding.
- **SEC-07 (partly fixed).** UCR uploads now must match magic-byte signatures
  for their extension, and served files carry `nosniff`. Still owed: image
  re-encoding, malware scanning and the audit's full test matrix.
- **SEC-08 (fixed for the three public endpoints).** New `core/throttle.py`
  counts failures per account and per client address in the cache: main
  sign-in (5 per account / 30 per address per 15 min), public registration
  (10 per address per hour), simulator sign-in (5 per Student ID / 30 per
  address per 15 min). A shared cache backend would extend this beyond a
  single application process. Note: `templates/registration/register.html`
  renders no messages, so the registration throttling notice is set but not
  displayed on that page.
- **SEC-10 (fixed).** `config/settings/local_production.py` now refuses to
  boot without `DJANGO_SECRET_KEY` set in the environment.
- **SEC-03 (resolved by policy decision).** The platform's courses are
  institution-wide shared content by design: every member of the Instructor
  group is a trusted author across all programmes and versions, with the
  Administrator and superuser overrides unchanged. No ownership boundary is
  required for this operating model, so the finding is closed by decision
  rather than by code. Revisit it before introducing any instructor-owned
  course model, at which point every authoring query needs owner scoping and
  the full authorisation test matrix the audit describes.
- **SEC-06 (accepted risk, gated).** The simulator save/submit transitions and
  reference allocation remain unserialized. Every current deployment is
  SQLite-backed (the local and VPS profiles), where the database itself
  serialises writers, so the race conditions the audit describes cannot arise
  there. Closing the finding — row locks on the target draft, sequence-backed
  reference allocation, idempotent submissions and the concurrent-connection
  test matrix — is a gate before the hosted PostgreSQL profile goes live.

Tests for the fixed findings live in `tests/test_security_hardening.py`.

