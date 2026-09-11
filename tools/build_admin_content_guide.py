from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "ICUMS_Admin_Content_Creation_Guide.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

PURPLE = colors.HexColor("#5145CD")
INK = colors.HexColor("#1C2540")
MUTED = colors.HexColor("#65718A")
LINE = colors.HexColor("#DDE3EE")
SOFT = colors.HexColor("#F5F6FB")
LAVENDER = colors.HexColor("#EEEBFC")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverKicker", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=colors.HexColor("#DAD6FF"), alignment=TA_CENTER, spaceAfter=12))
styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=28, leading=33, textColor=colors.white, alignment=TA_CENTER, spaceAfter=14))
styles.add(ParagraphStyle(name="CoverSub", parent=styles["Normal"], fontName="Helvetica", fontSize=11, leading=17, textColor=colors.HexColor("#E8E7FF"), alignment=TA_CENTER))
styles.add(ParagraphStyle(name="H1x", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=24, textColor=INK, spaceBefore=2, spaceAfter=10, keepWithNext=True))
styles.add(ParagraphStyle(name="H2x", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=PURPLE, spaceBefore=12, spaceAfter=6, keepWithNext=True))
styles.add(ParagraphStyle(name="Bodyx", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2, leading=14, textColor=INK, spaceAfter=6))
styles.add(ParagraphStyle(name="Smallx", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED, spaceAfter=4))
styles.add(ParagraphStyle(name="Bulletx", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.1, leading=13.5, leftIndent=13, firstLineIndent=-8, textColor=INK, spaceAfter=3))
styles.add(ParagraphStyle(name="CalloutTitle", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=9.2, leading=13, textColor=INK, spaceAfter=3))
styles.add(ParagraphStyle(name="TableHead", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white))
styles.add(ParagraphStyle(name="TableCell", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.8, leading=10.5, textColor=INK))


def p(text, style="Bodyx"):
    return Paragraph(text, styles[style])


def bullets(items):
    table = Table([[p(f"- {item}", "Bulletx")] for item in items], colWidths=[166 * mm])
    table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def callout(title, body, tone="info"):
    if tone == "warning":
        bg, edge = colors.HexColor("#FFF8E8"), colors.HexColor("#D8A914")
    elif tone == "success":
        bg, edge = colors.HexColor("#EDF9F4"), colors.HexColor("#239878")
    else:
        bg, edge = LAVENDER, PURPLE
    table = Table([[p(title, "CalloutTitle")], [p(body, "Bodyx")]], colWidths=[166 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), .7, edge),
        ("LINEBEFORE", (0, 0), (0, -1), 3, edge),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return KeepTogether([table, Spacer(1, 7)])


def data_table(rows, widths, header=True):
    converted = []
    for row_index, row in enumerate(rows):
        converted.append([p(str(value), "TableHead" if header and row_index == 0 else "TableCell") for value in row])
    table = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("GRID", (0, 0), (-1, -1), .35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        commands.extend([("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)])
        for index in range(1, len(rows)):
            if index % 2 == 0:
                commands.append(("BACKGROUND", (0, index), (-1, index), SOFT))
    table.setStyle(TableStyle(commands))
    return table


class GuideDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(22 * mm, 20 * mm, 166 * mm, 250 * mm, id="normal", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="guide", frames=[frame], onPage=self.draw_page)])

    def draw_page(self, canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setStrokeColor(LINE)
            canvas.setLineWidth(.5)
            canvas.line(22 * mm, 284 * mm, 188 * mm, 284 * mm)
            canvas.setFont("Helvetica-Bold", 7.5)
            canvas.setFillColor(PURPLE)
            canvas.drawString(22 * mm, 288 * mm, "ICUMS SIMULATOR")
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(188 * mm, 288 * mm, "Admin content creation guide")
            canvas.setStrokeColor(LINE)
            canvas.line(22 * mm, 15 * mm, 188 * mm, 15 * mm)
            canvas.setFont("Helvetica", 7.5)
            canvas.drawString(22 * mm, 10 * mm, "Training simulator - fictional data only")
            canvas.drawRightString(188 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()


story = []

cover = Table([
    [Spacer(1, 24 * mm)],
    [p("ADMINISTRATOR PLAYBOOK", "CoverKicker")],
    [p("Creating theory content<br/>from the Admin page", "CoverTitle")],
    [p("A practical, click-by-click guide to programmes, modules, lessons, lesson questions, assessments, enrolments, and instructor review.", "CoverSub")],
    [Spacer(1, 28 * mm)],
    [p("ICUMS Simulator | Version 1 content workflow | 9 September 2026", "CoverSub")],
], colWidths=[166 * mm], rowHeights=[24 * mm, 12 * mm, 30 * mm, 26 * mm, 28 * mm, 12 * mm])
cover.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), INK),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 17),
    ("RIGHTPADDING", (0, 0), (-1, -1), 17),
]))
story.extend([cover, PageBreak()])

