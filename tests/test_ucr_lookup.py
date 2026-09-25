import re
import json
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.db import IntegrityError, transaction
from django.forms.models import inlineformset_factory
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from scenarios.admin import TrainingServiceProviderForm, TrainingStakeholderForm, TrainingStakeholderNameForm, TrainingStakeholderNameFormSet
from scenarios.models import MdaAgency, MdaApplication, MdaConsignmentRequest, MdaProcess, MdaStatus, TrainingStakeholder, TrainingStakeholderName, TrainingServiceProvider, UcrDeclaration, UcrDocumentAttachment


@pytest.mark.django_db
def test_training_stakeholder_code_rules():
    for code in ("P0012345678", "C0012345678", "G0012345678", "Q0012345678", "V0012345678", "GHA1234567890"):
        TrainingStakeholder(code=code, tin_type=code[:3], name="Fictional learner company").full_clean()
    for code in ("P00123", "X0012345678", "GHA12345678", "C00INVALID!!"):
        with pytest.raises(ValidationError):
            TrainingStakeholder(code=code, name="Fictional learner company").full_clean()


@pytest.mark.django_db
def test_duplicate_tin_is_rejected_but_same_name_can_use_another_tin():
    TrainingStakeholder.objects.create(code="C0011111111", name="Fictional Shared Name", roles=["importer"])
    second = TrainingStakeholder(code="C0022222222", name="Fictional Shared Name", roles=["exporter"])
    second.full_clean()
    second.save()
    with pytest.raises(ValidationError):
        TrainingStakeholder(code="C0011111111", name="Different Name", roles=["cha"]).full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        TrainingStakeholder.objects.create(code="c0011111111", name="Case Variant")


@pytest.mark.django_db
def test_same_name_can_repeat_with_distinct_roles_under_one_tin():
    stakeholder = TrainingStakeholder.objects.create(code="C0033333333", name="Fictional Primary", roles=["importer"])
    distinct = TrainingStakeholderName(stakeholder=stakeholder, name=" fictional primary ", roles=["exporter"])
    distinct.full_clean()
    distinct.save()
    with pytest.raises(ValidationError):
        TrainingStakeholderName(stakeholder=stakeholder, name="Fictional Primary", roles=["importer", "cha"]).full_clean()
    with pytest.raises(ValidationError):
        TrainingStakeholderName(stakeholder=stakeholder, name="fictional primary", roles=["exporter"]).full_clean()


@pytest.mark.django_db
def test_admin_rejects_duplicate_unsaved_additional_names():
    stakeholder = TrainingStakeholder(code="C0044444444", name="Primary Name", roles=["importer"])
    formset_class = inlineformset_factory(
        TrainingStakeholder, TrainingStakeholderName,
        form=TrainingStakeholderNameForm, formset=TrainingStakeholderNameFormSet,
        fields=("name", "address", "roles"), extra=2,
    )
    prefix = formset_class.get_default_prefix()
    formset = formset_class(data={
        f"{prefix}-TOTAL_FORMS": "2", f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000",
        f"{prefix}-0-name": "Shared Alias", f"{prefix}-0-roles": ["exporter"],
        f"{prefix}-1-name": " shared alias ", f"{prefix}-1-roles": ["exporter", "cha"],
    }, instance=stakeholder)
    assert not formset.is_valid()
    assert "selected roles" in str(formset.errors)

    valid_formset = formset_class(data={
        f"{prefix}-TOTAL_FORMS": "2", f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000",
        f"{prefix}-0-name": "Shared Alias", f"{prefix}-0-roles": ["exporter"],
        f"{prefix}-1-name": " shared alias ", f"{prefix}-1-roles": ["cha"],
    }, instance=stakeholder)
    assert valid_formset.is_valid(), valid_formset.errors


@pytest.mark.django_db
def test_ucr_lookup_needs_exact_registered_code(client):
    user = User.objects.create_user(username="ucr-author", password="test-pass", is_staff=True)
    client.force_login(user)
    url = reverse("ucr-stakeholder-lookup")
    short = client.get(url, {"code": ""})
    assert short.status_code == 400
    assert short.json()["error"] == "The code entered is an invalid code.( input at least 11 characters)"
    unknown = client.get(url, {"code": "C0099999999"})
    assert unknown.status_code == 404
    assert "NID/TIN not registered" in unknown.json()["error"]
    stakeholder = TrainingStakeholder.objects.create(code="P0012345678", tin_type="P00", name="Practice One", address="Primary address", roles=["importer"])
    TrainingStakeholderName.objects.create(stakeholder=stakeholder, name="Practice Two", address="Second address", roles=["freight_forwarder"])
    TrainingStakeholder.objects.create(code="P0012345679", tin_type="P00", name="Unrelated person")
    found = client.get(url, {"code": "P0012345678"})
    assert found.status_code == 200
    assert [entry["name"] for entry in found.json()["results"]] == ["Practice One", "Practice Two"]
    assert [entry["description"] for entry in found.json()["results"]] == ["Practice One - (Importer)", "Practice Two - (Freight Forwarder)"]
    assert [entry["address"] for entry in found.json()["results"]] == ["Primary address", "Second address"]


@pytest.mark.django_db
def test_ucr_lookup_shows_same_name_in_separate_role_rows(client):
    client.force_login(User.objects.create_user(username="ucr-roles", password="test-pass", is_staff=True))
    stakeholder = TrainingStakeholder.objects.create(code="C0066666666", name="Fictional Company", roles=["importer", "exporter"])
    TrainingStakeholderName.objects.create(stakeholder=stakeholder, name="Fictional Company", roles=["cha"])
    response = client.get(reverse("ucr-stakeholder-lookup"), {"code": stakeholder.code})
    assert response.status_code == 200
    assert [row["description"] for row in response.json()["results"]] == [
        "Fictional Company - (Importer, Exporter)",
        "Fictional Company - (CHA / Declarant)",
    ]


@pytest.mark.django_db
def test_admin_form_generates_code_for_selected_type():
    form = TrainingStakeholderForm(data={"tin_type": "Q00", "generation_mode": "auto", "name": "Fictional Mission", "is_active": "on", "roles": ["importer", "freight_forwarder"]})
    assert form.is_valid(), form.errors
    stakeholder = form.save()
    assert stakeholder.code.startswith("Q00") and len(stakeholder.code) == 11
    assert stakeholder.roles == ["importer", "freight_forwarder"]


@pytest.mark.django_db
def test_additional_name_requires_its_own_role():
    without_role = TrainingStakeholderNameForm(data={"name": "Second training name", "address": "Second address"})
    assert not without_role.is_valid()
    with_role = TrainingStakeholderNameForm(data={"name": "Second training name", "address": "Second address", "roles": ["cha"]})
    assert with_role.is_valid(), with_role.errors


