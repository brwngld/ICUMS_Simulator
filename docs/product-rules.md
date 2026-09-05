# Product Rules and Decisions

## Purpose and safety boundary

Every simulator-facing page must clearly identify the product as a training environment. The application must use fictitious data and must not imply that a simulated declaration, payment, release, certificate, or status has legal or governmental effect.

The persistent short label is:

> TRAINING SIMULATOR — NOT OFFICIAL ICUMS

## Structural familiarity without impersonation

The simulator should reflect the real ICUMS system's relevant information architecture, terminology, navigation sequence, screen grouping, and workflow logic closely enough that learners can transfer their training to the real system.

It must remain visually distinct. The simulator will use its own colour palette, branding, typography, training banners, fictitious records, and training-specific guidance. It must not present itself as a live ICUMS session or reproduce official branding in a way that could mislead a learner.

Any claim that a screen or workflow matches the real system must be based on approved reference material or subject-matter-expert validation. Unverified layouts remain labelled as conceptual placeholders.

## Learning progression

Theory and practical difficulty are separate concepts:

1. Theory modules and lessons
2. Theory module assessments
3. Final theory examination
4. Simulator orientation
5. Beginner practical training
6. Intermediate practical training
7. Advanced practical training
8. Practical competency assessment
9. Competency report and certificate

Completed material remains available for review. Formal progression may remain locked until prerequisites are satisfied, while an instructor or administrator may override a lock with an audited reason.

## Assistance modes

| Mode | Guidance | Feedback | Expected behaviour |
|---|---|---|---|
| Beginner | Step-by-step directions, visible checklist, optional hints | Immediate and explanatory | Learn the workflow |
| Intermediate | Reduced directions and optional support | Usually after a decision or stage | Investigate and decide |
| Advanced | Minimal prompting and limited hints | Consequence-focused | Work independently |
| Competency | No instructional hints | Results after submission/review | Demonstrate competence |

The same scenario engine supports every mode. Assistance policy changes; separate simulators are not created.

## Assessment rules

- No assessment is timed in V1.
- Elapsed time may be recorded but must not affect the score or pass/fail result.
- Diagnostic results do not contribute to official scores.
- New attempts never overwrite previous attempts.
- Practice attempts and official assessment attempts are distinguished.
- Exact scores, pass thresholds, attempt limits, and competency weights remain configurable and TBC.
- An automatic evaluation stores its individual rule results, not only a total score.
- Future instructor overrides must preserve the original evaluation, the revised result, the reason, the instructor, and the timestamp.

## Certificate rules

In V1, successful completion automatically issues a certificate. Certificate issuance must use a policy setting so that a later release can require instructor approval without changing the completion model.

Certificates must say that they record completion of simulator training and are not government-issued professional qualifications.

## Content rules

- Curriculum, questions, workflows, scenarios, rubrics, and resources are data, not hard-coded application logic.
- Content records have draft/published/retired states.
- Attempts retain the content version used when the attempt started.
- Initial content can be loaded by seed files or developer/admin tools.
- Unknown customs rules remain explicitly TBC; sample content must be labelled fictional.

## Explicit V1 exclusions

- Real ICUMS integration or impersonation
- Real customs declarations, payments, shipments, releases, or government transactions
- Export, Transit, and Warehouse practical implementations
- Sophisticated visual scenario builder
- AI assistance or AI scenario generation
- Multi-institution tenancy
- Public certificate-verification portal
- Rich messaging, discussions, or cohort collaboration
- Offline synchronization between multiple computers
- Timed or remotely proctored examinations