story.extend([
    p("How to use this guide", "H1x"),
    p("The Admin page is a content-entry tool, not a drag-and-drop course builder. Some records appear as their own Admin menu items. Other records are intentionally created inside a parent record as inline rows. The quickest way to avoid confusion is to follow the dependency order in this guide.", "Bodyx"),
    callout("The one-sentence mental model", "A published programme version contains published modules. Each module contains published lessons. Each lesson contains ordered content blocks and optional lesson checks. Assessments reuse published question versions through assessment items.", "info"),
    p("What you will build", "H2x"),
    data_table([
        ["Admin record", "What it controls", "Where it is created"],
        ["Programme", "The course family, for example Customs Clearance Foundations.", "Onboarding > Programmes"],
        ["Programme version", "The frozen curriculum release that students enrol in.", "Onboarding > Programme versions"],
        ["Module", "A theory unit inside one programme version.", "Learning > Modules"],
        ["Lesson", "A learner-facing lesson inside one module.", "Learning > Lessons"],
        ["Content block", "Ordered text, example, or notice inside a lesson.", "Inline on a Lesson"],
        ["Question version", "A publishable version of a question and its answer choices.", "Assessments > Question versions"],
        ["Lesson check", "A short question shown after a lesson block.", "Inline on a Lesson"],
        ["Assessment", "A module assessment or final theory examination.", "Assessments > Assessments"],
        ["Assessment item", "A question version included in an assessment.", "Inline on an Assessment"],
        ["Enrolment", "Connects a student to a published programme version.", "Onboarding > Enrolments or inline on a User"],
    ], [38 * mm, 73 * mm, 55 * mm]),
    Spacer(1, 8),
    callout("Important", "Content is fictional training material. Do not enter live customs data, personal data, payment information, or production declarations.", "warning"),
    PageBreak(),
])

