# Deferred security and code review

Reviewed on 18 September 2026. This is a decision log for future work, not a claim that the items below are already fixed. The current local server starts on a loopback address; that limits remote exposure but does not replace the deployment checks below.

## Required before real students use simulator credentials

### Private, stable Django secret

`config/settings/local_production.py` currently inherits the public development fallback `SECRET_KEY` from `config/settings/base.py`. Make the production-style local setting refuse to start unless `DJANGO_SECRET_KEY` is explicitly configured, as hosted `production.py` already does. Document how to generate, store, and back up the key for each installation without committing it. Verify that startup fails with the fallback key and succeeds with a private key.

The key signs Django data and participates in generating simulator passwords. A known key alone is not enough to derive a student's password without that student's stored nonce and user ID, but keeping the key private is still essential. Rotating it can invalidate sessions and change generated simulator passwords, so plan a credential reissue when it changes.

### Throttle credential and reset requests

`simulator_login` and `simulator_reset_request` in `scenarios/views.py` currently accept repeated anonymous POSTs without a cooldown. Add limits by both source address and normalized student ID, use a generic response that does not reveal whether an ID exists, and expire counters automatically. Cover repeated failures, a successful login, and reset-request floods with tests. Choose a backing store that works across processes before multi-worker or hosted deployment.

**Gate:** finish both items above before issuing simulator credentials to real students or exposing the service beyond a developer-only local session.

## Before hosted deployment or broader access

- Recheck `scenario_document_pdf` learner access against the scenario version's publication policy. `BillOfLading` and `CommercialDocument` PDF views explicitly require published document status; `ScenarioDocument` has no separate status field. Decide whether a retired or draft version should remain downloadable through an existing attempt, then make the rule consistent and test it.
- Replace interpolated `innerHTML` in the older Opt In/Out pages (`single_window_search_opt_in_out.html` and `static/js/opt-in-out-detail.js`) with DOM creation and `textContent` before values can come from instructor input or server records.
- Review production domain/proxy settings, including `CSRF_TRUSTED_ORIGINS`, secure cookies, HSTS duration, and referrer policy, against the actual HTTPS deployment. Do not invent domain values in advance.
- Review the instructor dashboard's display of simulator passwords for the chosen operational workflow, especially shared screens and access permissions.

## Maintenance when these areas are next touched

- Remove the redundant self-merge branch in `TrainingStakeholder.clean()` and the pass-through `TrainingStakeholderAdmin.save_model()` override after confirming current merge tests still pass.
- Remove the unused `templates/scenarios/single_window_create_ucr.html` only after verifying that no route, include, or test still references it.
- Review the 70 tracked intermediate files under `tmp/`. Identify wanted artifacts before removing them from Git tracking; ignore future render output once the retained files have a deliberate home.
- Preserve the existing applied migrations, including the UCR stakeholder migrations. Do not squash or rewrite their history casually: this database and possibly another machine may already depend on those migration identifiers.

The pasted review's broad statements about the absence of all SQL injection, XSS, or access-control defects are not a substitute for a later focused security test. Reassess those claims when workflows begin accepting less-controlled content or the deployment surface changes.