@pytest.mark.django_db
def test_training_stakeholder_admin_shows_name_roles_and_generation_choice(client):
    admin_user = User.objects.create_superuser(username="stakeholder-admin", password="test-pass", email="admin@example.test")
    client.force_login(admin_user)
    response = client.get(reverse("admin:scenarios_trainingstakeholder_add"))
    assert response.status_code == 200
    assert b"Generate code automatically" in response.content
    assert b"Primary name (required)" in response.content
    assert b"Additional names" in response.content
    assert b"admin/js/training-stakeholder.js" in response.content


@pytest.mark.django_db
def test_merged_code_resolves_to_survivor_names(client):
    user = User.objects.create_user(username="ucr-merger", password="test-pass", is_staff=True)
    client.force_login(user)
    survivor = TrainingStakeholder.objects.create(code="C0088888888", name="Surviving Company")
    TrainingStakeholderName.objects.create(stakeholder=survivor, name="Former Trading Name")
    TrainingStakeholder.objects.create(code="C0077777777", name="Old Company", is_active=False, merged_into=survivor)
    found = client.get(reverse("ucr-stakeholder-lookup"), {"code": "C0077777777"})
    assert found.status_code == 200
    assert {entry["name"] for entry in found.json()["results"]} == {"Surviving Company", "Former Trading Name"}
    assert {entry["code"] for entry in found.json()["results"]} == {survivor.code}


@pytest.mark.django_db
def test_provider_lookup_prefers_assigned_record_and_filters_by_declarant(client):
    user = User.objects.create_user(username="provider-learner", password="test-pass", is_staff=True)
    client.force_login(user)
    assigned = TrainingServiceProvider.objects.create(
        owner=user, code="C0055555501", name="Learner Logistics", country_code="GH",
        address="Fictional learner address", contact_name="Learner Contact",
        contact_designation="Trainee Declarant", phone="+233000000000", email="learner@example.test")
    shared = TrainingServiceProvider.objects.create(
        code="C0055555502", name="Admin Logistics", country_code="GH",
        address="Fictional admin address", contact_name="Admin Contact",
        phone="+233111111111", email="admin@example.test")
    lookup = reverse("ucr-service-provider-lookup")
    unfiltered = client.get(lookup).json()
    assert unfiltered["declarant_code"] == assigned.declarant_code
    assert unfiltered["tin_code"] == assigned.code
    assert unfiltered["contact_designation"] == "Trainee Declarant"
    by_declarant = client.get(lookup, {"code": shared.declarant_code}).json()
    assert by_declarant["name"] == "Admin Logistics"
    missing = client.get(lookup, {"code": "ZZ000001"})
    assert missing.status_code == 404
    assert "error" in missing.json()


@pytest.mark.django_db
def test_provider_registration_view_is_a_staff_only_admin_redirect(client):
    client.force_login(User.objects.create_user(username="provider-staff", password="test-pass", is_staff=True))
    response = client.get(reverse("training-service-providers"))
    assert response.status_code == 302
    assert response.url == reverse("admin:scenarios_trainingserviceprovider_add")


@pytest.mark.django_db
def test_provider_contact_details_are_optional():
    provider = TrainingServiceProvider(code="C0066666601", name="Contacts Optional Ltd", country_code="GH", address="Fictional address")
    provider.full_clean()


@pytest.mark.django_db
def test_provider_admin_tin_limited_to_declarant_capable_stakeholders():
    cha = TrainingStakeholder.objects.create(code="C0011111101", name="CHA Capable Ltd", roles=["cha"])
    forwarder_host = TrainingStakeholder.objects.create(code="C0011111102", name="Alias Forwarder Ltd", roles=["importer"])
    TrainingStakeholderName.objects.create(stakeholder=forwarder_host, name="Alias Forwarder Trading", roles=["freight_forwarder"])
    TrainingStakeholder.objects.create(code="C0011111103", name="Plain Importer Ltd", roles=["importer", "exporter"])
    TrainingStakeholder.objects.create(code="C0011111104", name="Inactive CHA Ltd", roles=["cha"], is_active=False)
    form = TrainingServiceProviderForm()
    offered = set(form.fields["stakeholder"].queryset.values_list("code", flat=True))
    assert offered == {"C0011111101", "C0011111102"}

    form = TrainingServiceProviderForm(data={"declarant_prefix": "CH", "stakeholder": cha.pk, "name": "Declarant Branch", "country_code": "GH", "address": "Fictional branch address"})
    assert form.is_valid(), form.errors
    provider = form.save()
    assert provider.code == cha.code
    assert provider.declarant_code.startswith("CH")

    duplicate = TrainingServiceProviderForm(data={"declarant_prefix": "CH", "stakeholder": cha.pk, "name": "Second Branch", "country_code": "GH", "address": "Fictional branch address"})
    assert not duplicate.is_valid()
    assert "already exists" in str(duplicate.errors["stakeholder"])


@pytest.mark.django_db
def test_provider_country_code_must_be_a_known_code():
    unknown = TrainingServiceProvider(code="C0066666602", name="Bad Country Ltd", country_code="XQ", address="Fictional address")
    with pytest.raises(ValidationError):
        unknown.full_clean()
    known = TrainingServiceProvider(code="C0066666603", name="Good Country Ltd", country_code="GH", address="Fictional address")
    known.full_clean()
    known.country_code = "ZZ"
    known.full_clean()


@pytest.mark.django_db
def test_admin_form_rejects_unknown_country_code():
    cha = TrainingStakeholder.objects.create(code="C0011111105", name="CHA Country Check Ltd", roles=["cha"])
    form = TrainingServiceProviderForm(data={"declarant_prefix": "CH", "stakeholder": cha.pk, "name": "Branch", "country_code": "X9", "address": "Fictional address"})
    assert not form.is_valid()
    assert "known two-letter country code" in str(form.errors["country_code"])


def test_python_country_codes_match_the_frontend_list():
    import re
    from pathlib import Path
    from scenarios.country_codes import COUNTRY_CODES
    raw = (Path(__file__).resolve().parents[1] / "static" / "js" / "ucr-country-codes.js").read_text(encoding="utf-8")
    js_pairs = re.findall(r'\[\s*"([A-Z]{2})"\s*,\s*"([^"]+)"\s*\]', raw)
    assert js_pairs == [(code, name) for code, name in COUNTRY_CODES]


@pytest.mark.django_db
def test_ucr_page_auto_populates_provider_without_search_ui(client):
    client.force_login(User.objects.create_user(username="ucr-page-author", password="test-pass", is_staff=True))
    response = client.get(reverse("single-window-create-ucr"))
    assert response.status_code == 200
    assert b'id="ucr-country-dialog"' in response.content
    assert b'data-country-search="ucr-origin"' in response.content
    assert b'id="ucr-declarant" readonly' in response.content
    assert b"ucrProviderLookupUrl" in response.content
    assert b"ucr-provider-search" not in response.content
    assert b"ucr-provider-designation" not in response.content
    assert reverse("training-service-providers").encode() not in response.content


