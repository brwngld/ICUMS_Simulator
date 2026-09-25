# How to Review the ICUMS Simulator Locally

This guide explains how to inspect the application currently implemented in the project.

The completed theory journey and the first Phase 3 practical-engine increment are ready for local review. The practical content remains fictional and its screen structure is conceptual pending approved ICUMS reference material.

## 1. Open PowerShell in the project

```powershell
cd C:\Users\Bernard\Desktop\learning\Icums_Simulator
```

## 2. Create an administrator account

Run:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Enter a username, email address, and password when prompted. Keep these credentials private.

## 3. Load the fictional demonstration content

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo_content
.\.venv\Scripts\python.exe manage.py seed_demo_scenario
```

The command is designed to be safely repeated. All content created by it is fictional and intended only to demonstrate the training flow.

## 4. Start the application

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Keep that PowerShell window open while using the application.

Open these addresses in a browser:

- Student application: `http://127.0.0.1:8000/`
- Django administration: `http://127.0.0.1:8000/admin/`
- Practical workspace frontend prototype: `http://127.0.0.1:8000/practical/portal/`

Press `Ctrl+C` in PowerShell when you want to stop the server.

For the production-style local server, use this instead:

```powershell
.\.venv\Scripts\python.exe start_local.py
```

It remains available only on this computer at `http://127.0.0.1:8000/`.

## 5. Create and enrol a test student

Sign in to Django Admin using the administrator account created earlier.

1. Open **Users**.
2. Select **Add user**.
3. Enter a username and password.
4. Save and continue editing the user.
5. Add the student's email address if required.
6. In the **Enrolments** section on the same user page, select the published demonstration programme version.
7. Leave the enrolment status as **Active**.
8. Save the user.

The Student group is assigned automatically when the enrolment is saved. The application also records which administrator created the enrolment.

## 6. Optional command-line enrolment shortcut

In another PowerShell window, or after temporarily stopping the server, run:

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo_content --username YOUR_USERNAME
```

Replace `YOUR_USERNAME` with the test student's actual username. This development shortcut assigns the Student role if needed and enrols the account in the demonstration programme. It is no longer required for the normal Django Admin workflow.

Restart the server if you stopped it:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

## 7. Review the student journey

Sign out of the administrator account and sign in with the test-student account.

The available journey is:

```text
Sign in
  -> Accept the simulator disclaimer
  -> View the student dashboard
  -> Open the theory roadmap
  -> Complete the fictional lesson sections
  -> Answer the embedded knowledge check
  -> Take the module assessment
  -> Take the final theory examination
  -> Complete simulator orientation
  -> Open Practical
  -> Start the guided fictional Import scenario
  -> Complete the main workflow and parallel shipping-line actions
  -> Reach simulated gate out
  -> Review the evidence-based practical result
  -> Return to Practical and complete the fictional competency check independently
  -> Open the automatically created training record and certificate
```

The guided scenario is practice-only and cannot issue a certificate. The seeded completion policy requires a passed final theory examination, completed orientation, and a passed **Competency assessment** scenario. V1 issues the certificate automatically; an administrator can enable future instructor approval under **Completion policies** in Django Admin.

The correct answer in the fictional demonstration question is:

> Investigate and resolve the inconsistency

The example intentionally shows an invoice quantity of 120 cartons and a packing-list quantity of 102 cartons.

## 8. Review the instructor experience

To give an account instructor access:

1. Open the user in Django Admin.
2. Add the user to the **Instructor** group.
3. Save the user.

After signing in with that account, use the **Instructor** navigation link to review student progress and assessment attempts.

Completed practical attempts include an **Evaluation** link. From that page an instructor can:

- review the original system score and criterion evidence;
- add feedback that is visible to the student or keep a private instructor note;
- revise the effective pass/fail outcome with a required reason.

An instructor revision does not overwrite the system result. Both outcomes, the instructor, reason, and timestamp remain recorded in the audit history.

One account can belong to both the **Administrator** and **Instructor** groups.

## 9. Run automated verification

From the project directory, run:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pytest -q
```

The most recently completed verification reported:

- Django system check: no issues
- Migration consistency: no changes detected
- Automated tests: 39 passed

## 10. Back up and restore local data

Create a ZIP containing the SQLite database and uploaded media:

```powershell
.\.venv\Scripts\python.exe manage.py backup_local_system
```

The archive is written to the `backups` directory. Copy it to a separate protected device or storage location. To restore a verified archive while the development server is stopped:

```powershell
.\.venv\Scripts\python.exe manage.py restore_local_system backups\YOUR_BACKUP_FILE.zip --confirm
```

