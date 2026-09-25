import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from decimal import Decimal

from assessment.models import Assessment
from assessment.service import refresh_assessment
from scenarios.models import ConsignmentApplication, GhanaHSCode, UcrDeclaration

User = get_user_model()

REFERENCE_ROWS = {
    "01": ("119441.83", "24", "20.00", "23888.37"),
    "02": ("143330.20", "31", "15.00", "21499.53"),
    "05": ("119441.83", "24", "0.00", "0.00"),
    "06": ("119441.83", "24", "0.50", "597.21"),
    "31": ("119441.83", "24", "1.00", "1194.42"),
    "32": ("106822.08", "25", "0.40", "427.29"),
    "33": ("427.29", "52", "15.00", "64.09"),
    "45": ("12.00", "", "", "12.00"),
    "47": ("143330.20", "31", "2.50", "3583.26"),
    "48": ("427.29", "52", "2.50", "10.68"),
    "49": ("119441.83", "24", "5.00", "5972.09"),
    "63": ("112.06", "", "", "112.06"),
    "72": ("5.00", "", "", "5.00"),
    "78": ("119441.83", "24", "2.00", "2388.84"),
    "87": ("119441.83", "24", "0.75", "895.81"),
    "88": ("143330.20", "31", "2.50", "3583.26"),
    "89": ("427.29", "52", "2.50", "10.68"),
    "98": ("119441.83", "24", "0.20", "238.88"),
}


def _make_vehicle_application(owner):
    ucr = UcrDeclaration.objects.create(
        owner=owner, regime="IM", goods_description="VEHICLE",
        origin_country="CN", destination_country="GH", transport_mode="10, Sea Transport",
        ucr_no="KGHTESTUCR9900000001", status=UcrDeclaration.Status.SUBMITTED,
    )
    return ConsignmentApplication.objects.create(
        owner=owner,
        ucr=ucr,
        status=ConsignmentApplication.Status.SUBMITTED,
        currency="JPY",
        exchange_rate=0.0696,
        fob_fcy=1534800.00,
        fob_ncy=106822.08,
        freight_ncy=11583.70,
        insurance_ncy=None,
        items=[{"hs_code": "8703240000", "description": "MOTOR CAR", "quantity": "1"}],
    )


@pytest.mark.django_db
def test_vehicle_assessment_matches_reference():
    owner = User.objects.create_user(username="assess-student", email="assess-student@example.test", password="x")
    GhanaHSCode.objects.update_or_create(code="8703240000", defaults={"description": "MOTOR CARS", "import_duty": "20.00"})
    application = _make_vehicle_application(owner)

    assessment = refresh_assessment(application)

    assert assessment.customs_value == Decimal("119441.83")
    assert assessment.import_duty == Decimal("23888.37")
    assert assessment.is_vehicle is True
    assert assessment.duty_hs_code == "8703240000"
    assert assessment.total == Decimal("64483.47")

    by_code = {row["code"]: row for row in assessment.rows}
    assert set(by_code) == set(REFERENCE_ROWS)
    for code, (base, tbc, rate, amount) in REFERENCE_ROWS.items():
        row = by_code[code]
        assert row["base"] == base, code
        assert row["tbc"] == tbc, code
        assert row["rate"] == rate, code
        assert row["amount"] == amount, code


@pytest.mark.django_db
def test_goods_assessment_drops_vehicle_taxes_and_uses_provided_insurance():
    owner = User.objects.create_user(username="assess-goods", email="assess-goods@example.test", password="x")
    GhanaHSCode.objects.update_or_create(code="6309000000", defaults={"description": "WORN CLOTHING", "import_duty": "20.00"})
    ucr = UcrDeclaration.objects.create(
        owner=owner, regime="IM", goods_description="USED CLOTHING",
        origin_country="CN", destination_country="GH", transport_mode="10, Sea Transport",
        ucr_no="KGHTESTUCR9900000002", status=UcrDeclaration.Status.SUBMITTED,
    )
    application = ConsignmentApplication.objects.create(
        owner=owner,
        ucr=ucr,
        status=ConsignmentApplication.Status.SUBMITTED,
        currency="USD",
        exchange_rate=1.0000,
        fob_ncy=10000.00,
        freight_ncy=500.00,
        insurance_ncy=250.00,
        items=[{"hs_code": "6309000000", "description": "USED SHOES", "quantity": "20"}],
    )

    assessment = refresh_assessment(application)

    assert assessment.customs_value == Decimal("10750.00")  # 10000 + 500 + provided 250
    assert assessment.is_vehicle is False
    by_code = {row["code"]: row for row in assessment.rows}
    assert "31" not in by_code and "49" not in by_code  # vehicle-only taxes drop out
    assert by_code["01"]["amount"] == "2150.00"         # 20% x 10750.00
    assert by_code["02"]["base"] == "12900.00"          # CV + duty
    assert by_code["02"]["amount"] == "1935.00"         # 15% x 12900.00


@pytest.mark.django_db
def test_assessment_page_is_owner_and_staff_only(client):
    owner = User.objects.create_user(username="assess-owner", email="assess-owner@example.test", password="x")
    other = User.objects.create_user(username="assess-other", email="assess-other@example.test", password="x")
    staff = User.objects.create_user(username="assess-staff", email="assess-staff@example.test", password="x", is_staff=True)
    application = _make_vehicle_application(owner)

    client.force_login(other)
    assert client.get(reverse("assessment-detail", args=(application.pk,))).status_code == 403

    client.force_login(staff)
    assert client.get(reverse("assessment-detail", args=(application.pk,))).status_code == 200

    client.force_login(owner)
    page = client.get(reverse("assessment-detail", args=(application.pk,)))
    assert page.status_code == 200
    assert Assessment.objects.filter(application=application).exists()