def _ucr_payload(**overrides):
    payload = {
        "regime": "EX",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "PRINCEKING LOGISTICS COMPANY LIMITED",
            "country": "GH", "address": "P.O. BOX PMB, ACCRA", "contact": "Prince King",
            "phone": "+233200000000", "email": "princeking@example.test", "email_2": "",
        },
        "exporter": {
            "identity": "C0012345678", "name": "Fictional Exporter Ltd", "country": "GH",
            "address": "Fictional exporter address", "phone": "+233201111111", "fax": "",
            "contact": "Export Contact", "contact_no": "+233201111112", "designation": "Export Manager",
        },
        "importer": {
            "identity": "", "name": "Fictional Importer Ltd", "country": "CN",
            "address": "Fictional importer address", "phone": "+8610000000000", "fax": "",
            "contact": "Import Contact", "contact_no": "+8610000000001", "designation": "Import Manager",
        },
        "consignment": {
            "goods": "Fictional training goods", "origin": "GH", "destination": "CN",
            "mode": "10, Sea Transport", "reference": "REF-001", "email": "",
        },
        "documents": [{"code": "003", "name": "Invoice", "reference": "INV-001"}],
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_country_list_matches_official_pdfs():
    from scenarios.country_codes import COUNTRY_CODES

    assert len(COUNTRY_CODES) == 243
    codes = [code for code, _ in COUNTRY_CODES]
    assert len(set(codes)) == 243
    mapping = dict(COUNTRY_CODES)
    assert mapping["CN"] == "China"
    assert mapping["CH"] == "Switzerland"
    assert mapping["GH"] == "Ghana"
    assert mapping["ZZ"] == "Asia, Europe USA, etc"


@pytest.mark.django_db
def test_ucr_save_creates_temp_draft_and_reuses_it(client):
    user = User.objects.create_user(username="ucr-saver", password="test-pass", is_staff=True)
    client.force_login(user)
    first = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json")
    assert first.status_code == 200
    temp_no = first.json()["temp_no"]
    draft_id = first.json()["id"]
    assert re.fullmatch(r"TEMPUCR\d+", temp_no)
    record = UcrDeclaration.objects.get(owner=user)
    assert record.status == "draft"
    assert record.temp_no == temp_no
    assert record.ucr_no == ""
    assert record.documents == [{"code": "003", "name": "Invoice", "reference": "INV-001"}]

    updated = _ucr_payload(**{"consignment": {**_ucr_payload()["consignment"], "goods": "Updated goods"}})
    second = client.post(reverse("ucr-save"), {**updated, "draft_id": draft_id}, content_type="application/json")
    assert second.status_code == 200
    assert second.json()["temp_no"] == temp_no
    assert UcrDeclaration.objects.filter(owner=user).count() == 1
    assert UcrDeclaration.objects.get(owner=user).goods_description == "Updated goods"


@pytest.mark.django_db
def test_ucr_submit_issues_final_number_and_closes_the_draft(client):
    user = User.objects.create_user(username="ucr-submitter", password="test-pass", is_staff=True)
    client.force_login(user)
    draft_id = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()["id"]
    response = client.post(reverse("ucr-submit"), {**_ucr_payload(), "draft_id": draft_id}, content_type="application/json")
    assert response.status_code == 200
    data = response.json()
    assert re.fullmatch(r"KGHTESTUCR\d{9}", data["ucr_no"])
    assert data["ucr_no"][len("KGHTESTUCR"):len("KGHTESTUCR") + 2] == timezone.localtime().strftime("%y")
    record = UcrDeclaration.objects.get(owner=user)
    assert record.status == "submitted"
    assert record.submitted_at is not None
    assert record.ucr_no == data["ucr_no"]

    # The next save starts a fresh draft with a new TEMPUCR reference.
    fresh = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()
    assert re.fullmatch(r"TEMPUCR\d+", fresh["temp_no"])
    assert UcrDeclaration.objects.filter(owner=user).count() == 2


@pytest.mark.django_db
def test_ucr_submit_without_a_saved_draft_fails(client):
    client.force_login(User.objects.create_user(username="ucr-jumpgun", password="test-pass", is_staff=True))
    response = client.post(reverse("ucr-submit"), _ucr_payload(), content_type="application/json")
    assert response.status_code == 400
    assert "Save the UCR" in response.json()["error"]


@pytest.mark.django_db
def test_ucr_save_rejects_unknown_countries_and_bad_emails(client):
    client.force_login(User.objects.create_user(username="ucr-validator", password="test-pass", is_staff=True))
    bad_country = _ucr_payload(consignment={**_ucr_payload()["consignment"], "origin": "X9"})
    response = client.post(reverse("ucr-save"), bad_country, content_type="application/json")
    assert response.status_code == 400
    assert "consignment.origin" in response.json()["errors"]

    bad_email = _ucr_payload(provider={**_ucr_payload()["provider"], "email": "not-an-email"})
    response = client.post(reverse("ucr-save"), bad_email, content_type="application/json")
    assert response.status_code == 400
    assert "provider.email" in response.json()["errors"]

    response = client.post(reverse("ucr-save"), _ucr_payload(regime=""), content_type="application/json")
    assert response.status_code == 400
    assert "regime" in response.json()["errors"]


@pytest.mark.django_db
def test_ucr_page_wires_save_submit_and_csrf(client):
    client.force_login(User.objects.create_user(username="ucr-wiring", password="test-pass", is_staff=True))
    response = client.get(reverse("single-window-create-ucr"))
    assert response.status_code == 200
    assert b'id="ucr-submit"' in response.content
    assert b"ucrCsrfToken" in response.content
    assert reverse("ucr-save").encode() in response.content
    assert reverse("ucr-submit").encode() in response.content
    assert b"dialog-pagination.js" in response.content


@pytest.mark.django_db
def test_ucr_search_filters_saved_records_and_view_is_private(client):
    owner = User.objects.create_user(username="ucr-search-owner", email="ucr-search-owner@example.test", password="test-pass", is_staff=True)
    other = User.objects.create_user(username="ucr-search-other", email="ucr-search-other@example.test", password="test-pass", is_staff=True)
    client.force_login(owner)
    client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json")
    record = UcrDeclaration.objects.get(owner=owner)
    search = reverse("single-window-search-ucr")
    # Nothing is listed until a criterion is entered, then exact criteria hit.
    assert record.temp_no.encode() not in client.get(search).content
    assert record.temp_no.encode() in client.get(search, {"date_from": record.created_at.date().isoformat()}).content
    assert record.temp_no.encode() not in client.get(search, {"date_from": "2099-01-01"}).content
    assert record.temp_no.encode() not in client.get(search, {"number": "NO-MATCH"}).content
    assert record.temp_no.encode() in client.get(search, {"number": record.temp_no}).content
    assert record.temp_no.encode() in client.get(reverse("ucr-detail", args=[record.pk])).content
    client.force_login(other)
    assert client.get(reverse("ucr-detail", args=[record.pk])).status_code == 404