story.extend([
    p("10. Test the learner journey", "H1x"),
    p("Use a separate student account. Do not test with the administrator account because the learner dashboard is driven by enrolment and student permissions.", "Bodyx"),
    data_table([
        ["Test", "Expected result"],
        ["Sign in", "The disclaimer appears when the account has not accepted the current disclaimer."],
        ["Dashboard", "The active programme and published modules appear."],
        ["Roadmap", "Modules are ordered correctly. Prerequisites lock later modules when configured."],
        ["Lesson", "Blocks appear in order and the lesson check appears after its selected block."],
        ["Completion", "Finishing the last lesson redirects to the module assessment when one exists."],
        ["Assessment", "Only the assessment items appear. The learner receives an automatic score and outcome."],
        ["Final theory", "It remains locked until the published module lessons and module assessments are complete."],
    ], [40 * mm, 126 * mm]),
    p("11. Review progress as an instructor", "H1x"),
    p("Instructor pages are for teaching review; Django Admin is for content and account management. After a learner has attempted content, use the Instructor link in the main navigation to review assigned students, progress, attempts, feedback, and competency results. Read-only attempt records in Admin are useful for audit and troubleshooting, but they are not meant to be manually created.", "Bodyx"),
    p("Records that are read-only", "H2x"),
    bullets([
        "Theory attempts are created when a learner starts an assessment.",
        "Theory responses are created when a learner submits answers.",
        "Lesson check responses are created when a learner checks an answer.",
        "Do not try to add these records manually from Admin; the Add buttons are intentionally disabled.",
    ]),
    p("12. Troubleshooting", "H1x"),
    data_table([
        ["Symptom", "Likely cause", "Fix"],
        ["Lesson does not appear", "Lesson, module, or programme version is unpublished.", "Check all three Is published/Status fields."],
        ["Question is not in a dropdown", "Question version was not saved, or you selected Question instead of Question version.", "Save the version and reopen the parent form."],
        ["Lesson check gives an error", "After block belongs to another lesson.", "Select a content block from the same Lesson."],
        ["Assessment cannot save", "Module belongs to another programme version, or final theory has a module.", "Match the programme and module; clear Module for final theory."],
        ["Published record cannot be edited", "This is the intentional version-safety rule.", "Create a new draft version or revise while the parent programme version is Draft."],
        ["Student sees an empty roadmap", "No active enrolment or the enrolled version is not published.", "Create an Active enrolment for the published version."],
    ], [42 * mm, 58 * mm, 66 * mm]),
    PageBreak(),
])

story.extend([
    p("Worked example: one complete theory lesson", "H1x"),
    p("Use this miniature example to verify that the relationships are set up correctly before entering a larger curriculum.", "Bodyx"),
    p("Parent records", "H2x"),
    data_table([
        ["Record", "Example value"],
        ["Programme", "Customs Clearance Foundations"],
        ["Programme version", "Version 1, Draft while building"],
        ["Module", "Document Review Foundations / document-foundations / order 1"],
        ["Lesson", "Checking document consistency / document-consistency / order 1"],
    ], [48 * mm, 118 * mm]),
    p("Teaching content", "H2x"),
    data_table([
        ["Block", "Kind", "Body"],
        ["1", "Notice", "All names, references, quantities, and events are fictional."],
        ["2", "Text", "Compare parties, references, quantities, descriptions, weights, and dates."],
        ["3", "Example", "The invoice shows 120 cartons while the packing list shows 102."],
    ], [18 * mm, 26 * mm, 122 * mm]),
    p("Question and assessment links", "H2x"),
    bullets([
        "Question code: <b>demo-document-mismatch</b>.",
        "Question version 1: single choice, one point, three options, one correct option.",
        "Lesson check: placed after block 2 and points to Question version 1.",
        "Module assessment: points to the same Question version through one Assessment item.",
        "Final theory examination: can also include the Question version, but should normally contain a broader set of questions in a real course.",
    ]),
    callout("Fast demonstration shortcut", "For local development only, the project includes <b>python manage.py seed_demo_content</b>. It creates clearly labelled fictional programme, lesson, question, lesson check, module assessment, final assessment, and disclaimer data. Use the Admin workflow in this guide when creating your own curriculum.", "info"),
    p("Final release checklist", "H2x"),
    bullets([
        "Every module and lesson has a clear title, order, and learner-facing description or summary.",
        "Every lesson has at least one content block and any lesson check points to the correct block.",
        "Every question version has answer options, exactly one correct option for single choice, and a useful explanation.",
        "Every assessment has the correct programme/module relationship and at least one assessment item.",
        "Published flags are set only after review, and the Programme version is published last.",
        "A test student can enrol, open the roadmap, complete a lesson, answer a check, and submit an assessment.",
    ]),
    PageBreak(),
])