Restore replaces the active local database. The command first retains a timestamped safety copy beside the current database. Media files from the archive are restored into the configured media directory.

## Current limitations

- The curriculum and assessment content are fictional placeholders.
- The current practical rubric and score are fictional demonstration rules, not an approved competency standard.
- Practical layouts have not been validated against permitted ICUMS reference material.
- The development server is for local review only and must not be exposed to the internet.
- Packaged local production serving and formal deployment-browser checks remain pending operational work.
- No official customs transaction, declaration, payment, release, or shipment activity occurs in this application.

## Related documentation

- [Local development](local-development.md)
- [Implementation status](implementation-status.md)
- [Product rules](product-rules.md)
- [System architecture](architecture.md)
- [Browser and accessibility review](browser-accessibility-review.md)
- [Practical interface reference log](practical-reference-log.md)
# Single Window navigation update

The simulator now links the full Single Window menu discovered from the authorised read-only reference: UCR (Create, Search, Transfer, Received), Exporter Registration, Opt In/Out, FCIE Registration, Preparation/Master/Consignment Applications, Bank Pre-Registration, Letter of Commitment, and Previous Data searches.

Open `http://127.0.0.1:8000/practical/single-window/` and use either the left navigation or the page cards. Transfer UCR and Received UCR reproduce the confirmed search fields, statuses, record columns, date controls, and pagination structure with fictional/empty practice data. Newly discovered pages use linked reference screens while their deeper workflows are inspected and implemented.

## Exporter Registration and Opt In/Out verification

- Create Exporter Registration: `http://127.0.0.1:8000/practical/single-window/exporter-registration/create/`
- Search Exporter Registration: `http://127.0.0.1:8000/practical/single-window/exporter-registration/search/`
- Create Opt In/Out: `http://127.0.0.1:8000/practical/single-window/opt-in-out/create/`
- Search Opt In/Out: `http://127.0.0.1:8000/practical/single-window/opt-in-out/search/`

The exporter screens include the confirmed certificate and GRA-office choices, representative details, item/eDocument columns, submission and approval dates, and registration result columns. Opt In/Out includes the confirmed MDA, branch, importer, product-group, GSA fee rule, submission/detail flow, and all five processing statuses. Simulator records remain fictional and browser-local.

## Application screens

- Preparation Create: `/practical/single-window/application/preparation/create/`
- Preparation Search: `/practical/single-window/application/preparation/search/`
- Master Create: `/practical/single-window/application/master/create/`
- Master Search: `/practical/single-window/application/master/search/`
- Consignment Create: `/practical/single-window/application/consignment/create/`
- Consignment Search: `/practical/single-window/application/consignment/search/`

Preparation reproduces the confirmed New Preparation Request and Application List screens. Master reproduces the confirmed New Master Request with the full eMDA list and dependent Application/Process selectors. Consignment currently uses the same linked, fictional reference-screen shell and is ready for its deeper fields when that screen is available for read-only inspection.

## Reviewing student work (staff, view-only)

Students sign in to the simulator with their Student ID and monthly password, and every UCR, consignment application, and MDA application belongs to the student who created it. Staff have two ways to see that work:

1. **Review login (view only).** Sign in with your own staff account and click **Simulator sign out** on the workspace home: the popup offers **Review student work** — enter the student's ID or name (no password needed) and browse the Single Window menus — you see that student's UCRs, consignment applications, and MDA applications exactly as they do, whether draft or submitted. Saving, submitting, editing, cloning, and deleting are disabled while reviewing, and a banner in the sidebar names the student you are viewing. Use **Exit review** (sidebar or the same popup) to return to your own workspace.
2. **Django Admin.** UCR declarations, consignment applications, and MDA consignment requests are registered in Advanced administration with a **Student** column showing which student created each record; search by student ID, name, or record number.

Both routes are read-only for student records: corrections are the learner's to make.

## Simulator student IDs and monthly passwords

- A student's **ID** (for example `BERN00001/26`) is allocated automatically the first time their simulator login is issued: four letters from the first name, a five-digit sequence, and the year.
- The **monthly password** is generated randomly at issue, stored only as a hash, and **shown exactly once** on the instructor dashboard's one-time password screen (with a Copy button). It is never displayed or stored in a readable form again — if it is lost, use "Reset monthly password" to generate a new one.
- Passwords expire at the end of the month. Students can flag "Request password reset" from the simulator login dialog, which shows on the instructor dashboard.
- The one-time reveal lives on the instructor dashboard only; Django Admin shows credential status (never the password) and can create a credential record, but the reveal happens at an instructor reset.