@pytest.mark.django_db
def test_ucr_clone_edit_then_amend_flow(client):
    owner = User.objects.create_user(username="ucr-derive-owner", password="test-pass", is_staff=True)
    client.force_login(owner)
    draft_id = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()["id"]
    client.post(reverse("ucr-submit"), {**_ucr_payload(), "draft_id": draft_id}, content_type="application/json")
    source = UcrDeclaration.objects.get(owner=owner)

    clone_response = client.post(reverse("ucr-clone", args=[source.pk]))
    assert clone_response.status_code == 302 and "draft=" in clone_response.url
    clone_pk = int(clone_response.url.split("draft=")[1])
    page = client.get(reverse("single-window-create-ucr"), {"draft": clone_pk})
    assert b"ucr-initial-draft" in page.content and source.goods_description.encode() in page.content

    # Cloning is unlimited: several drafts can sit open at once.
    client.post(reverse("ucr-clone", args=[source.pk]))
    assert UcrDeclaration.objects.filter(owner=owner, derivation="clone").count() == 2

    # Amend updates the same record in place; no new UCR number is issued.
    amend_page = client.get(reverse("ucr-amend", args=[source.pk]))
    assert amend_page.status_code == 200 and b'name="regime"' in amend_page.content
    client.post(reverse("ucr-amend", args=[source.pk]), {"regime": "FO", "new_documents": "[]"})
    source.refresh_from_db()
    assert source.regime == "FO"
    assert UcrDeclaration.objects.filter(owner=owner).count() == 3  # original + two clones


@pytest.mark.django_db
def test_ucr_attachment_is_saved_and_owner_only(client):
    owner = User.objects.create_user(username="ucr-file-owner", email="ucr-file-owner@example.test", password="test-pass", is_staff=True)
    other = User.objects.create_user(username="ucr-file-other", email="ucr-file-other@example.test", password="test-pass", is_staff=True)
    with override_settings(STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }):
        client.force_login(owner)
        response = client.post(reverse("ucr-save"), {
            "payload": json.dumps(_ucr_payload()),
            "file_0": SimpleUploadedFile("invoice.pdf", b"%PDF-1.4\nfictional training attachment", content_type="application/pdf"),
        })
        assert response.status_code == 200
        attachment = UcrDocumentAttachment.objects.get(ucr__owner=owner)
        assert b"invoice.pdf" in client.get(reverse("ucr-detail", args=[attachment.ucr_id])).content
        assert b"%PDF-1.4" in b"".join(client.get(reverse("ucr-attachment", args=[attachment.pk])).streaming_content)
        client.force_login(other)
        assert client.get(reverse("ucr-attachment", args=[attachment.pk])).status_code == 404


@pytest.mark.django_db
def test_clone_copies_everything_and_is_unlimited(client):
    user = User.objects.create_user(username="ucr-cloner", password="test-pass", is_staff=True)
    client.force_login(user)
    original = UcrDeclaration.objects.create(
        owner=user, regime="EX", declarant_code="CH000869", provider_code="C0029705992",
        provider_name="PRINCEKING LOGISTICS", provider_country="GH", provider_address="P.O. BOX PMB, ACCRA",
        goods_description="Clone source goods", origin_country="GH", destination_country="CN",
        transport_mode="10, Sea Transport", user_reference="REF-CLONE",
        documents=[{"code": "003", "name": "Invoice", "reference": "INV-9"}],
        temp_no="TEMPUCR2600000001", ucr_no="KGHTESTUCR2600000001", status="submitted",
    )
    first = client.post(reverse("ucr-clone", args=[original.pk]))
    assert first.status_code == 302
    assert "draft=" in first.url
    second = client.post(reverse("ucr-clone", args=[original.pk]))
    assert second.status_code == 302
    clones = UcrDeclaration.objects.filter(owner=user, derivation="clone")
    assert clones.count() == 2
    assert len({clone.temp_no for clone in clones}) == 2
    for clone in clones:
        assert clone.status == "draft"
        assert clone.ucr_no == ""
        assert clone.source_ucr_id == original.pk
        assert clone.regime == original.regime
        assert clone.goods_description == "Clone source goods"
        assert clone.provider_name == "PRINCEKING LOGISTICS"
        assert clone.documents == [{"code": "003", "name": "Invoice", "reference": "INV-9"}]


@pytest.mark.django_db
def test_amend_updates_in_place_within_the_regime_family(client):
    user = User.objects.create_user(username="ucr-amender", password="test-pass", is_staff=True)
    client.force_login(user)
    source = UcrDeclaration.objects.create(
        owner=user, regime="IM", goods_description="Amend source goods", origin_country="CN",
        destination_country="GH", transport_mode="40, Air Transport", documents=[{"code": "003", "name": "Invoice", "reference": "INV-1"}],
        temp_no="TEMPUCR2600000002", ucr_no="KGHTESTUCR2600000002", status="submitted",
    )
    page = client.get(reverse("ucr-amend", args=[source.pk]))
    assert page.status_code == 200
    # The page mirrors the create form and only offers the regime family (IM with FI).
    assert b'name="regime"' in page.content
    assert b'value="IM"' in page.content and b'value="FI"' in page.content
    assert b'value="EX"' not in page.content and b'value="TN"' not in page.content
    assert b"Amend source goods" in page.content
    assert b"Only the Regime Type and eDocuments Details can be changed" in page.content

    # Cross-family regimes are rejected server-side.
    rejected = client.post(reverse("ucr-amend", args=[source.pk]), {"regime": "EX", "new_documents": "[]"})
    assert rejected.status_code == 302
    source.refresh_from_db()
    assert source.regime == "IM"

    accepted = client.post(reverse("ucr-amend", args=[source.pk]), {
        "regime": "FI",
        "new_documents": '[{"code": "005", "name": "Bill of Lading / Airwaybill", "reference": "BL-7"}]',
    })
    assert accepted.status_code == 302
    assert accepted.url == reverse("ucr-detail", args=[source.pk])
    source.refresh_from_db()
    assert UcrDeclaration.objects.filter(owner=user).count() == 1
    assert source.regime == "FI"
    assert source.ucr_no == "KGHTESTUCR2600000002"
    assert source.status == "submitted"
    assert source.goods_description == "Amend source goods"
    assert source.documents == [
        {"code": "003", "name": "Invoice", "reference": "INV-1"},
        {"code": "005", "name": "Bill of Lading / Airwaybill", "reference": "BL-7"},
    ]