story.extend([
    p("6. Add a lesson knowledge check", "H1x"),
    p("A lesson check is a short question embedded after a specific content block. It is not the same as the formal module assessment.", "Bodyx"),
    bullets([
        "Return to Learning > Lessons and open the Lesson change page.",
        "Scroll to the Lesson checks inline section.",
        "Choose Add another Lesson check.",
        "Select After block. This must be a Content block belonging to the same lesson.",
        "Select the Question version you created.",
        "Set Order if the lesson has more than one check.",
        "Save the Lesson.",
    ]),
    callout("If the Question version is missing from the dropdown", "Save the Question version first. Also check that you are selecting the version record, not the stable Question record. Publish it later with the other dependencies.", "info"),
    p("7. Create an assessment", "H1x"),
    p("Assessments reuse Question versions through Assessment items. They do not copy the prompt or answer options, so the question versions must exist first.", "Bodyx"),
    p("Module assessment", "H2x"),
    bullets([
        "Go to Assessments > Assessments and choose Add assessment.",
        "Select the Programme version.",
        "Select the Module for a module assessment.",
        "Enter a Title, for example <b>Document Review Foundations Assessment</b>.",
        "Choose Assessment type: <b>Module assessment</b>.",
        "Set Pass percentage, for example <b>70</b>.",
        "Set Maximum attempts to a number, or leave it blank for unlimited attempts.",
        "Choose Randomize questions only when question order should vary for each attempt.",
        "Leave Is published unchecked while building.",
    ]),
    p("Final theory examination", "H2x"),
    bullets([
        "Create another Assessment with the same Programme version.",
        "Choose Assessment type: <b>Final theory examination</b>.",
        "Leave Module empty. Final theory applies to the whole programme.",
        "Set the pass percentage and attempt policy, then add the question items.",
    ]),
    p("Add assessment items inline", "H2x"),
    bullets([
        "On the Assessment change page, scroll to Assessment items.",
        "Choose Add another Assessment item.",
        "Select a published-ready Question version.",
        "Set Order. Use a unique question version once per assessment.",
        "Save the Assessment.",
    ]),
    callout("Validation rule", "A final theory examination cannot have a Module selected. A module assessment must point to a module from the same Programme version.", "warning"),
    PageBreak(),
])

story.extend([
    p("8. Publish safely", "H1x"),
    p("Publishing is a release operation. Use this checklist before students are enrolled.", "Bodyx"),
    data_table([
        ["Order", "Record", "Check"],
        ["1", "Resources", "Titles, descriptions, and links are correct."],
        ["2", "Question versions", "Prompt, explanation, points, options, and exactly one correct answer are ready."],
        ["3", "Lessons", "All content blocks and lesson checks are present; Is published is checked."],
        ["4", "Modules", "Order, prerequisite, and Is published are correct."],
        ["5", "Assessments", "Programme, module/type, pass percentage, attempts, items, and Is published are correct."],
        ["6", "Programme version", "Set Status to Published and set Published at. Save last."],
    ], [20 * mm, 42 * mm, 104 * mm]),
    callout("Why publish the Programme version last", "Learner queries filter by the active enrolled Programme version and published flags. Publishing the parent last prevents a half-built course from appearing in the student roadmap.", "success"),
    p("What becomes locked", "H2x"),
    bullets([
        "A Module or Lesson cannot be changed after its Programme version is published.",
        "A published Question version cannot be changed. Create a new version instead.",
        "A published Assessment cannot be changed.",
        "Attempts store snapshots of the question set, so changing content after a learner starts an attempt would be unsafe.",
    ]),
    p("9. Create a student and enrol them", "H1x"),
    bullets([
        "Go to Accounts > Users and choose Add user. Set the login credentials and save.",
        "Go to Onboarding > Enrolments and choose Add enrolment, or use the Enrolments inline section on the User page.",
        "Select the student and the published Programme version.",
        "Leave Status as Active.",
        "Save. The system records the enrolling administrator and assigns the Student group automatically.",
    ]),
    callout("If the programme does not appear", "Confirm that the Programme version status is Published and that the enrolment uses that exact version. A Draft version is intentionally not a learner-ready option.", "warning"),
    PageBreak(),
])

