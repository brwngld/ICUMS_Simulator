from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "ICUMS_Simulator_Administrator_Manual.docx"
OUTPUT = ROOT / "docs" / "ICUMS_Simulator_Administrator_Manual.pdf"
NAVY = colors.HexColor("#17324D")
PALE = colors.HexColor("#EEF3F6")
LINE = colors.HexColor("#D9D9D9")


def blocks(document):
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield DocxParagraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield DocxTable(child, document)


def clean(text):
    return escape(text).replace("\n", "<br/>")


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#596873"))
    canvas.drawString(18 * mm, 10 * mm, "ICUMS Simulator Administrator Manual - Training simulator only")
    canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


source = Document(SOURCE)
base = getSampleStyleSheet()
styles = {
    "Title": ParagraphStyle("ManualTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=colors.black, spaceAfter=10),
    "Subtitle": ParagraphStyle("ManualSubtitle", parent=base["Normal"], fontName="Helvetica", fontSize=12, leading=16, textColor=colors.HexColor("#374151"), spaceAfter=8),
    "Heading 1": ParagraphStyle("ManualH1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=colors.black, spaceBefore=12, spaceAfter=7, keepWithNext=True),
    "Heading 2": ParagraphStyle("ManualH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.black, spaceBefore=10, spaceAfter=5, keepWithNext=True),
    "Heading 3": ParagraphStyle("ManualH3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=colors.black, spaceBefore=8, spaceAfter=4, keepWithNext=True),
    "Normal": ParagraphStyle("ManualBody", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=12.5, spaceAfter=6),
    "List Bullet": ParagraphStyle("ManualBullet", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=12.5, leftIndent=12, firstLineIndent=-7, bulletIndent=4, spaceAfter=3),
    "List Number": ParagraphStyle("ManualNumber", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=12.5, leftIndent=14, firstLineIndent=-9, bulletIndent=3, spaceAfter=4),
}
cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=7.7, leading=10, spaceAfter=0)
head_style = ParagraphStyle("CellHead", parent=cell_style, fontName="Helvetica-Bold", textColor=colors.white)
story = []
number = 0
for block in blocks(source):
    if isinstance(block, DocxParagraph):
        text = block.text.strip()
        if not text:
            continue
        name = block.style.name if block.style else "Normal"
        if name.startswith("List Number"):
            number += 1
            story.append(Paragraph(clean(text), styles["List Number"], bulletText=f"{number}."))
        elif name.startswith("List Bullet"):
            story.append(Paragraph(clean(text), styles["List Bullet"], bulletText="•"))
        else:
            number = 0
            story.append(Paragraph(clean(text), styles.get(name, styles["Normal"])))
    else:
        rows = []
        for r_idx, row in enumerate(block.rows):
            rows.append([Paragraph(clean(cell.text.strip()), head_style if r_idx == 0 else cell_style) for cell in row.cells])
        if not rows:
            continue
        count = len(rows[0])
        widths = {2: (46 * mm, 128 * mm), 3: (39 * mm, 64 * mm, 71 * mm)}.get(count, tuple([174 * mm / count] * count))
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        commands = [("GRID", (0, 0), (-1, -1), .45, LINE), ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
        for idx in range(2, len(rows), 2):
            commands.append(("BACKGROUND", (0, idx), (-1, idx), PALE))
        table.setStyle(TableStyle(commands))
        story.extend([table, Spacer(1, 4 * mm)])

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
pdf = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=17 * mm, title="ICUMS Simulator Administrator Manual", author="ICUMS Simulator")
pdf.build(story, onFirstPage=footer, onLaterPages=footer)
print(OUTPUT)
