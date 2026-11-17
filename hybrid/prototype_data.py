"""Mock curriculum data for the Milestone 1 authoring prototype.

CUSTOMS CLEARANCE TRAINING — MOCK PROGRAMME. This is invented sample content
for a UI review only. It is not a database fixture, not seeded anywhere, and
never touches production Programme/Course/Module/Lesson records. Delete this
file with the prototype; nothing imports it except prototype_views.
"""

PROTOTYPE_NOTE = (
    "UI prototype — Milestone 1–2 (programme, course & lesson authoring). All content on "
    "this page is mock data: creating, editing, moving or publishing anything here "
    "changes nothing in the database."
)

MOCK_PROGRAMME = {
    "prototype_note": PROTOTYPE_NOTE,
    "total_count": 2,
    "landing_rows": [
        {
            "name": "Customs Clearance Practitioner — Sea Import",
            "code": "CCP-SEA-IMP",
            "editions": [
                {"version": 3, "status": "draft", "courses": 2, "modules": 3, "lessons": 7},
                {"version": 2, "status": "published", "courses": 2, "modules": 3, "lessons": 6},
            ],
            "can_delete": True,
            "detail_url": "hybrid-prototype-milestone1-programme",
            "manage_label": "Manage",
        },
        {
            "name": "Declarant Refresher — BOE & Duty Assessment",
            "code": "REF-BOE",
            "editions": [
                {"version": 1, "status": "published", "courses": 1, "modules": 2, "lessons": 4},
            ],
            "can_delete": False,
            "detail_url": "",
            "manage_label": "Published — read-only",
        },
    ],
    "detail": {
        "name": "Customs Clearance Practitioner — Sea Import",
        "code": "CCP-SEA-IMP",
    },
    "course": {
        "title": "Pre-arrival & Cargo Handling",
        "code": "CCP1",
        "description": "Documents and cargo actions that precede a bill of entry.",
        "lesson_count": 5,
        "blockers": [
            "Module “Cargo service request & physical delivery” has a lesson with no theory written.",
        ],
        "modules": [
            {
                "title": "Arrival notice, bill of lading & delivery order",
                "code": "CCP1-M1",
                "lesson_count": 3,
                "detail_url": "hybrid-prototype-milestone1-module",
            },
            {
                "title": "Cargo service request & physical delivery",
                "code": "CCP1-M2",
                "lesson_count": 2,
                "detail_url": "",
            },
        ],
        "journeys": [
            {
                "title": "Sea import clearance end-to-end",
                "start_mode": "New record",
                "issue_count": 2,
            },
        ],
    },
}

MOCK_EDITIONS = [
    {
        "version_number": 3,
        "status": "draft",
        "courses": 2,
        "modules": 3,
        "lessons": 7,
        "published_at": None,
        "mock_courses": [
            {
                "title": "Pre-arrival & Cargo Handling",
                "code": "CCP1",
                "modules": 2,
                "lessons": 5,
                "not_ready": False,
            },
            {
                "title": "Declarations, Assessment & Release",
                "code": "CCP2",
                "modules": 1,
                "lessons": 2,
                "not_ready": True,
            },
        ],
        "blockers": [
            "Course “Declarations, Assessment & Release” has a journey with unbound verification conditions.",
        ],
    },
    {
        "version_number": 2,
        "status": "published",
        "courses": 2,
        "modules": 3,
        "lessons": 6,
        "published_at_display": "14 Oct 2026",
        "blockers": [],
    },
]

MOCK_MODULE = {
    "title": "Arrival notice, bill of lading & delivery order",
    "code": "CCP1-M1",
    "interactive_count": 2,
    "theory_count": 2,
    "not_ready_count": 1,
    "lesson_rows": [
        {
            "title": "Reading the bill of lading",
            "slug": "bl-basics",
            "is_interactive": False,
            "step_count": 0,
            "has_theory": True,
            "issues": [],
        },
        {
            "title": "Registering a consignment application",
            "slug": "consignment-app",
            "is_interactive": True,
            "step_count": 6,
            "has_theory": True,
            "issues": [],
        },
        {
            "title": "Requesting a delivery order",
            "slug": "delivery-order",
            "is_interactive": True,
            "step_count": 4,
            "has_theory": False,
            "issues": ["Theory not written"],
        },
    ],
}

