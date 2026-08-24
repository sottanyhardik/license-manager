from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.allotment.models import AllotmentModel
from apps.allotment.services.paired_allocation_max import calculate_paired_allocation_max
from apps.core.models import NotificationNumber, PortModel, PurchaseStatus, SchemeCode
from apps.license.models import (
    LicenseDetailsModel, LicenseItemPlan, SionPlanningProfile, SionPlanningRule,
)


def test_seed_browser_2509_refuses_non_test_database():
    from apps.license.management.commands.seed_browser_2509 import Command

    with patch(
        "apps.license.management.commands.seed_browser_2509.connection",
        SimpleNamespace(settings_dict={"NAME": "lmanagement"}),
    ), pytest.raises(CommandError, match="only runs against a disposable database"):
        Command()._require_disposable_database()


@pytest.mark.django_db(transaction=True)
def test_seed_browser_2509_creates_idempotent_canonical_fixture(monkeypatch):
    monkeypatch.setenv("LM_USERNAME", "browser-gate")
    monkeypatch.setenv("LM_PASSWORD", "browser-gate-password")

    call_command("seed_browser_2509")
    call_command("seed_browser_2509")

    license_obj = LicenseDetailsModel.objects.get(pk=2509, license_number="3411008090")
    assert license_obj.planning_source_revision == license_obj.planning_applied_revision == 1
    assert license_obj.replan_requests.count() == 0
    assert license_obj.scheme_code == SchemeCode.objects.get(code="E2E2509")
    assert license_obj.notification_number == NotificationNumber.objects.get(code="2509")
    assert license_obj.port == PortModel.objects.get(code="E2E")
    assert PurchaseStatus.objects.filter(is_active=True).exists()
    plan = LicenseItemPlan.objects.get(license=license_obj, is_active=True)
    assert plan.planned_quantity == Decimal("234.000")
    assert plan.planned_cif_fc == Decimal("2064.12")
    assert plan.allocation_provenance["canonical_unit_price"] == "8.821"
    assert plan.planning_rule == SionPlanningRule.objects.get(stable_key="E2E2509:RULE:001")
    assert SionPlanningProfile.objects.get(stable_key="E2E2509:PROFILE").is_active

    allotment = AllotmentModel.objects.get(invoice="E2E-ALLOTMENT-2509")
    maximum = calculate_paired_allocation_max(
        quantity_ceiling=Decimal("500.000"), cif_ceiling=Decimal("2066.75"),
        unit_price=allotment.unit_value_per_unit, quantity_step=Decimal("1.000"),
    )
    assert maximum.quantity == Decimal("234.000")
    assert maximum.cif == Decimal("2064.12")
    user = get_user_model().objects.get(username="browser-gate")
    assert user.is_superuser and user.check_password("browser-gate-password")


@pytest.mark.django_db(transaction=True)
def test_seed_browser_2509_reports_conflicting_reference_data():
    SchemeCode.objects.create(code="E2E2509", label="conflicting scheme")

    with pytest.raises(CommandError, match="Conflicting scheme code"):
        call_command("seed_browser_2509")
