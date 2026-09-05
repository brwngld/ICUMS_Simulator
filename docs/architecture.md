# System Architecture

## Architectural goals

The V1 architecture favours clarity and reliable local operation while preserving a straightforward path to hosted deployment. It is a modular monolith: one Django project divided into focused Django apps, with one relational database and a private media store.

This is appropriate for the current scale of roughly 10 students and avoids the operational cost of microservices. Domain boundaries allow parts to be extracted later only if usage justifies it.

The presentation layer must support structurally faithful training screens without coupling the domain engine to one fixed visual layout. Screen definitions and workflow states should reproduce approved real-system navigation patterns where educationally relevant, while the surrounding training shell remains visibly distinct.

## High-level structure

```text
Web browser
    |
    v
Django application
    |-- Identity and permissions
    |-- Student onboarding
    |-- Learning content
    |-- Theory assessment
    |-- Scenario runtime
    |-- Practical evaluation
    |-- Progress and remediation
    |-- Instructor administration
    |-- Reports and certificates
    |-- Audit trail
    |
    +--> Django ORM --> SQLite (local V1)
    |                  PostgreSQL (hosted)
    |
    +--> Private document/file storage
```

## Application modules

### Identity and access

Django authentication, password security, sessions, account status, and role-based permissions. A custom user model is established before the first migration. Django Groups and model permissions provide the authorization foundation; business rules add object-level checks where a user must be assigned to a particular student, programme, or attempt. A user can belong to more than one role group so the initial administrator can also be an instructor.

### Learning content

Programmes, curriculum versions, modules, lessons, resources, examples, and questions. Ordering and prerequisite rules are stored as data.

### Theory assessment

Creates immutable attempts from published question/content versions, records responses, evaluates objective questions, and produces results.

### Scenario runtime

Loads a published scenario version, creates a transaction instance, exposes actions allowed by the current state, records every action, applies transition rules, and saves resumable state.

### Practical evaluation

Evaluates workflow accuracy, document review, decisions, errors, corrections, and assistance used. Scoring policies remain configurable.

### Progress and remediation

Calculates unlocks and completion from recorded results. Weakness codes connect failed criteria to lessons, resources, and alternative scenarios.

### Instructor administration

Provides basic content/scenario management, student progress, results, feedback, remediation assignments, and audited unlocks. Django Admin provides the initial developer/administrator content-entry interface. Purpose-built instructor screens are added for teaching workflows where Django Admin would be confusing or expose excessive access. A visual scenario builder is excluded from V1.

### Reports and certificates

Builds competency reports and generates uniquely identified completion certificates from immutable completion records.

### Audit trail

Records sensitive administrative changes, including role changes, unlocks, result overrides, publishing, and certificate actions.

## Scenario engine model

Scenarios are versioned definitions, separate from student attempts. A definition contains:

- briefing and learning objectives;
- practical area and difficulty/assistance mode;
- fictitious documents and transaction data;
- initial state and permitted actions;
- transition and validation rules;
- decision points and consequences;
- evaluation criteria and remediation mappings.

The engine should begin as a constrained state machine implemented with validated application data. V1 must not execute arbitrary instructor-provided Python, JavaScript, SQL, or template code.

Each scenario attempt stores a snapshot/version reference, current state, action log, assistance events, and evaluation. Resume reconstructs the state from the stored attempt and action history.

Parallel activity, such as shipping-line work, is represented through independent conditions/capabilities rather than one rigid screen sequence. For example, `request_shipping_invoice` becomes available when its prerequisites are true, even while another workflow branch remains in progress.

## Security and privacy baseline

- Passwords use Django's configurable password-hashing framework and are never encrypted or stored in plain text.
- Server-side authorization protects every restricted operation; hidden buttons are not security controls.
- State-changing requests use CSRF protection.
- Uploaded documents are private, type/size validated, renamed with generated identifiers, and served only after authorization.
- Training data is fictional by policy. The product should still minimize and protect student personal information.
- Structured audit records capture security- and assessment-sensitive actions.
- Local backups include both the database and private uploaded/generated files.

## Local deployment

Recommended initial packaging:

```text
Browser -> local Django application -> SQLite database
                              -> private data directory
```

Development may use Django's development server. A distributable local installation should use a production WSGI or ASGI server and bind to localhost by default. Network access should be enabled only through explicit configuration. Django Admin must not be exposed beyond trusted administrators.

## Hosted deployment path

```text
HTTPS reverse proxy
    -> production WSGI application
    -> PostgreSQL
    -> managed/private object or file storage
```

Configuration comes from environment variables or deployment secrets. Application logic, migrations, URL routes, and templates remain the same across database engines.

## SQLite-to-PostgreSQL compatibility contract

SQLite compatibility does not mean copying the `.db` file into PostgreSQL. It means keeping the schema and application behaviour portable, then performing an explicit data migration.

The implementation must:

- use Django model fields and Django migrations;
- use generated string/UUID identifiers where appropriate rather than depending on SQLite row identifiers;
- use timezone-aware UTC timestamps at the application boundary;
- store booleans through ORM boolean types;
- use portable Django fields such as `TextField`, `CharField`, `IntegerField`, `DecimalField`, `DateField`, `DateTimeField`, and JSON-compatible structures;
- avoid SQLite-only SQL, triggers, pragmas, collations, and conflict syntax in domain code;
- avoid PostgreSQL-only types until hosted migration is approved;
- enforce relationships and uniqueness in declared schema constraints;
- enable SQLite foreign-key enforcement on every connection;
- use `Decimal` for money and declared precision/scale, never binary floating point;
- define deterministic ordering explicitly rather than relying on insertion order;
- test migration scripts against both engines before hosting.

Before hosted launch, create PostgreSQL in a staging environment, apply all Django migrations from zero, import a sanitized copy of local data, compare record counts and key totals, and run the complete test suite. PostgreSQL becomes the production source of truth only after verification.

## Suggested project layout

```text
icums_simulator/
    config/             # settings, root URLs, WSGI/ASGI
    accounts/
    onboarding/
    learning/
    assessments/
    scenarios/
    progress/
    instructor_portal/
    reports/
    audit/
    templates/
    static/
    media/              # private local files; not public static files
    seed_data/
    tests/
    local_data/         # ignored database, generated files, and backups
    docs/
```

Each Django app owns its models, migrations, services, permissions, admin configuration, and tests. Cross-domain business workflows belong in explicit service functions rather than large views, model signals, or admin hooks.

## Django-specific decisions

- Create a custom `User` model before the first migration, even if it initially adds few fields.
- Use Django Admin for trusted content/configuration work, not as the student simulator or general instructor experience.
- Keep views thin; progression, evaluation, and scenario transitions run through tested domain services.
- Use database transactions for submission, evaluation, progression, and certificate issuance.
- Use Django forms for server-side validation; JavaScript enhancement must not replace server validation.
- Store uploaded/generated documents through Django's storage abstraction so local media can later move to hosted object storage.
- Avoid critical behaviour hidden in Django signals. Explicit workflows are easier to test and audit.
- Separate settings for development, automated tests, local production, and hosted production.