MOCK_STATS = {
    "landing": {
        "programmes": 2,
        "courses": 3,
        "modules": 5,
        "lessons": 11,
    },
}

# ---------------------------------------------------------------------------
# Milestone 2 — mock lesson authoring content.
#
# The two seeded lessons below back the prototype lesson editor and instructor
# preview. Learning objectives, supporting materials and knowledge checks are
# PROPOSED only: the real HybridLesson model has none of them, and Guided
# Material Study creation is refused server-side today. The editor renders
# them as clearly-flagged provisional sections.
# ---------------------------------------------------------------------------

SIMULATOR_SCREENS = [
    "Unique Consignment Reference",
    "Consignment application",
    "Preparation application",
    "Cargo service request",
    "Direct delivery",
    "Bill of entry draft",
    "Duty assessment",
]

MOCK_LESSONS = {
    "bl-basics": {
        "slug": "bl-basics",
        "kind": "guided",
        "title": "Reading the bill of lading",
        "summary": "What a bill of lading is, who issues it, and which fields matter before a cargo service request is raised.",
        "objectives": [
            "Identify the parties named on an original bill of lading.",
            "Locate the consignee, notify party and freight terms on the face of the document.",
            "Explain why the bill of lading number is carried into the consignment application.",
        ],
        "theory_html": (
            "<h3>What the bill of lading does</h3>"
            "<p>The bill of lading is the carrier's receipt for the cargo, evidence of the contract of"
            " carriage, and — when issued to order — a document of title. In sea import you will meet it"
            " long before any declaration: the vessel's agent works from it to release cargo.</p>"
            "<h3>The fields that matter to you</h3>"
            "<p>Read the face of the document in this order: shipper, consignee, notify party, vessel and"
            " voyage, port of loading, port of discharge, description of packages, freight terms, and the"
            " bill of lading number itself. The number is what ICUMS-style systems key on — a consignment"
            " application raised against the wrong bill will not match the manifest.</p>"
            "<ul><li>Consignee “to order” means the bank or endorsee controls delivery.</li>"
            "<li>“Freight payable as per charter” points you at a charter party, not a liner tariff.</li>"
            "<li>Package counts and container numbers must match the cargo service request exactly.</li></ul>"
        ),
        "materials": [
            {"name": "Sample bill of lading — Maersk LINE (PDF)", "size_display": "412 KB"},
            {"name": "Face-of-B/L field map (PNG)", "size_display": "96 KB"},
            {"name": "Endorsement chain worked example (PDF)", "size_display": "220 KB"},
        ],
        "checks": [
            {
                "prompt": "A bill of lading consigned “to order and blank endorsed” is delivered to the importer by…",
                "options": ["The carrier's agent at the port", "The lawful holder of the original document", "The customs declarant", "The notify party named on the face"],
                "answer_index": 1,
            },
            {
                "prompt": "Which field links the bill of lading to the consignment application in the simulator?",
                "options": ["The vessel name", "The freight terms", "The bill of lading number", "The port of loading"],
                "answer_index": 2,
            },
        ],
        "procedure": "",
        "steps": [],
    },
    "consignment-app": {
        "slug": "consignment-app",
        "kind": "interactive",
        "title": "Registering a consignment application",
        "summary": "Raise a consignment application against an arrived sea-import bill of lading, from the unique consignment reference to a saved, assessable record.",
        "objectives": [
            "Open the consignment application screen from the single-window workspace.",
            "Enter the bill of lading key data so the manifest match succeeds.",
            "Save the application and confirm its status in the record register.",
        ],
        "theory_html": (
            "<h3>Where this sits in sea import</h3>"
            "<p>Before a delivery order or a bill of entry, the consignment application tells the system"
            " who is claiming the cargo and under which bill of lading. It is the first record a clearing"
            " agent creates after the arrival notice, and every later document is hung off its unique"
            " consignment reference (UCR).</p>"
            "<h3>What the check will look for</h3>"
            "<p>A saved application carrying the correct bill of lading number, consignee code and"
            " package count. Get the manifest match wrong and the later bill of entry will not find the"
            " consignment — so verify each field against the sample documents before you save.</p>"
        ),
        "materials": [],
        "checks": [],
        "procedure": "Consignment application",
        "steps": [
            {"title": "Open the single window", "instruction": "From the workspace, open Unique Consignment Reference and choose New consignment.", "outcome": "The consignment registration screen is open with a fresh draft.", "verifications": [{"kind": "screen_opened", "detail": "Unique Consignment Reference"}]},
            {"title": "Key the bill of lading", "instruction": "Enter the bill of lading number and issue date from the sample document.", "outcome": "The manifest lookup returns the arrived line.", "verifications": []},
            {"title": "Identify the consignee", "instruction": "Search and select the consignee TIN, then confirm the trading-partner panel populates.", "outcome": "Consignee name and address appear on the application.", "verifications": [{"kind": "saved_record", "detail": "Consignment application — consignee populated"}]},
            {"title": "Enter cargo particulars", "instruction": "Copy package count, gross weight and container number from the bill of lading.", "outcome": "Particulars match the manifest line exactly.", "verifications": []},
            {"title": "Review the declaration data", "instruction": "Expand the review panel and check each flagged field before saving.", "outcome": "No unresolved validation warnings remain.", "verifications": [{"kind": "screen_opened", "detail": "Consignment application"}]},
            {"title": "Save the application", "instruction": "Save the consignment application and note the returned UCR.", "outcome": "The application is saved and listed in the record register.", "verifications": [{"kind": "saved_record", "detail": "Consignment application — status Draft"}]},
        ],
    },
    "delivery-order": {
        "slug": "delivery-order",
        "kind": "interactive",
        "title": "Requesting a delivery order",
        "summary": "Raise the cargo service request that turns an approved consignment into a physical delivery order.",
        "objectives": [],
        "theory_html": "",
        "materials": [],
        "checks": [],
        "procedure": "Cargo service request",
        "steps": [
            {"title": "Open the service request", "instruction": "From the consignment record, start a new cargo service request.", "outcome": "The service request form opens pre-keyed with the UCR.", "verifications": [{"kind": "screen_opened", "detail": "Cargo service request"}]},
            {"title": "Select the delivery basis", "instruction": "Choose delivery order against the released bill of lading.", "outcome": "The basis is accepted with no manifest warning.", "verifications": []},
            {"title": "Confirm fees", "instruction": "Review the handling and statutory fees shown on the summary.", "outcome": "Fee lines are present on the request.", "verifications": []},
            {"title": "Submit the request", "instruction": "Submit and note the service request number.", "outcome": "The request is saved and visible in the register.", "verifications": [{"kind": "saved_record", "detail": "Cargo service request — status Submitted"}]},
        ],
    },
}


