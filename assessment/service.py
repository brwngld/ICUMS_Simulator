"""Duty assessment computation for a consignment application.

Formulas follow the training reference (illustrative values, not official duty):
    FOB Ncy      = FOB Fcy x exchange rate
    Insurance    = provided, or (FOB Ncy + Freight Ncy) x 0.875% when absent
    Customs Value= FOB Ncy + Freight Ncy + Insurance
    Import Duty  = Customs Value x HS code duty rate
    CV + ID      = base for VAT, NHIL, GET Fund
    Network Chg  = FOB Ncy x 0.4% (its VAT/NHIL/GET Fund levies ride on it)
"""

from decimal import Decimal, ROUND_HALF_UP

from scenarios.models import GhanaHSCode

TWO_PLACES = Decimal("0.01")

TBC_BY_BASE = {"cv": "24", "cv_duty": "31", "fob": "25", "network": "52", "flat": ""}

NETWORK_CHARGE_CODE = "32"
IMPORT_DUTY_CODE = "01"
VEHICLE_HS_PREFIX = "87"
INSURANCE_RATE = Decimal("0.00875")


def _q2(value) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _percent(base: Decimal, rate: Decimal) -> Decimal:
    return _q2(base * rate / Decimal("100"))


def hs_duty_rate(hs_code: str) -> Decimal:
    """Import duty percentage for the item's HS code from the seeded tariff."""
    code = (hs_code or "").strip()
    if not code:
        return Decimal("0")
    match = GhanaHSCode.objects.filter(code__iexact=code[:10]).first()
    if match is None and len(code) >= 6:
        match = GhanaHSCode.objects.filter(code__istartswith=code[:6]).order_by("code").first()
    if match is None:
        return Decimal("0")
    try:
        return Decimal(str(match.import_duty).replace("%", "").strip() or "0")
    except Exception:
        return Decimal("0")


def compute_from_invoice(fob_ncy, freight_ncy, insurance_ncy, hs_codes):
    """Compute the tax rows from invoice values. Returns (rows, summary)."""
    fob_ncy = _q2(fob_ncy or 0)
    freight_ncy = _q2(freight_ncy or 0)
    if insurance_ncy:
        insurance_ncy = _q2(insurance_ncy)
    else:
        insurance_ncy = _q2((fob_ncy + freight_ncy) * INSURANCE_RATE)
    customs_value = _q2(fob_ncy + freight_ncy + insurance_ncy)
    duty_hs_code = hs_codes[0] if hs_codes else ""
    is_vehicle = any(code.startswith(VEHICLE_HS_PREFIX) for code in hs_codes)

    from .models import TaxCode

    amounts = {}
    rows = []

    def base_amount(tax) -> Decimal:
        if tax.base == TaxCode.Base.CUSTOMS_VALUE:
            return customs_value
        if tax.base == TaxCode.Base.CV_PLUS_DUTY:
            return customs_value + amounts.get(IMPORT_DUTY_CODE, Decimal("0"))
        if tax.base == TaxCode.Base.FOB_NCY:
            return fob_ncy
        if tax.base == TaxCode.Base.NETWORK_CHARGE:
            return amounts.get(NETWORK_CHARGE_CODE, Decimal("0"))
        return Decimal("0")

    for tax in TaxCode.objects.filter(active=True).order_by("code"):
        if tax.applies_to == TaxCode.AppliesTo.VEHICLES and not is_vehicle:
            continue
        if tax.base == TaxCode.Base.FLAT:
            rate = None
            base = _q2(tax.flat_amount or 0)
            amount = _q2(tax.flat_amount or 0)
        else:
            rate = hs_duty_rate(duty_hs_code) if tax.code == IMPORT_DUTY_CODE else (tax.rate if tax.rate is not None else Decimal("0"))
            base = _q2(base_amount(tax))
            amount = _percent(base, rate)
        amounts[tax.code] = amount
        rows.append({
            "code": tax.code,
            "name": tax.name,
            "base": f"{base:.2f}",
            "tbc": TBC_BY_BASE.get(tax.base, ""),
            "rate": f"{rate:.2f}" if rate is not None else "",
            "amount": f"{amount:.2f}",
        })

    total = _q2(sum(amounts.values(), Decimal("0")))
    summary = {
        "customs_value": customs_value,
        "import_duty": amounts.get(IMPORT_DUTY_CODE),
        "duty_hs_code": duty_hs_code,
        "is_vehicle": is_vehicle,
        "total": total,
    }
    return rows, summary