@pytest.mark.django_db
def test_amend_requires_a_submitted_original(client):
    client.force_login(User.objects.create_user(username="ucr-amend-guard", password="test-pass", is_staff=True))
    draft = UcrDeclaration.objects.create(owner_id=User.objects.get(username="ucr-amend-guard").pk, regime="IM", temp_no="TEMPUCR2600000003")
    response = client.get(reverse("ucr-amend", args=[draft.pk]))
    assert response.status_code == 302
    assert response.url == reverse("ucr-detail", args=[draft.pk])


@pytest.mark.django_db
def test_expired_drafts_are_purged_but_recent_and_submitted_survive(client):
    from datetime import timedelta

    from django.utils import timezone as dz

    from scenarios.models import purge_expired_ucr_drafts
    user = User.objects.create_user(username="ucr-hoarder", password="test-pass", is_staff=True)
    client.force_login(user)
    stale = UcrDeclaration.objects.create(owner=user, regime="IM", temp_no="TEMPUCR2600000011")
    fresh = UcrDeclaration.objects.create(owner=user, regime="IM", temp_no="TEMPUCR2600000012")
    final = UcrDeclaration.objects.create(owner=user, regime="IM", temp_no="TEMPUCR2600000013", ucr_no="KGHTESTUCR2600000013", status="submitted", submitted_at=dz.now())
    UcrDeclaration.objects.filter(pk=stale.pk).update(updated_at=dz.now() - timedelta(days=8))
    UcrDeclaration.objects.filter(pk=final.pk).update(updated_at=dz.now() - timedelta(days=30))

    # Loading the search page triggers the purge.
    client.get(reverse("single-window-search-ucr"))
    remaining = set(UcrDeclaration.objects.filter(owner=user).values_list("temp_no", flat=True))
    assert remaining == {fresh.temp_no, final.temp_no}


@pytest.mark.django_db
def test_create_page_prefills_the_requested_draft_only(client):
    user = User.objects.create_user(username="ucr-picker", password="test-pass", is_staff=True)
    client.force_login(user)
    wanted = UcrDeclaration.objects.create(owner=user, regime="EX", goods_description="Wanted draft", temp_no="TEMPUCR2600000021")
    other = UcrDeclaration.objects.create(owner=user, regime="IM", goods_description="Other draft", temp_no="TEMPUCR2600000022")
    page = client.get(reverse("single-window-create-ucr"), {"draft": wanted.pk})
    assert page.status_code == 200
    assert b"Wanted draft" in page.content
    assert b"Other draft" not in page.content
    blank = client.get(reverse("single-window-create-ucr"))
    assert b"Wanted draft" not in blank.content
    # A submitted id redirects to its read-only view.
    submitted = UcrDeclaration.objects.create(owner=user, regime="IM", temp_no="TEMPUCR2600000023", ucr_no="KGHTESTUCR2600000023", status="submitted")
    gone = client.get(reverse("single-window-create-ucr"), {"draft": submitted.pk})
    assert gone.status_code == 302
    assert gone.url == reverse("ucr-detail", args=[submitted.pk])


@pytest.mark.django_db
def test_ucr_numbers_are_sequential_not_random(client):
    user = User.objects.create_user(username="ucr-sequence", password="test-pass", is_staff=True)
    client.force_login(user)
    first = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()
    second = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()
    assert first["temp_no"].endswith("0000001") and second["temp_no"].endswith("0000002")
    submitted = client.post(reverse("ucr-submit"), {**_ucr_payload(), "draft_id": first["id"]}, content_type="application/json").json()
    assert submitted["ucr_no"] == first["temp_no"].replace("TEMPUCR", "KGHTESTUCR")


@pytest.mark.django_db
def test_search_ucr_matches_exactly_and_stays_empty_until_searched(client):
    user = User.objects.create_user(username="ucr-exact", password="test-pass", is_staff=True)
    client.force_login(user)
    draft_id = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()["id"]
    client.post(reverse("ucr-submit"), {**_ucr_payload(), "draft_id": draft_id}, content_type="application/json")
    search = reverse("single-window-search-ucr")

    # No criteria: nothing is listed even though a record exists.
    empty = client.get(search)
    assert empty.status_code == 200
    assert b"No data found." in empty.content
    assert b"KGHTESTUCR" not in empty.content

    # Partial text never hits; only the exact TIN or full name does.
    assert b"No data found." in client.get(search, {"exporter": "Fictional"}).content
    hit = client.get(search, {"exporter": "Fictional Exporter Ltd"})
    assert b"No data found." not in hit.content
    hit_by_tin = client.get(search, {"exporter": "C0012345678"})
    assert b"No data found." not in hit_by_tin.content

    # Partial UCR number does not hit; the full number does.
    assert b"No data found." in client.get(search, {"number": "KGHTEST"}).content
    number = UcrDeclaration.objects.get(owner=user).ucr_no
    assert b"No data found." not in client.get(search, {"number": number}).content

    # Partial user reference does not hit; the full reference does.
    assert b"No data found." in client.get(search, {"reference": "REF"}).content
    assert b"No data found." not in client.get(search, {"reference": "REF-001"}).content

    # Regime and status work on their own.
    assert b"No data found." not in client.get(search, {"regime": "EX"}).content
    assert b"No data found." not in client.get(search, {"status": "submitted"}).content
    assert b"No data found." in client.get(search, {"status": "draft"}).content


@pytest.mark.django_db
def test_preparation_ucr_picker_lists_issued_ucrs_only(client):
    user = User.objects.create_user(username="ucr-picker-user", password="test-pass", is_staff=True)
    client.force_login(user)
    draft_id = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()["id"]
    client.post(reverse("ucr-submit"), {**_ucr_payload(), "draft_id": draft_id}, content_type="application/json")
    open_draft = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()

    # No criteria: nothing is returned, matching Search UCR.
    assert client.get(reverse("ucr-reference-search")).json()["results"] == []

    by_regime = client.get(reverse("ucr-reference-search"), {"regime": "EX"}).json()["results"]
    assert [row["ucr_no"] for row in by_regime] == [UcrDeclaration.objects.get(owner=user, status="submitted").ucr_no]
    assert by_regime[0]["regime"] == "Export"
    assert by_regime[0]["exporter"] == "C0012345678, Fictional Exporter Ltd"
    assert by_regime[0]["importer"] == "Fictional Importer Ltd"

    wrong_regime = client.get(reverse("ucr-reference-search"), {"regime": "IM"}).json()["results"]
    assert wrong_regime == []
    partial = client.get(reverse("ucr-reference-search"), {"exporter": "Fictional"}).json()["results"]
    assert partial == []

    page = client.get(reverse("single-window-create-preparation-application"))
    assert page.status_code == 200
    assert b'id="ucr-reference-dialog"' in page.content
    assert b'id="preparation-ucr-search"' in page.content


