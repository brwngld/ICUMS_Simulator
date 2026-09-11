from io import BytesIO
from decimal import Decimal
from types import SimpleNamespace
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from .models import CommercialDocument


NAVY = colors.HexColor("#17324D")
PALE = colors.HexColor("#EEF3F6")
LINE = colors.HexColor("#7F8D98")
LAYOUT_TITLES = {"bill_of_lading": "BILL OF LADING", "commercial_invoice": "COMMERCIAL INVOICE", "packing_list": "PACKING LIST", "generic": "CUSTOMS TRAINING DOCUMENT"}


def _value(data, *keys, default="Not supplied"):
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            return ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
    return default


def _labelled(label, value, styles):
    return Paragraph(f'<font size="6"><b>{escape(label.upper())}</b></font><br/>{escape(str(value)).replace(chr(10), "<br/>")}', styles["Small"])


def _grid_style(header_rows=()):
    commands = [("GRID", (0, 0), (-1, -1), 0.55, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    for row in header_rows:
        commands.extend((("BACKGROUND", (0, row), (-1, row), NAVY), ("TEXTCOLOR", (0, row), (-1, row), colors.white), ("FONTNAME", (0, row), (-1, row), "Helvetica-Bold")))
    return TableStyle(commands)


def _bill_of_lading_story(document, styles):
    data = document.learner_data
    bl_number = _value(data, "bill_of_lading_number", "bl_number", default=document.reference or "SIM-BL-000001")
    carrier = _value(data, "carrier", "carrier_name", default="Atlantic Training Carrier Ltd")
    header = Table([[Paragraph(f'<b>{escape(carrier)}</b><br/><font size="7">Fictitious carrier for simulator training</font>', styles["Carrier"]), Paragraph(f'<b>BILL OF LADING No.</b><br/><font size="14"><b>{escape(bl_number)}</b></font><br/><font size="7">NON-NEGOTIABLE TRAINING COPY</font>', styles["Right"])]], colWidths=(93 * mm, 77 * mm))
    header.setStyle(_grid_style())
    parties = Table([
        [_labelled("Shipper", _value(data, "shipper", "exporter"), styles), _labelled("Carrier or agent", _value(data, "carrier_agent", default=carrier), styles)],
        [_labelled("Consignee", _value(data, "consignee", "importer"), styles), _labelled("Booking reference", _value(data, "booking_reference", "booking_ref"), styles)],
        [_labelled("Notify party", _value(data, "notify_party", default=_value(data, "consignee", "importer")), styles), _labelled("Shipper reference", _value(data, "shipper_reference", "shipper_ref"), styles)],
    ], colWidths=(98 * mm, 72 * mm), rowHeights=(22 * mm, 22 * mm, 22 * mm))
    parties.setStyle(_grid_style())
    route = Table([
        [_labelled("Vessel and voyage", f'{_value(data, "vessel")} / {_value(data, "voyage_number", "voyage")}', styles), _labelled("Port of loading", _value(data, "port_of_loading"), styles), _labelled("Port of discharge", _value(data, "port_of_discharge"), styles)],
        [_labelled("Place of receipt", _value(data, "place_of_receipt"), styles), _labelled("Place of delivery", _value(data, "place_of_delivery"), styles), _labelled("Freight terms", _value(data, "freight_terms", default="Freight prepaid"), styles)],
    ], colWidths=(58 * mm, 56 * mm, 56 * mm))
    route.setStyle(_grid_style())
    cargo_data = [[Paragraph("CONTAINER, SEAL<br/>AND MARKS", styles["CargoHead"]), Paragraph("DESCRIPTION OF PACKAGES<br/>AND GOODS", styles["CargoHead"]), Paragraph("GROSS<br/>WEIGHT", styles["CargoHead"]), Paragraph("MEASUREMENT", styles["CargoHead"])]]
    cargo_rows = getattr(document, "cargo_rows", None)
    if cargo_rows:
        for row in cargo_rows:
            cargo_data.append([
                Paragraph(escape(row["container"]).replace(chr(10), "<br/>"), styles["Small"]),
                Paragraph(escape(row["description"]).replace(chr(10), "<br/>"), styles["Small"]),
                Paragraph(escape(row["weight"]), styles["Small"]),
                Paragraph(escape(row["measurement"]), styles["Small"]),
            ])
        cargo_data.append(["", Paragraph("TOTAL", styles["CargoHead"]), Paragraph(escape(_value(data, "gross_weight")), styles["CargoHead"]), Paragraph(escape(_value(data, "measurement", "volume")), styles["CargoHead"])])
    else:
        cargo_data.append([Paragraph(f'<b>{escape(_value(data, "container_number", "container_no"))}</b><br/>{escape(_value(data, "container_type", default="Container type not supplied"))}<br/><br/><b>Seal:</b> {escape(_value(data, "seal_number", "seal_no"))}', styles["Small"]), Paragraph(f'<b>{escape(_value(data, "package_count", "packages", default="Packages not supplied"))}</b><br/>{escape(_value(data, "goods_description", "description_of_goods")).replace(chr(10), "<br/>")}', styles["Small"]), Paragraph(escape(_value(data, "gross_weight")), styles["Small"]), Paragraph(escape(_value(data, "measurement", "volume")), styles["Small"])])
    cargo = Table(cargo_data, colWidths=(42 * mm, 82 * mm, 25 * mm, 21 * mm), repeatRows=1)
    cargo.setStyle(_grid_style(header_rows=(0,)))
    if cargo_rows:
        cargo.setStyle(TableStyle([("BACKGROUND", (0, -1), (-1, -1), NAVY), ("TEXTCOLOR", (0, -1), (-1, -1), colors.white)]))
    issue = Table([
        [_labelled("Declared value", _value(data, "declared_value"), styles), _labelled("Number of packages or containers", _value(data, "package_count", "packages"), styles)],
        [_labelled("Place and date of issue", _value(data, "place_and_date_of_issue", "issue_place_date"), styles), _labelled("Shipped on board date", _value(data, "shipped_on_board_date"), styles)],
    ], colWidths=(85 * mm, 85 * mm))
    issue.setStyle(_grid_style())
    return [header, parties, route, Spacer(1, 2 * mm), Paragraph("PARTICULARS FURNISHED FOR TRAINING PURPOSES", styles["Strip"]), cargo, issue]


def _generic_story(document, styles):
    rows = [["Field", "Fictitious training value"]]
    for key, value in document.learner_data.items():
        rows.append([Paragraph(str(key).replace("_", " ").title(), styles["BodyText"]), Paragraph(_value({"value": value}, "value"), styles["BodyText"])])
    if len(rows) == 1:
        rows.append(["Document status", "Fictitious training sample - details not yet entered"])
    table = Table(rows, colWidths=(55 * mm, 115 * mm), repeatRows=1)
    table.setStyle(_grid_style(header_rows=(0,)))
    return [Paragraph(LAYOUT_TITLES.get(document.pdf_layout, LAYOUT_TITLES["generic"]), styles["Heading1"]), Paragraph(document.title, styles["Heading2"]), Paragraph(f"Training reference: {document.reference or 'Not assigned'}", styles["Normal"]), Spacer(1, 5 * mm), table]


def build_fictitious_document_pdf(document):
    """Render learner-visible fictional data as a genuine, downloadable PDF."""
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=12 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="Carrier", parent=styles["BodyText"], fontName="Helvetica", fontSize=12, leading=14))
    styles.add(ParagraphStyle(name="Right", parent=styles["BodyText"], alignment=TA_RIGHT, fontSize=9, leading=11))
    styles.add(ParagraphStyle(name="Strip", parent=styles["BodyText"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=colors.white, backColor=NAVY, borderPadding=4))
    styles.add(ParagraphStyle(name="Warning", parent=styles["BodyText"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.HexColor("#9A3412")))
    styles.add(ParagraphStyle(name="CargoHead", parent=styles["BodyText"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=6.5, leading=7.5, textColor=colors.white))
    story = [Paragraph("TRAINING SAMPLE - FICTITIOUS - NOT FOR COMMERCIAL USE", styles["Warning"]), Spacer(1, 3 * mm)]
    story.extend(_bill_of_lading_story(document, styles) if document.pdf_layout == "bill_of_lading" else _generic_story(document, styles))
    story.extend([Spacer(1, 5 * mm), KeepTogether([Paragraph("Training notice", styles["Heading3"]), Paragraph("This document was generated solely for ICUMS simulator training. Every party, shipment, value, identifier, and transaction shown is fictitious. It has no legal, customs, banking, shipping, or commercial effect.", styles["Small"])])])
    doc.build(story)
    return output.getvalue()


def build_bill_of_lading_pdf(bill):
    """Render a structured BillOfLading and its repeatable cargo items."""
    items = list(bill.cargo_items.all())
    containers = []
    container_types = []
    seals = []
    descriptions = []
    total_weight = Decimal("0")
    total_measurement = Decimal("0")
    package_total = 0
    cargo_rows = []
    for item in items:
        container_line = item.container_number
        if item.container_type:
            container_line += f" ({item.container_type})"
        if item.seal_number:
            container_line += f" / Seal {item.seal_number}"
        if container_line not in containers:
            containers.append(item.container_number)
        if item.container_type and item.container_type not in container_types:
            container_types.append(item.container_type)
        if item.seal_number and item.seal_number not in seals:
            seals.append(item.seal_number)
        package_total += item.package_quantity
        total_weight += item.gross_weight
        if item.measurement is not None:
            total_measurement += item.measurement
        detail = f"{item.package_quantity} {item.package_type}"
        if item.goods_description:
            detail += f" - {item.goods_description}"
        if item.cargo_type == "vehicle":
            vehicle = " ".join(str(value) for value in (item.vehicle_year, item.vehicle_make, item.vehicle_model) if value)
            if vehicle:
                detail += f"\n{vehicle}"
            if item.vin_or_chassis:
                detail += f"\nVIN/Chassis: {item.vin_or_chassis}"
        if item.hs_code:
            detail += f"\nHS code: {item.hs_code}"
        if item.marks_and_numbers:
            detail += f"\nMarks: {item.marks_and_numbers}"
        descriptions.append(detail)
        cargo_rows.append({
            "container": "\n".join(part for part in (item.container_number, item.container_type, f"Seal: {item.seal_number}" if item.seal_number else "", item.marks_and_numbers) if part),
            "description": detail,
            "weight": f"{item.gross_weight:,.3f} {item.weight_unit}",
            "measurement": f"{item.measurement:,.3f} {item.measurement_unit}" if item.measurement is not None else "-",
        })
    data = {
        "carrier": bill.carrier,
        "carrier_agent": bill.carrier_agent,
        "bill_of_lading_number": bill.reference,
        "shipper": bill.shipper,
        "consignee": bill.consignee,
        "notify_party": bill.notify_party,
        "booking_reference": bill.booking_reference,
        "shipper_reference": bill.shipper_reference,
        "vessel": bill.vessel,
        "voyage_number": bill.voyage_number,
        "place_of_receipt": bill.place_of_receipt,
        "port_of_loading": bill.port_of_loading,
        "port_of_discharge": bill.port_of_discharge,
        "place_of_delivery": bill.place_of_delivery,
        "freight_terms": bill.freight_terms,
        "container_number": "\n".join(containers) or "No container entered",
        "container_type": " / ".join(container_types) or "Not supplied",
        "seal_number": " / ".join(seals) or "Not supplied",
        "package_count": f"{package_total} package(s)",
        "goods_description": "\n\n".join(descriptions) or "No cargo item entered",
        "gross_weight": f"{total_weight:,.3f} KGM",
        "measurement": f"{total_measurement:,.3f} MTQ" if total_measurement else "Not supplied",
        "declared_value": bill.shippers_declared_value or "Not declared",
        "place_and_date_of_issue": " - ".join(part for part in (bill.place_of_issue, bill.date_of_issue.isoformat() if bill.date_of_issue else "") if part),
        "shipped_on_board_date": bill.shipped_on_board_date.isoformat() if bill.shipped_on_board_date else "Not supplied",
    }
    if bill.additional_declarations:
        data["goods_description"] += f"\n\n{bill.additional_declarations}"
    adapter = SimpleNamespace(pdf_layout="bill_of_lading", learner_data=data, reference=bill.reference, title=bill.title, cargo_rows=cargo_rows)
    return build_fictitious_document_pdf(adapter)


def build_commercial_document_pdf(document):
    """Render the structured invoice or packing list as a genuine training PDF."""
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm, topMargin=12 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="DocSmall", parent=styles["BodyText"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="DocTitle", parent=styles["Heading1"], fontSize=16, textColor=NAVY, spaceAfter=5))
    styles.add(ParagraphStyle(name="DocWarn", parent=styles["BodyText"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=8, textColor=colors.HexColor("#9A3412")))
    packing = document.document_type == CommercialDocument.DocumentType.PACKING_LIST
    title = {CommercialDocument.DocumentType.PACKING_LIST: "PACKING LIST", CommercialDocument.DocumentType.PROFORMA_INVOICE: "PROFORMA INVOICE"}.get(document.document_type, "COMMERCIAL INVOICE")
    def p(value):
        return Paragraph(escape(str(value or "")).replace("\n", "<br/>"), styles["DocSmall"])
    story = [Paragraph("TRAINING SAMPLE - FICTITIOUS - NOT FOR COMMERCIAL USE", styles["DocWarn"]), Spacer(1, 3 * mm), Paragraph(title, styles["DocTitle"])]
    if document.document_type == CommercialDocument.DocumentType.PROFORMA_INVOICE:
        story.append(Paragraph("QUOTATION ONLY - VALUES ARE PROVISIONAL AND THIS IS NOT A FINAL COMMERCIAL INVOICE", styles["DocWarn"]))
    story.append(Table([[p(document.exporter_name + ("\n" + document.exporter_address if document.exporter_address else "")), p("Reference: " + document.reference + ("\nDate: " + document.document_date.isoformat() if document.document_date else ""))], [p("Contact: " + document.exporter_contact), p("Container / shipment: " + (document.container_reference or "Not supplied"))], [p(document.consignee_name + ("\n" + document.consignee_address if document.consignee_address else "")), p("Currency: " + document.currency + ("\nTerms: " + document.payment_terms if document.payment_terms else ""))]], colWidths=(95 * mm, 85 * mm), style=_grid_style()))
    if packing:
        headers = ["NO.", "DESCRIPTION OF GOODS", "QTY", "PACKAGES / PCS", "NET WEIGHT", "GROSS WEIGHT"]
        widths = (10 * mm, 62 * mm, 24 * mm, 31 * mm, 24 * mm, 24 * mm)
    else:
        headers = ["NO.", "DESCRIPTION OF GOODS", "QTY", "UNIT PRICE", "AMOUNT"]
        widths = (10 * mm, 83 * mm, 20 * mm, 32 * mm, 35 * mm)
    rows = [[Paragraph(h, styles["DocSmall"]) for h in headers]]
    total_amount = Decimal("0")
    total_net = Decimal("0")
    total_gross = Decimal("0")
    for index, line in enumerate(document.line_items.all(), 1):
        qty = f"{line.quantity:g} {line.quantity_unit}"
        if packing:
            rows.append([p(index), p(line.description), p(qty), p((f"{line.package_count} pkgs" if line.package_count else "") + (f"\n{line.pieces_per_package}" if line.pieces_per_package else "")), p(f"{line.net_weight:g} {line.weight_unit}" if line.net_weight is not None else "-"), p(f"{line.gross_weight:g} {line.weight_unit}" if line.gross_weight is not None else "-")])
            total_net += line.net_weight or Decimal("0"); total_gross += line.gross_weight or Decimal("0")
        else:
            amount = line.amount if line.amount is not None else ((line.unit_price or Decimal("0")) * line.quantity)
            total_amount += amount
            rows.append([str(index), p(line.description), qty, p(f"{document.currency} {line.unit_price:,.2f}" if line.unit_price is not None else "-"), p(f"{document.currency} {amount:,.2f}")])
    if len(rows) == 1:
        rows.append(["1", p("No line items entered"), "-", "-", "-", "-"] if packing else ["1", p("No line items entered"), "-", "-", "-"])
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(_grid_style(header_rows=(0,)))
    story.extend([Spacer(1, 4 * mm), table])
    if packing:
        story.append(Table([[p("TOTAL NET WEIGHT"), p(f"{total_net:g} KGM"), p("TOTAL GROSS WEIGHT"), p(f"{total_gross:g} KGM")]], colWidths=(42 * mm, 48 * mm, 46 * mm, 44 * mm), style=_grid_style()))
    else:
        fob = document.fob if document.fob is not None else total_amount
        freight = document.freight or Decimal("0"); insurance = document.insurance or Decimal("0")
        story.append(Table([[p("FOB"), p(f"{document.currency} {fob:,.2f}")], [p("FREIGHT / FRT"), p(f"{document.currency} {freight:,.2f}")], [p("INSURANCE / INS"), p(f"{document.currency} {insurance:,.2f}")], [p("TOTAL C&F / CFR"), p(f"{document.currency} {(fob + freight + insurance):,.2f}")]], colWidths=(55 * mm, 55 * mm), hAlign="RIGHT", style=_grid_style()))
    if document.notes:
        story.extend([Spacer(1, 3 * mm), p(document.notes)])
    story.extend([Spacer(1, 5 * mm), p("This document was generated solely for ICUMS simulator training. All parties, shipment details, values and identifiers are fictitious.")])
    doc.build(story)
    return output.getvalue()