def compute_assessment(application):
    """Return (rows, totals) for a consignment application using the configured TaxCodes."""
    exchange_rate = application.exchange_rate or Decimal("1")
    fob_ncy = _q2(application.fob_ncy if application.fob_ncy is not None else (application.fob_fcy or 0) * exchange_rate)
    freight_ncy = _q2(application.freight_ncy or 0)
    if application.insurance_ncy:
        insurance_ncy = _q2(application.insurance_ncy)
    else:
        insurance_ncy = _q2((fob_ncy + freight_ncy) * INSURANCE_RATE)
    items = application.items or []
    hs_codes = [str(item.get("hs_code", "")).strip() for item in items]
    rows, summary = compute_from_invoice(fob_ncy, freight_ncy, insurance_ncy, hs_codes)
    totals = {
        "exchange_rate": exchange_rate,
        "fob_ncy": fob_ncy,
        "freight_ncy": freight_ncy,
        "insurance_ncy": insurance_ncy,
        **summary,
    }
    return rows, totals


def refresh_assessment(application):
    """Compute and persist the assessment snapshot for the application."""
    from .models import Assessment

    rows, totals = compute_assessment(application)
    assessment, _ = Assessment.objects.get_or_create(application=application)
    for field, value in totals.items():
        setattr(assessment, field, value)
    assessment.rows = rows
    assessment.save()
    return assessment


# --- BOE Tax tab preview ----------------------------------------------------
#
# The Tax tab renders the full 18-row ICUMS levy catalogue before and after the
# "Compute Tax" click.  Rows the duty engine cannot derive yet stay 0.00 (the
# product owner reconciles those later); every money value is a display string
# with thousands separators, e.g. "17,619.20", and rates use four decimals.

FOUR_PLACES = Decimal("0.0001")

# basis: "cv" item customs value (TBC 24); "cv_hs"/"cv_duty_hs" same bases but the
# rate comes from the item's GhanaHSCode record; "cv_duty" customs value + import
# duty (TBC 31); "cv_network_base" customs value under TBC 25 (Network Charge);
# "network" the Network Charge amount (TBC 52); "flat" declaration-level flat
# amount; "unknown" basis not yet reproduced (stays 0.00).
TAX_CATALOG = (
    {"code": "01", "name": "Import Duty", "basis": "cv_hs"},
    {"code": "02", "name": "Import VAT", "basis": "cv_duty_hs"},
    {"code": "05", "name": "Processing Fee", "basis": "cv"},
    {"code": "06", "name": "ECOWAS Levy", "basis": "cv"},
    {"code": "32", "name": "Network Charge", "basis": "cv_network_base"},
    {"code": "33", "name": "Network Charge VAT", "basis": "network"},
    {"code": "45", "name": "Ghana Shippers Authority SNF Fee", "basis": "flat"},
    {"code": "47", "name": "Import NHIL", "basis": "cv_duty_hs"},
    {"code": "48", "name": "Network Charge NHIL", "basis": "network"},
    {"code": "56", "name": "1% Withholding Tax on Import", "basis": "cv"},
    {"code": "63", "name": "GHS Disinfection Fee", "basis": "unknown"},
    {"code": "72", "name": "MoTI e-IDF Fee", "basis": "flat"},
    {"code": "78", "name": "Special Import Levy (2%)", "basis": "cv"},
    {"code": "87", "name": "Ghana Export-Import Bank (EXIM) Levy", "basis": "cv"},
    {"code": "88", "name": "Ghana Education Trust (GET) Fund Import Levy", "basis": "cv_duty"},
    {"code": "89", "name": "Network Charge GET Fund Levy", "basis": "network"},
    {"code": "93", "name": "Inspection Fee", "basis": "cv"},
    {"code": "98", "name": "African Union Import Levy", "basis": "cv"},
)

_TAX_HS_RATE_FIELDS = {"01": "import_duty", "02": "import_vat", "47": "nhil_rate"}
_TAX_FIXED_RATES = {
    "05": Decimal("0"), "06": Decimal("0.5"), "32": Decimal("0.4"),
    "33": Decimal("15"), "48": Decimal("2.5"), "56": Decimal("1"),
    "78": Decimal("2"), "87": Decimal("0.75"), "88": Decimal("0"),
    "89": Decimal("2.5"), "93": Decimal("1"), "98": Decimal("0.2"),
}
_TAX_FLAT_AMOUNTS = {"45": Decimal("12.00"), "72": Decimal("5.00")}
_TAX_TBC_BY_BASIS = {"cv": "24", "cv_hs": "24", "cv_duty": "31", "cv_duty_hs": "31", "network": "52", "cv_network_base": "25"}


def _parse_percent(value) -> Decimal:
    """Tolerant percent parse for GhanaHSCode CharFields holding "20", "20.000" or "20%"."""
    if value is None:
        return Decimal("0")
    text = str(value).strip().replace("%", "").replace(",", "")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except Exception:
        return Decimal("0")


def _money(value) -> str:
    return f"{_q2(value):,.2f}"


def _rate4(value) -> str:
    return f"{Decimal(value).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP):.4f}"