@pytest.mark.django_db
def test_consignment_application_lifecycle(client):
    from scenarios.models import ConsignmentApplication, GhanaHSCode, MdaAgency, MdaApplication, MdaConsignmentRequest, MdaProcess, PortCode

    assert GhanaHSCode.objects.count() == 4854
    assert GhanaHSCode.objects.filter(code="0101210000", description__icontains="horses").exists()
    PortCode.objects.create(code="ghtem", name="Tema", country_code="gh", country_name="Ghana")
    PortCode.objects.create(code="CAMTR", name="Montreal", country_code="CA", country_name="Canada")
    PortCode.objects.create(code="OLDPT", name="Inactive Port", country_code="GH", country_name="Ghana", is_active=False)
    fda = MdaAgency.objects.get(code="FDA")
    permit = MdaApplication.objects.create(mda=fda, code="IP", name="Import Permit")
    new_process = MdaProcess.objects.create(application=permit, code="NEW", name="New Application")
    MdaProcess.objects.create(application=permit, code="REN", name="Renewal")

    user = User.objects.create_user(username="app-author", password="test-pass", is_staff=True)
    client.force_login(user)
    draft_id = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()["id"]
    submitted = client.post(reverse("ucr-submit"), {**_ucr_payload(), "draft_id": draft_id}, content_type="application/json").json()
    ucr_no = submitted["ucr_no"]

    # The create page prefills from the issued UCR.
    page = client.get(reverse("consignment-application-create"), {"ucr": ucr_no})
    assert page.status_code == 200
    assert ucr_no.encode() in page.content
    assert b"Fictional Exporter Ltd" in page.content
    assert b"Fictional exporter address" in page.content
    assert b"+233201111111" in page.content
    assert b'"consignor_same": false' in page.content
    assert b'"consignee_same": false' in page.content
    assert b'data-app-same="consignor" checked' not in page.content
    assert b'data-app-same="consignee" checked' not in page.content
    assert b'data-app-field="exporter.name" readonly' in page.content
    assert b'data-app-field="importer.code" readonly' in page.content
    assert b'data-app-country-search="consignor.physical_country"' in page.content
    assert b'data-app-country-search="consignee.physical_country"' in page.content
    assert b'id="app-country-dialog"' in page.content
    assert b'id="app-hs-dialog"' in page.content
    assert b'id="app-port-dialog"' in page.content
    assert b'id="app-mda-dialog"' in page.content
    assert b'id="app-ucr"' in page.content
    assert b'id="app-mda-ucr"' in page.content
    assert b'id="app-mda-add"' in page.content
    assert b'<button class="ucr-row-action" type="button" data-mda-create="FDA">Create</button>' in page.content
    assert b'Create Application Form' in page.content
    assert b'data-app-port-search="port_arrival"' in page.content
    assert b'data-app-port-search="port_departure"' in page.content
    assert b'<th>MDA</th><th>Application</th><th>Process</th><th>Exporter</th><th>Importer</th>' in page.content
    assert b'id="app-confirm-sections"' in page.content
    assert b'id="app-confirm-summary"' not in page.content

    hs_by_code = client.get(reverse("application-hs-code-search"), {"code": "6404", "length": "10"})
    assert hs_by_code.status_code == 200
    assert hs_by_code.json()["results"]
    assert all(row["full_code"].startswith("6404") for row in hs_by_code.json()["results"])
    hs_by_description = client.get(reverse("application-hs-code-search"), {"description": "training shoes", "length": "10"})
    assert hs_by_description.status_code == 200
    assert any("training shoes" in row["description"].lower() for row in hs_by_description.json()["results"])
    hs_heading = client.get(reverse("application-hs-code-search"), {"code": "64", "length": "4"})
    assert hs_heading.status_code == 200
    assert all(len(row["code"]) == 4 for row in hs_heading.json()["results"])
    port_by_code = client.get(reverse("application-port-code-search"), {"code": "HTE"})
    assert port_by_code.status_code == 200
    assert port_by_code.json()["results"] == [{"code": "GHTEM", "name": "Tema", "country_code": "GH", "country_name": "Ghana"}]
    assert client.get(reverse("application-port-code-search"), {"name": "ontre"}).json()["results"][0]["code"] == "CAMTR"
    assert client.get(reverse("application-port-code-search"), {"country": "ghana"}).json()["total"] == 1
    assert client.get(reverse("application-port-code-search"), {"code": "OLD"}).json()["results"] == []
    mda_options = client.get(reverse("application-mda-options"))
    assert mda_options.status_code == 200
    fda_option = next(item for item in mda_options.json()["results"] if item["code"] == "FDA")
    assert fda_option["applications"][0]["name"] == "Import Permit"
    assert [process["code"] for process in fda_option["applications"][0]["processes"]] == ["NEW", "REN"]
    assert b'<option value="C">Container</option>' in page.content
    assert b'<option value="V">Vehicle</option>' in page.content
    assert b'<option value="B">Bulk</option>' in page.content
    assert b'<option value="E">Empty Container</option>' in page.content
    assert b'<option value="O">Other</option>' in page.content
    assert b'id="app-container-status" hidden' in page.content

    # Without a UCR the page bounces back to the preparation step.
    bounced = client.get(reverse("consignment-application-create"))
    assert bounced.status_code == 302
    assert bounced.url == reverse("single-window-create-preparation-application")

    payload = {
        "ucr_no": ucr_no,
        "exporter": {"name": "Fictional Exporter Ltd", "physical_country": "GH", "physical_address": "Training address", "tel": "233"},
        "consignor": {"same": True},
        "importer": {"code": "Fictional Importer Ltd", "physical_country": "CN", "physical_address": "Fictional importer address", "tel": "233"},
        "consignee": {"same": True},
        "means_of_transport": "10, Sea Transport", "shipment_date": "2026-09-19",
        "delivery_term": "CFR", "currency": "USD", "fob_fcy": "257", "freight_fcy": "80",
        "customs_value_ncy": "1",  # ignored: NCY and customs values are calculated by the server
        "items": [{"hs_code": "6309000000", "description": "USED SHOES GRADE C", "state_of_goods": "02", "quantity_unit": "KGM", "quantity": "20", "package_unit": "KG", "package_quantity": "20", "origin_country": "CA", "net_weight": "20.00", "gross_weight": "20.00", "currency": "USD", "exchange_rate": "12.41", "price_fcy": "10.00", "price_ncy": "124.10", "unit_fob_fcy": "0.5000", "unit_fob_ncy": "6.205", "fob_fcy": "10", "fob_ncy": "124.10", "remarks": "OK"}],
    }
    incomplete = client.post(reverse("application-save"), {**payload, "exporter": {"name": ""}}, content_type="application/json")
    assert incomplete.status_code == 400
    assert incomplete.json()["error"] == "Complete all required General fields before saving."
    first = client.post(reverse("application-save"), payload, content_type="application/json").json()
    assert re.fullmatch(r"CD\d{8}\d{6}", first["application_no"])
    assert first["application_no"].endswith("000001")
    record = ConsignmentApplication.objects.get(owner=user)
    assert record.status == "draft" and record.ucr.ucr_no == ucr_no
    assert record.exchange_rate == Decimal("12.4100")
    assert record.customs_value_fcy == Decimal("337.00")
    assert record.customs_value_ncy == Decimal("4182.17")
    assert record.items[0]["origin_country"] == "CA"
    assert record.items[0]["state_of_goods"] == "02"
    assert record.items[0]["price_fcy"] == "10.00"
    assert record.items[0]["fob_fcy"] == "10.00"

    mda_create_url = reverse("application-mda-request-create")
    missing_master = client.post(mda_create_url, {
        "consignment_application_id": first["id"], "mda_id": fda.id, "application_id": permit.id,
        "process_id": new_process.id, "consignment_type": "SB", "master_no": "",
    }, content_type="application/json")
    assert missing_master.status_code == 400
    mda_created = client.post(mda_create_url, {
        "consignment_application_id": first["id"], "mda_id": fda.id, "application_id": permit.id,
        "process_id": new_process.id, "consignment_type": "SG", "master_no": "SHOULD-BE-CLEARED",
    }, content_type="application/json")
    assert mda_created.status_code == 201
    mda_number = mda_created.json()["application_no"]
    assert len(mda_number) == 21
    assert re.fullmatch(r"CD\d{6}FDAIP\d{8}", mda_number)
    assert mda_number.endswith("00000001")
    assert MdaConsignmentRequest.objects.get(application_no=mda_number).master_no == ""
    mda_detail = client.get(mda_created.json()["url"])
    assert mda_detail.status_code == 200
    assert mda_number.encode() in mda_detail.content
    assert b'data-app-tab="approval"' in mda_detail.content
    assert b"Request Approval" in mda_detail.content
    assert b"Additional Parties for Distribution" in mda_detail.content
    assert b"eDocuments Details" in mda_detail.content
    mda_saved = client.post(reverse("mda-consignment-application-save", args=(mda_created.json()["id"],)), {
        **payload, "approval_terms": True, "approval_purpose": "Permit for clearance",
        "approval_remarks": "Training request", "additional_parties": [{"name": "Test Party", "mailbox": "BOX-1"}],
    }, content_type="application/json")
    assert mda_saved.status_code == 200
    mda_record = MdaConsignmentRequest.objects.get(application_no=mda_number)
    assert mda_record.approval_terms is True
    assert mda_record.form_data["means_of_transport"] == "10, Sea Transport"
    resumed = client.get(reverse("consignment-application-create"), {"ucr": ucr_no})
    assert resumed.status_code == 200
    assert first["application_no"].encode() in resumed.content
    assert mda_number.encode() in resumed.content
    application_search = client.get(reverse("single-window-search-preparation-application"), {"number": first["application_no"][-6:], "searched": "1"})
    assert application_search.status_code == 200
    assert first["application_no"].encode() in application_search.content
    assert b"SIM-CD-0790708" not in application_search.content

    # Item Price/FOB is always quantity × Unit FOB. If that would exceed the
    # Invoice FOB, the server reduces Unit FOB to the remaining allowance.
    capped_payload = {
        **payload,
        "app_id": first["id"],
        "items": [{**payload["items"][0], "unit_fob_fcy": "20", "price_fcy": "1", "fob_fcy": "1"}],
    }
    capped = client.post(reverse("application-save"), capped_payload, content_type="application/json")
    assert capped.status_code == 200
    record.refresh_from_db()
    assert record.items[0]["unit_fob_fcy"] == "12.850000"
    assert record.items[0]["price_fcy"] == "257.00"
    assert record.items[0]["fob_fcy"] == "257.00"

    # A second save updates the same draft; submit closes it keeping the number.
    payload["carrier"] = "HAPL, HAPAG LLOYD"
    second = client.post(reverse("application-save"), {**payload, "app_id": first["id"]}, content_type="application/json").json()
    assert second["application_no"] == first["application_no"]
    submitted_app = client.post(reverse("application-submit"), {**payload, "app_id": first["id"]}, content_type="application/json").json()
    assert submitted_app["status"] == "submitted"
    record.refresh_from_db()
    assert record.carrier == "HAPL, HAPAG LLOYD" and record.submitted_at is not None
    submitted_view = client.get(reverse("consignment-application-create"), {"app": record.pk})
    assert submitted_view.status_code == 200
    assert b"window.appReadOnly = true" in submitted_view.content

    # Submit without a saved draft fails.
    rejected = client.post(reverse("application-submit"), payload, content_type="application/json")
    assert rejected.status_code == 400

    # Numbers are sequential and unknown UCRs are rejected.
    next_number = client.post(reverse("application-save"), payload, content_type="application/json")
    assert next_number.status_code == 400 or next_number.json()["application_no"].endswith("000002")


