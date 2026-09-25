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


def compute_assessment(application):
    """Return (rows, totals) for the application using the configured TaxCodes."""
    exchange_rate = application.exchange_rate or Decimal("1")
    fob_ncy = _q2(application.fob_ncy if application.fob_ncy is not None else (application.fob_fcy or 0) * exchange_rate)
    freight_ncy = _q2(application.freight_ncy or 0)
    if application.insurance_ncy:
        insurance_ncy = _q2(application.insurance_ncy)
    else:
        insurance_ncy = _q2((fob_ncy + freight_ncy) * INSURANCE_RATE)
    customs_value = _q2(fob_ncy + freight_ncy + insurance_ncy)

    items = application.items or []
    hs_codes = [str(item.get("hs_code", "")).strip() for item in items]
    is_vehicle = any(code.startswith(VEHICLE_HS_PREFIX) for code in hs_codes)
    duty_hs_code = hs_codes[0] if hs_codes else ""

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
    totals = {
        "exchange_rate": exchange_rate,
        "fob_ncy": fob_ncy,
        "freight_ncy": freight_ncy,
        "insurance_ncy": insurance_ncy,
        "customs_value": customs_value,
        "import_duty": amounts.get(IMPORT_DUTY_CODE),
        "duty_hs_code": duty_hs_code,
        "is_vehicle": is_vehicle,
        "total": total,
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
