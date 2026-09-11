# Browser and Accessibility Review

## Review date

6 September 2026

## Scope

This review covers the current local-first Phase 5 implementation. It is a technical and visual baseline, not a certification against WCAG or a substitute for testing with disabled users and assistive technologies.

## Automated checks

The test suite verifies that the student login page contains:

- an English document language;
- a main-content landmark;
- one primary page heading;
- a skip link targeting the main content;
- programmatically associated username and password labels.

It also verifies that the packaged launcher refuses network-facing bind addresses such as `0.0.0.0`.

## Live browser checks

The application was served through Waitress on `127.0.0.1` with `DEBUG=False` and static assets supplied by WhiteNoise. The following pages were inspected in the Codex in-app browser:

| Page | Result |
| --- | --- |
| Student sign-in | Styled successfully; one level-one heading; labelled username and password controls; sign-in button; skip-to-content link; visible keyboard focus. |
| Django Admin sign-in | Styled successfully; admin branding; labelled username and password controls; login button; Django skip-to-content link; visible focus. |

## Accessibility improvements included

- Skip-to-main-content link on simulator pages
- Stable `main-content` target
- High-visibility focus outline for links, buttons, fields, selects, text areas, and focusable regions
- Existing English document language and navigation landmarks retained
- Existing form labels retained for authentication, assessment, disclaimer, evaluation, and feedback controls

## Checks still required before institutional release

- Keyboard-only completion of the entire student journey
- Screen-reader testing with NVDA on Windows
- Browser zoom at 200% and 400%
- Reflow testing at narrow mobile widths
- Colour contrast measurement for every interactive state
- Error-message announcement and focus-management testing
- Testing with representative students, instructors, and administrators
- Current Chrome, Edge, and Firefox acceptance runs on the deployment hardware

Any defect found in these later checks should be recorded and corrected before the application is described as accessibility-conformant.