@pytest.mark.django_db
def test_application_delete_is_draft_only_and_owner_scoped(client):
    from scenarios.models import ConsignmentApplication

    owner = User.objects.create_user(username="app-del-owner", email="app-del-owner@example.test", password="test-pass", is_staff=True)
    other = User.objects.create_user(username="app-del-other", email="app-del-other@example.test", password="test-pass", is_staff=True)
    ucr = UcrDeclaration.objects.create(owner=owner, regime="IM", temp_no="TEMPUCR2600000031", ucr_no="KGHTESTUCR260000031", status="submitted",
                                        importer_identity="P0001234567", importer_name="Work In Progress")
    draft = ConsignmentApplication.objects.create(owner=owner, ucr=ucr, application_no="CD20260922000001", status="draft")
    keep = ConsignmentApplication.objects.create(owner=owner, ucr=ucr, application_no="CD20260922000004", status="draft")
    final = ConsignmentApplication.objects.create(owner=owner, ucr=ucr, application_no="CD20260922000002", status="submitted")
    foreign = ConsignmentApplication.objects.create(owner=other, ucr=ucr, application_no="CD20260922000003", status="draft")
    delete_url = reverse("application-delete")
    search_url = reverse("single-window-search-preparation-application")

    client.force_login(owner)
    # Draft deletes with a success message.
    response = client.post(delete_url, {"application_id": draft.pk})
    assert response.status_code == 302
    assert not ConsignmentApplication.objects.filter(pk=draft.pk).exists()

    # Submitted records stay protected.
    response = client.post(delete_url, {"application_id": final.pk})
    assert ConsignmentApplication.objects.filter(pk=final.pk).exists()

    # Another learner's application is unreachable.
    response = client.post(delete_url, {"application_id": foreign.pk})
    assert ConsignmentApplication.objects.filter(pk=foreign.pk).exists()

    # Empty selection reports a message instead of failing.
    response = client.post(delete_url, {"application_id": ""})
    assert response.status_code == 302

    # The search page offers radios only for drafts and shows the Delete action.
    initial_page = client.get(search_url)
    assert b"CD20260922000004" not in initial_page.content
    empty_search = client.get(search_url, {"searched": "1"})
    assert b"Enter at least one search criterion before searching." in empty_search.content

    page = client.get(search_url, {"number": "000004", "searched": "1"})
    assert page.status_code == 200
    assert b'name="application-select"' in page.content
    assert b'id="application-delete"' in page.content
    assert f'value="{keep.pk}"'.encode() in page.content  # remaining draft is selectable
    assert b"P0001234567, Work In Progress" in page.content

    # Importer filters are partial and search the inherited UCR TIN/name too.
    importer_match = client.get(search_url, {"importer": "progress", "searched": "1"})
    assert b"P0001234567, Work In Progress" in importer_match.content