def _tax_hs_record(hs_code, cache):
    """GhanaHSCode row for an item, following hs_duty_rate's lookup convention."""
    code = (hs_code or "").strip()
    if not code:
        return None
    key = code[:10].lower()
    if key in cache:
        return cache[key]
    match = GhanaHSCode.objects.filter(code__iexact=code[:10]).first()
    if match is None and len(code) >= 6:
        match = GhanaHSCode.objects.filter(code__istartswith=code[:6]).order_by("code").first()
    cache[key] = match
    return match


def _tax_decimal(value) -> Decimal:
    try:
        return Decimal(str(value).replace(",", "").strip() or "0")
    except Exception:
        return Decimal("0")


def compute_tax_preview(form_data, hs_cache=None):
    """Estimated duty preview for the BOE declaration Tax tab's Compute Tax button.

    Returns the full 18-row catalogue (declaration level), the per-item breakdown
    with base/TBC/rate detail, and the totals.  Amounts that the rules above do
    not support (currently the GHS Disinfection Fee, code 63) stay "0.00".
    """
    data = form_data if isinstance(form_data, dict) else {}
    cache = hs_cache if isinstance(hs_cache, dict) else {}
    raw_items = [item for item in (data.get("items") or []) if isinstance(item, dict)]

    def pick(*values):
        """First value that is present (non-blank), parsed as a Decimal amount."""
        for value in values:
            if str(value if value is not None else "").strip():
                return _tax_decimal(value)
        return Decimal("0")

    item_amounts = []
    item_results = []
    item_total = Decimal("0")
    for index, item in enumerate(raw_items):
        fob = pick(item.get("fob_ncy"), data.get("fob_ncy"))
        customs_value = pick(item.get("customs_value_ncy"), data.get("customs_value_ncy"),
                             item.get("fob_ncy"), data.get("fob_ncy"))
        hs = _tax_hs_record(item.get("hs_code"), cache)
        amounts = {}
        rows = []
        for entry in TAX_CATALOG:
            basis = entry["basis"]
            if basis in ("flat", "unknown"):
                continue  # declaration-level only
            code = entry["code"]
            if code in _TAX_HS_RATE_FIELDS:
                rate = _parse_percent(getattr(hs, _TAX_HS_RATE_FIELDS[code], None) if hs else None)
            else:
                rate = _TAX_FIXED_RATES[code]
            if basis == "network":
                base = amounts.get("32", Decimal("0"))
            elif basis.startswith("cv_duty"):
                base = customs_value + amounts.get("01", Decimal("0"))
            else:
                base = customs_value
            exact = base * rate / Decimal("100")
            amounts[code] = exact
            rows.append({
                "code": code,
                "name": entry["name"],
                "base": _money(base),
                "tbc": _TAX_TBC_BY_BASIS[basis],
                "rate": _rate4(rate),
                "exempted": "0.00",
                "suspended": "0.00",
                "payable": _money(exact),
            })
        payable = _q2(sum(amounts.values(), Decimal("0")))
        item_total += payable
        item_amounts.append(amounts)
        item_results.append({
            "index": index,
            "item_no": str(item.get("item_no") or f"{index + 1:04d}").strip() or f"{index + 1:04d}",
            "hs_code": str(item.get("hs_code", "") or ""),
            "cpc": str(item.get("cpc", "") or data.get("cpc", "") or ""),
            "fob_ncy": _money(fob),
            "customs_value_ncy": _money(customs_value),
            "exempted": "0.00",
            "suspended": "0.00",
            "payable": _money(payable),
            "rows": rows,
        })

    declaration_rows = []
    total = item_total + sum(_TAX_FLAT_AMOUNTS.values(), Decimal("0"))
    for entry in TAX_CATALOG:
        basis = entry["basis"]
        if basis == "flat":
            amount = _TAX_FLAT_AMOUNTS[entry["code"]]
        elif basis == "unknown":
            amount = Decimal("0")
        else:
            amount = _q2(sum((amounts.get(entry["code"], Decimal("0")) for amounts in item_amounts), Decimal("0")))
        declaration_rows.append({
            "code": entry["code"],
            "name": entry["name"],
            "user_defined": "N",
            "exempted": "0.00",
            "suspended": "0.00",
            "payable": _money(amount),
        })

    customs_value_fcy = _tax_decimal(data.get("customs_value_fcy"))
    if not customs_value_fcy:
        customs_value_fcy = sum((_tax_decimal(item.get("customs_value_fcy")) for item in raw_items), Decimal("0"))
    customs_value_ncy = _tax_decimal(data.get("customs_value_ncy"))
    if not customs_value_ncy:
        customs_value_ncy = sum((_tax_decimal(item.get("customs_value_ncy")) for item in raw_items), Decimal("0"))
    return {
        "declaration_rows": declaration_rows,
        "totals": {"tax": _money(total), "exempted": "0.00", "guarantee": "0.00", "payable": _money(total)},
        "customs_value": {"fcy": _money(customs_value_fcy), "ncy": _money(customs_value_ncy)},
        "items": item_results,
        "item_total": _money(item_total),
    }
