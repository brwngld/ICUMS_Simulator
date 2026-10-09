# Deferred security findings (pre-launch hardening list)

Agreed with the product owner on 2026-10-09: none are urgent for the training
simulator, but **#1 must be fixed before any real cohort uses the system
concurrently**. Re-audit or fix at pre-launch.

## 1. BOE creation accepts another student's IDF (HIGH — fix pre-launch)
`scenarios/views.py` — `boe_idf_lookup` (~line 1907) and `boe_create` (~2118)
look up `MdaConsignmentRequest` by IDF number with no ownership check. A
student can enter another student's IDF, leak the victim's UCR number, and
create a BOE whose `form_data` snapshots the victim's consignment. Also burns
the victim's UCR (one-BOE-per-UCR).
Fix: add `consignment_application__owner=request.user` to both queries.

## 2. Stored XSS in the admin (MEDIUM)
`scenarios/admin.py` (~268) + `templates/admin/scenarios/trainingserviceprovider/change_form.html`:
`json.dumps` output injected via `|safe` into a script tag; a stakeholder
name/address containing `</script>` breaks out. Staff-only injection path.
Fix: `json_script` or the JSON.parse-of-script-element pattern.

## 3. No brute-force protection on logins (MEDIUM)
`simulator_login` and the learning-account login have no attempt counter or
lockout. Fix: django-axes or a cache-based attempt counter.

## 4. Missing transport hardening in `config/settings/vps.py` (LOW)
No `SECURE_HSTS_SECONDS` / `SECURE_SSL_REDIRECT` / `SECURE_HSTS_INCLUDE_SUBDOMAINS`.
Set once HTTPS + the domain are live.

## Cleared during the 2026-10-09 audit
Ownership checks verified across UCR/BOE/consignment/MDA/assessment/
evaluations/reports endpoints; reset flow enumeration-safe; cookie flags and
frame options set. SQLite findings excluded (PostgreSQL planned).