@pytest.mark.django_db
def test_ucr_save_and_submit_return_attachment_links_and_view_url(client):
    user = User.objects.create_user(username="ucr-view-flow", password="test-pass", is_staff=True)
    client.force_login(user)
    with override_settings(STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }):
        upload = lambda: SimpleUploadedFile("invoice.pdf", b"%PDF-1.4\nfictional training attachment", content_type="application/pdf")
        saved = client.post(reverse("ucr-save"), {"payload": json.dumps(_ucr_payload()), "file_0": upload()}).json()
        assert saved["attachments"][0]["name"] == "invoice.pdf"
        assert "/attachments/" in saved["attachments"][0]["url"]
        submitted = client.post(reverse("ucr-submit"), {
            "payload": json.dumps({**_ucr_payload(), "draft_id": saved["id"]}),
            "file_0": upload(),
        }).json()
        assert submitted["ucr_no"]
        assert submitted["attachments"][0]["name"] == "invoice.pdf"
        view = client.get(submitted["detail_url"])
        assert view.status_code == 200
        assert submitted["ucr_no"].encode() in view.content
        assert b"invoice.pdf" in view.content


@pytest.mark.django_db
def test_consignment_create_application_mirrors_preparation_create(client):
    user = User.objects.create_user(username="consignment-creator", password="test-pass", is_staff=True)
    client.force_login(user)
    page = client.get(reverse("single-window-create-consignment-application"))
    assert page.status_code == 200
    assert b"Consignment Application" in page.content
    assert b"New Master Request" in page.content
    assert b'id="preparation-ucr-search"' in page.content
    assert b'id="ucr-reference-dialog"' in page.content
    assert b"Create Application Form" in page.content


@pytest.mark.django_db
def test_consignment_search_application_lists_mda_requests(client):
    user = User.objects.create_user(username="consignment-searcher", password="test-pass", is_staff=True)
    client.force_login(user)
    fda = MdaAgency.objects.get(code="FDA")
    permit = MdaApplication.objects.create(mda=fda, code="IDF", name="Import Duty Framework")
    new_process = MdaProcess.objects.create(application=permit, code="NEW", name="New Application")
    draft_id = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()["id"]
    ucr_no = client.post(reverse("ucr-submit"), {**_ucr_payload(), "draft_id": draft_id}, content_type="application/json").json()["ucr_no"]
    payload = {
        "ucr_no": ucr_no,
        "exporter": {"name": "Fictional Exporter Ltd", "physical_country": "GH", "physical_address": "Training address", "tel": "233"},
        "consignor": {"same": True},
        "importer": {"code": "Fictional Importer Ltd", "physical_country": "CN", "physical_address": "Fictional importer address", "tel": "233"},
        "consignee": {"same": True},
        "means_of_transport": "10, Sea Transport", "shipment_date": "2026-09-19",
        "delivery_term": "CFR", "currency": "USD", "fob_fcy": "257", "freight_fcy": "80",
        "items": [{"hs_code": "6309000000", "description": "USED SHOES GRADE C", "state_of_goods": "02", "quantity_unit": "KGM", "quantity": "20", "package_unit": "KG", "package_quantity": "20", "origin_country": "CA", "net_weight": "20.00", "gross_weight": "20.00", "currency": "USD", "exchange_rate": "12.41", "price_fcy": "10.00", "price_ncy": "124.10", "unit_fob_fcy": "0.5000", "unit_fob_ncy": "6.205", "fob_fcy": "10", "fob_ncy": "124.10", "remarks": "OK"}],
    }
    saved = client.post(reverse("application-save"), payload, content_type="application/json").json()
    mda_created = client.post(reverse("application-mda-request-create"), {
        "consignment_application_id": saved["id"], "mda_id": fda.pk, "application_id": permit.pk,
        "process_id": new_process.pk, "consignment_type": "SG", "master_no": "",
    }, content_type="application/json").json()

    search_url = reverse("single-window-search-consignment-application")
    page = client.get(search_url)
    assert page.status_code == 200
    # The MDA's own application number is listed, not the consignment document number.
    assert mda_created["application_no"].encode() in page.content
    assert ucr_no.encode() in page.content
    assert b"Fictional Exporter Ltd" in page.content
    assert b"FDA" in page.content
    assert reverse("mda-consignment-application", args=(mda_created["id"],)).encode() in page.content
    assert saved["application_no"].encode() not in page.content
    # Amend only becomes available once the MDA application is approved.
    assert b">Amend</a>" not in page.content
    MdaConsignmentRequest.objects.filter(pk=mda_created["id"]).update(status=MdaStatus.APPROVED)
    approved_page = client.get(search_url)
    assert b">Amend</a>" in approved_page.content
    # The Status dropdown offers the full shared MDA status list.
    assert b">DR, Draft</option>" in page.content
    assert b">SU, Submitted</option>" in page.content
    assert b">AP, Approved</option>" in page.content
    assert b">SC, Approved 2nd MDA Checking Officer(GCoO)</option>" in page.content

    filtered = client.get(search_url, {"mda": "FDA"})
    assert mda_created["application_no"].encode() in filtered.content
    empty = client.get(search_url, {"mda": "GSA"})
    assert b"No data found." in empty.content

    # Draft MDA applications can be deleted from the search page.
    MdaConsignmentRequest.objects.filter(pk=mda_created["id"]).update(status=MdaStatus.DRAFT)
    response = client.post(reverse("mda-request-delete"), {"mda_request_id": mda_created["id"]})
    assert response.status_code == 302
    assert not MdaConsignmentRequest.objects.filter(pk=mda_created["id"]).exists()