# ---------------------------------------------------------------------------
# Milestone 3 — mock demonstration capture scripts.
#
# The production recording engine (hybrid/demonstrations.py, conversion.py)
# exists but is gated off by DEMONSTRATION_RECORDING_ENABLED, which stays
# False in this environment. Nothing here is captured from the simulator:
# the prototype replays these scripted events as clearly labelled mock
# examples. Action codes and the proposed-step wording mirror the real
# engine's vocabulary (screen_opened / saved_record conditions,
# "Open the … screen in the simulator") so the review UI shows what the
# real conversion would produce for the consignment workflow.
# ---------------------------------------------------------------------------

DEMO_EVENT_SCRIPTS = {
    "consignment-app": [
        {
            "code": "portal.opened",
            "label": "Opened the Cargo service dashboard",
            "screen": "Simulator portal",
            "proposal": None,
        },
        {
            "code": "single_window.opened",
            "label": "Opened the single-window workspace",
            "screen": "Single window",
            "proposal": {
                "screen": "Single window",
                "title": "Open the single-window workspace",
                "instruction": "Open the single-window workspace from the Cargo service dashboard — this is where a clearing agent starts any application.",
                "outcome": "The single-window workspace is open.",
                "hint": "The workspace is the first entry point on the dashboard; every application starts there.",
                "condition": {"kind": "screen_opened", "detail": "Single window is open"},
            },
        },
        {
            "code": "consignment.create_form_opened",
            "label": "Opened the consignment application form",
            "screen": "Consignment application",
            "proposal": {
                "screen": "Consignment application",
                "title": "Start a new consignment application",
                "instruction": "From the single-window workspace, choose New consignment application so the form opens empty.",
                "outcome": "A blank consignment application form is open.",
                "hint": "If the form opens with old values, cancel and start again — copied drafts key on the wrong bill of lading.",
                "condition": {"kind": "screen_opened", "detail": "Consignment application form is open"},
            },
        },
        {
            "code": "record.selected",
            "label": "Selected an existing arrival notice to copy values from",
            "screen": "Consignment application",
            "proposal": None,
        },
        {
            "code": "fields.entered",
            "label": "Entered the bill of lading, consignee and package data",
            "screen": "Consignment application",
            "proposal": {
                "screen": "Consignment application",
                "title": "Key the bill of lading and consignee data",
                "instruction": "Enter the bill of lading number and issue date, then search and select the consignee by TIN so the trading-partner panel populates.",
                "outcome": "The manifest lookup returns the arrived line and the consignee details show on the application.",
                "hint": "Copy the number straight from the bill of lading — a one-character slip breaks the manifest match.",
                "condition": None,
            },
        },
        {
            "code": "consignment.saved",
            "label": "Saved the consignment application — status Draft",
            "screen": "Consignment application",
            "proposal": {
                "screen": "Consignment application",
                "title": "Save the application",
                "instruction": "Check each flagged field, then save the consignment application and note the returned unique consignment reference.",
                "outcome": "The application is saved as Draft and listed in the record register.",
                "hint": "The UCR is shown only after the first successful save — write it down before navigating away.",
                "condition": {"kind": "saved_record", "detail": "Consignment application saved as Draft"},
            },
        },
        {
            "code": "ucr.detail_opened",
            "label": "Confirmed the saved draft in the record register",
            "screen": "Unique Consignment Reference",
            "proposal": {
                "screen": "Unique Consignment Reference",
                "title": "Confirm the draft in the record register",
                "instruction": "Open the unique consignment reference record and confirm the saved application appears with status Draft.",
                "outcome": "The register lists the new draft against the UCR.",
                "hint": None,
                "condition": {"kind": "screen_opened", "detail": "Unique Consignment Reference register is open"},
            },
        },
    ],
}

