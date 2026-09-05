# Screen Map and Navigation

## Global experience

Every authenticated simulator page includes the training disclaimer in a persistent header or banner. Role-aware navigation shows only authorized areas, while the server independently enforces permissions.

```text
Public
|-- Welcome
|-- Sign in
|-- Register (if enabled)
`-- Password recovery (local/admin-assisted initially acceptable)

Student
|-- Dashboard / Continue Training
|-- Roadmap
|-- Theory
|-- Practical Training
|-- Assessments
|-- Results and Competency
|-- Resources
|-- Assignments
`-- Profile

Instructor
|-- Instructor Dashboard
|-- Students
|-- Learning Content
|-- Scenarios
|-- Assessments and Results
|-- Feedback and Remediation
`-- Resources

Administrator
|-- Users and Roles
|-- Programmes and Versions
|-- Configuration
|-- Content Publishing
|-- Certificate Settings
`-- Audit Log
```

## Student flow

### Onboarding

```text
Welcome / Sign in
    -> Registration or enrolment confirmation
    -> Student profile
    -> Simulator notice and acknowledgement
    -> Introduction
    -> Optional diagnostic (may be deferred)
    -> Learning roadmap
```

### Theory

```text
Roadmap
    -> Module overview
    -> Lesson viewer
       -> Content/example
       -> Short question
       -> Feedback
       -> Next lesson
    -> Module assessment instructions
    -> Assessment workspace
    -> Result and review
    -> Next module or remediation
    -> Final theory examination
```

The lesson viewer must save position. The assessment workspace shows progress through questions but no countdown timer.

### Simulator orientation

```text
Orientation overview
    -> Interface tour
    -> Demonstration transaction
    -> Guided interaction check
    -> Orientation complete
```

### Practical training

```text
Practical area overview
    -> Import modules
    -> Difficulty/mode overview
    -> Scenario briefing
    -> Document viewer + transaction workspace
    -> Contextual actions / decisions
    -> Save and exit or complete
    -> Feedback and result
    -> Recommended review / next scenario
```

The transaction workspace uses a consistent shell:

```text
+-----------------------------------------------------------+
| TRAINING SIMULATOR — NOT OFFICIAL ICUMS                   |
+---------------+---------------------------+---------------+
| Workflow and  | Main simulated workspace  | Documents /   |
| current status|                           | help (by mode) |
+---------------+---------------------------+---------------+
| Feedback, warnings, validation, and available actions     |
+-----------------------------------------------------------+
```

This is an information architecture, not a final visual design. Beginner mode may expose the workflow checklist and help panel; advanced and competency modes progressively reduce them.

### Completion

```text
Final competency result
    -> Competency report
    -> Completion record
    -> Certificate view/download
    -> Course record
    -> Practice sandbox (later release or minimal V1 entry)
```

## Instructor flow

```text
Instructor Dashboard
    -> Student list
    -> Student detail
       |-- Progress
       |-- Theory results
       |-- Practical attempts/action evidence
       |-- Assistance and errors
       |-- Feedback
       `-- Remediation

Learning Content
    -> Modules -> Lessons -> Questions -> Preview -> Publish

Scenarios
    -> Scenario list -> Basic structured editor -> Validate -> Preview -> Publish

Assessments
    -> Definitions -> Attempts -> Result detail -> Feedback
```

V1 content/scenario management may be intentionally basic and optimized for trained administrators rather than offering a visual drag-and-drop builder.

## Administrator flow

```text
Administration
    -> Users -> Account -> Roles/status
    -> Programmes -> Version -> Module order/prerequisites
    -> Publishing queue
    -> Certificate policy/template
    -> System configuration
    -> Audit event search/detail
```

## Essential states on every relevant screen

- Empty state with a useful next action
- Loading/processing state where relevant
- Validation errors that preserve entered data
- Unauthorized and not-found states without leaking private data
- Locked content with the unmet prerequisite explained
- Saved/resumable attempt state
- Published content/version indicator for instructors
- Read-only historical view for retired content and completed attempts
