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

Press `Ctrl+C` in PowerShell when you want to stop the server.

## 5. Create a test student

Sign in to Django Admin using the administrator account created earlier.

1. Open **Users**.
2. Select **Add user**.
3. Enter a username and password.
4. Save and continue editing the user.
5. Add the student's email address if required.
6. Assign the user to the **Student** group.
7. Save the user.

## 6. Enrol the test student

In another PowerShell window, or after temporarily stopping the server, run:

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo_content --username YOUR_USERNAME
```

Replace `YOUR_USERNAME` with the test student's actual username. This assigns the Student role if needed and enrols the account in the demonstration programme.

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
```

The correct answer in the fictional demonstration question is:

> Investigate and resolve the inconsistency

The example intentionally shows an invoice quantity of 120 cartons and a packing-list quantity of 102 cartons.

## 8. Review the instructor experience

To give an account instructor access:

1. Open the user in Django Admin.
2. Add the user to the **Instructor** group.
3. Save the user.

After signing in with that account, use the **Instructor** navigation link to review student progress and assessment attempts.

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
- Automated tests: 25 passed

## Current limitations

- The curriculum and assessment content are fictional placeholders.
- Practical evaluation, competency scoring, and remediation are planned for Phase 4.
- Practical layouts have not been validated against permitted ICUMS reference material.
- The development server is for local review only and must not be exposed to the internet.
- Backup/restore automation and packaged local production serving remain pending operational work.
- No official customs transaction, declaration, payment, release, or shipment activity occurs in this application.

## Related documentation

- [Local development](local-development.md)
- [Implementation status](implementation-status.md)
- [Product rules](product-rules.md)
- [System architecture](architecture.md)