# Used for interactive lessons without their own script — mirrors the only
# write the real engine currently captures: a demonstration UCR save.
DEFAULT_DEMO_EVENT_SCRIPT = [
    {
        "code": "portal.opened",
        "label": "Opened the Cargo service dashboard",
        "screen": "Simulator portal",
        "proposal": None,
    },
    {
        "code": "ucr.create_form_opened",
        "label": "Opened the UCR creation form",
        "screen": "Unique Consignment Reference",
        "proposal": {
            "screen": "Unique Consignment Reference",
            "title": "Open the unique consignment reference screen",
            "instruction": "Open the unique consignment reference screen from the dashboard and start a new reference.",
            "outcome": "The reference form is open.",
            "hint": None,
            "condition": {"kind": "screen_opened", "detail": "Unique Consignment Reference form is open"},
        },
    },
    {
        "code": "ucr.saved",
        "label": "Saved the reference as a draft",
        "screen": "Unique Consignment Reference",
        "proposal": {
            "screen": "Unique Consignment Reference",
            "title": "Save the reference",
            "instruction": "Complete the required fields and save; note the allocated reference number.",
            "outcome": "The reference is saved and appears in the register.",
            "hint": None,
            "condition": {"kind": "saved_record", "detail": "Unique Consignment Reference saved as Draft"},
        },
    },
]