story.extend([
    p("2. Create modules", "H1x"),
    p("A module is a major theory unit. It appears on the learner roadmap and can own a module assessment.", "Bodyx"),
    bullets([
        "Go to Learning > Modules and choose Add module.",
        "Select the Draft Programme version.",
        "Enter a Code such as <b>document-foundations</b>. The code is used in learner URLs, so do not change it casually after publishing.",
        "Enter the learner-facing Title and a short Description.",
        "Set Order to <b>1</b>, <b>2</b>, <b>3</b>, and so on. Lower numbers appear first.",
        "Leave Is published unchecked while building.",
        "Use Prerequisite only when this module must wait for another module. Leave it empty for the first module.",
        "Save.",
    ]),
    p("3. Create lessons and their content", "H1x"),
    p("Lessons are created as their own records. Their teaching material is entered on the same change page through the Content blocks inline section.", "Bodyx"),
    p("Create the lesson", "H2x"),
    bullets([
        "Go to Learning > Lessons and choose Add lesson.",
        "Select the Module you created.",
        "Enter a Title, for example <b>Checking document consistency</b>.",
        "Enter a Slug, for example <b>document-consistency</b>. If the Admin auto-fills it, review it for lowercase words separated by hyphens.",
        "Enter a Summary that explains what the learner will practise.",
        "Set Order inside the module and leave Is published unchecked.",
    ]),
    p("Add content blocks in the same form", "H2x"),
    bullets([
        "Scroll below the lesson fields to Content blocks.",
        "Choose Add another Content block for each section of teaching content.",
        "Choose Kind: Text for explanation, Example for a worked example, or Notice for a warning or fictional-data notice.",
        "Enter an optional Heading and the Body. Use plain paragraphs; keep each block focused on one idea.",
        "Set Order to control the learner sequence. Use 1, 2, 3 rather than relying on save order.",
        "Save the Lesson. The blocks are saved with it.",
    ]),
    callout("Common confusion", "Content blocks are not a separate Admin menu item in this project. They are inline rows on the Lesson change page. If you leave the inline row blank, remove it before saving.", "warning"),
    PageBreak(),
])

story.extend([
    p("4. Add resources", "H1x"),
    p("Resources can be linked to lessons and later used as remediation guidance for a question or practical criterion.", "Bodyx"),
    bullets([
        "Go to Learning > Resources and choose Add resource.",
        "Enter a Title and optional Description.",
        "Enter a URL only when the link is safe and available to your learners. Leave it empty for an internal reference note.",
        "Use the Lessons multi-select to link the resource to one or more lessons.",
        "Save. You can later select this resource from a Question version as Remediation resource.",
    ]),
    p("5. Build questions and answer options", "H1x"),
    p("Questions are deliberately versioned. The Question record is the stable identity. The Question version contains the actual wording, scoring, explanation, and answer options that learners see.", "Bodyx"),
    p("Create the stable question", "H2x"),
    bullets([
        "Go to Assessments > Questions and choose Add question.",
        "Enter a unique Code such as <b>document-mismatch-first-action</b>.",
        "Save. Do not put the full prompt in the Code.",
    ]),
    p("Create the question version", "H2x"),
    bullets([
        "Go to Assessments > Question versions and choose Add question version.",
        "Select the Question record.",
        "Set Version to <b>1</b> for the first wording. Use version 2 when you need a new wording after publication; do not rewrite a published version.",
        "Choose Question type: Single choice or True or false.",
        "Enter the Prompt exactly as the learner should read it.",
        "Enter Explanation. This is shown after a lesson check and helps explain why an answer is correct or incorrect.",
        "Set Points, normally 1 for a short objective question.",
        "Optionally choose a Remediation resource.",
        "Leave Is published unchecked until the question is complete.",
    ]),
    p("Add answer options inline", "H2x"),
    bullets([
        "On the same Question version page, scroll to Answer options.",
        "Choose Add another Answer option for each answer.",
        "Enter the Label exactly as the learner should see it.",
        "Set Order to 1, 2, 3, and so on.",
        "Check Is correct for the accepted answer. For Single choice, normally check exactly one option. For True or false, create two options and mark one correct.",
        "Save the Question version.",
    ]),
    callout("Do not publish an incomplete question", "The learner experience depends on answer options being present. A published Question version with no correct option cannot produce a meaningful result.", "warning"),
    PageBreak(),
])

