# V1 Wireframe Decisions

## Visual direction

The proposed interface is calm, instructional, and clearly distinct from an official government system. It uses a restrained green accent, neutral surfaces, readable typography, and persistent training identification.

Within that distinct visual treatment, the simulator should follow the approved structure of the real ICUMS website where it helps learners transfer their skills: navigation hierarchy, terminology, grouping of fields, table and form organization, action placement, status presentation, and workflow sequence. It should not copy the real system's colours or create a deceptive replica.

The temporary product mark uses the initials `IS`. It is a placeholder, not a final logo.

## Shared application shell

Every authenticated page contains:

- a persistent `TRAINING SIMULATOR — NOT OFFICIAL ICUMS` banner;
- temporary ICUMS Simulator branding;
- role-appropriate primary navigation;
- page title, current learning context, and one clear primary action;
- responsive behaviour that keeps all essential actions available on smaller screens.

## Student dashboard

The dashboard prioritizes `Continue Training`, then shows the learning roadmap, prerequisite locks, areas needing attention, recent activity, and overall theory/practical progress. It avoids decorative metrics that do not help the student decide what to do next.

## Theory lesson

The lesson screen presents content and examples in the main reading area, with a compact lesson outline alongside it on wider screens. Short questions appear in the lesson flow. Progress is saved, and there is no examination timer.

## Guided practical workspace

The desktop layout has three functional regions:

1. Workflow and current stage
2. Main simulated transaction workspace
3. Document viewer and assistance appropriate to the current mode

On smaller screens, these regions stack rather than shrink. Beginner mode exposes guidance and hints. Intermediate and Advanced modes progressively reduce assistance, while Competency mode removes instructional hints.

The practical workspace should reproduce the relevant real-system structure once reference material has been reviewed. Until then, the current three-region layout is a conceptual placeholder and must not be described as an accurate representation of ICUMS.

Training-only elements—guidance, hints, learning objectives, feedback, and the simulator warning—sit in a clearly distinguishable training layer around or alongside the structurally familiar transaction workspace.

## Instructor workspace

The initial instructor dashboard emphasizes student progress and actionable needs. Student details will expose theory performance, practical evidence, errors, assistance used, feedback, and remediation. Developer-oriented curriculum entry remains in Django Admin; teaching workflows receive purpose-built screens.

## Accessibility and interaction baseline

- Keyboard-accessible native controls
- Visible focus states
- Minimum practical touch targets on narrow/coarse-pointer devices
- Colour is never the only status indicator
- Clear error messages that preserve entered work
- Responsive layout down to 320 pixels
- Plain language and consistent action labels
- No countdown components because V1 assessments are untimed

## Approval checkpoint

Before application scaffolding begins, confirm or revise:

- the calm green visual direction;
- persistent placement of the simulator warning;
- left navigation on desktop and horizontal navigation on narrow screens;
- dashboard information priority;
- three-region practical workspace;
- separation between Django Admin and instructor-facing screens.

## Reference-validation checkpoint

Before finalizing practical screens, obtain approved reference screenshots, screen recordings, field lists, or a subject-matter-expert walkthrough of the relevant real ICUMS workflow. For each simulated screen, record which structural details are verified, which are deliberately different, and which remain TBC. Reference material must be handled according to its confidentiality and permitted-use conditions.
