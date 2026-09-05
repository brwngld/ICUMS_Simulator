# ICUMS Simulator

> **TRAINING SIMULATOR — NOT OFFICIAL ICUMS**

ICUMS Simulator is a local-first educational web application for learning customs-clearance theory and practising simulated customs workflows. It does not connect to the official ICUMS platform, submit declarations, process payments, or use real transactions.

The current repository contains the planning baseline for approval before implementation begins.

## Agreed V1 direction

- Local deployment for approximately 10 students, designed for later web hosting.
- Student, instructor, and administrator roles; one person may hold both instructor and administrator roles.
- Theory precedes practical training.
- Practical progression uses Beginner, Intermediate, Advanced, and independent Competency modes.
- Import is the first practical workflow, while the underlying engine remains reusable for Export, Transit, Warehouse, and future processes.
- Exams are not timed. Time is recorded for insight but does not affect pass/fail.
- Certificates are issued automatically after passing in V1. Instructor approval will later be configurable.
- Initial learning and scenario content may be loaded by a developer or administrator.
- Temporary branding: **ICUMS Simulator**.

## Planning package

- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Screen map](docs/screen-map.md)
- [Wireframe decisions](docs/wireframes.md)
- [Implementation plan](docs/implementation-plan.md)
- [Local development](docs/local-development.md)
- [How to review the application](docs/how-to-review.md)
- [Product rules and decisions](docs/product-rules.md)

## Proposed implementation stack

- Python and Django
- Django templates, HTML, CSS, and focused JavaScript
- Django ORM and Django migrations
- SQLite for local V1 operation
- PostgreSQL for hosted deployment
- Pytest and pytest-django for automated testing

Implementation should begin only after this planning baseline has been reviewed.

## Current implementation status

Phase 1 foundation work, the Phase 2 theory journey, the Phase 3 practical engine, and the configurable Phase 4 evaluation layer are operational with fictional content. The repository now includes versioned declarative scenarios and rubrics, structured fictitious documents, conditional and parallel actions, mode-based assistance, append-only action evidence, save/resume, criterion-level results, remediation, instructor feedback, audited outcome revisions, and a guided fictional Import workflow through simulated gate out. Practical layouts and competency rules remain conceptual until validated.

See [implementation status](docs/implementation-status.md) for verified capabilities and remaining work.