story.extend([
    p("Before you start", "H1x"),
    p("Open the Admin page at <b>http://127.0.0.1:8000/admin/</b> and sign in with a staff or superuser account. The redesigned Admin dashboard groups the records into cards. If a card is not visible, the account does not have permission for that model.", "Bodyx"),
    p("The lifecycle rule that controls everything", "H2x"),
    bullets([
        "Build and edit the curriculum while the Programme version status is Draft.",
        "Keep modules, lessons, question versions, and assessments unpublished while you are still checking them.",
        "Publish each dependent record only after its parent and references are ready.",
        "Publish the Programme version last. Students only see published content belonging to their active programme version.",
        "Published lessons and modules cannot be changed while their Programme version is published. Published question versions and assessments are also protected from editing.",
    ]),
    callout("Recommended build order", "Programme -> Programme version (Draft) -> Modules -> Lessons and blocks -> Resources -> Questions and options -> Lesson checks -> Assessments and items -> Publish flags -> Programme version (Published) -> Student enrolment -> Test learner journey.", "success"),
    p("1. Create the programme and programme version", "H1x"),
    p("Start with the parent records so every later dropdown has a valid destination.", "Bodyx"),
    p("Create the programme", "H2x"),
    bullets([
        "Go to Onboarding > Programmes and choose Add programme.",
        "Enter Name, for example <b>Customs Clearance Foundations</b>.",
        "Enter Code, for example <b>customs-foundations</b>. Keep it short, lowercase, and unique.",
        "Leave Is active checked, then save.",
    ]),
    p("Create the programme version", "H2x"),
    bullets([
        "Go to Onboarding > Programme versions and choose Add programme version.",
        "Select the Programme you just created.",
        "Enter Version, normally <b>1</b> for the first release.",
        "Leave Status as <b>Draft</b>. Leave Published at empty until the final release step.",
        "Save and return to the list.",
    ]),
    callout("Why the version matters", "A student enrols in a Programme version, not just a Programme. This lets you create version 2 later without changing what version 1 students already studied.", "info"),
    PageBreak(),
])


def group_title(group):
    for flowable in group:
        if isinstance(flowable, Paragraph):
            return flowable.getPlainText()
    return ""


groups = []
current = []
for flowable in story:
    current.append(flowable)
    if isinstance(flowable, PageBreak):
        groups.append(current)
        current = []
if current:
    groups.append(current)

desired = [
    "How to use this guide",
    "Before you start",
    "2. Create modules",
    "4. Add resources",
    "6. Add a lesson knowledge check",
    "8. Publish safely",
    "10. Test the learner journey",
    "Worked example: one complete theory lesson",
]

cover_group = groups[0]
content_groups = {group_title(group): group for group in groups[1:]}
story = cover_group + [
    flowable
    for title in desired
    for flowable in content_groups[title]
    if not isinstance(flowable, PageBreak)
]

doc = GuideDocTemplate(
    str(OUTPUT),
    pagesize=A4,
    leftMargin=22 * mm,
    rightMargin=22 * mm,
    topMargin=20 * mm,
    bottomMargin=20 * mm,
    title="ICUMS Admin Content Creation Guide",
    author="ICUMS Simulator",
)
doc.build(story)
print(OUTPUT)
