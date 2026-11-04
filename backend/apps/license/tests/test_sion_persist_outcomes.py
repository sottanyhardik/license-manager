"""
SION plan persistence outcomes (regression for KeyError: 'write_result').

Outcome taxonomy asserted here:
  * BLOCKED_OVER_UTILISED - budget gate fails closed before any write; the licence has a
    write_result with that status (no plan rows), is reported in ``licenses`` and
    ``over_utilised_count``, and is excluded from ``planned_licenses``.
  * SKIPPED_NO_MATCH      - persistence step ran, no persistable lines; reported in
    ``write_results`` with status SKIPPED_NO_MATCH and writes no plan rows.
  * PLANNED               - successful persistence; a write_result and LicenseItemPlan rows.
  * failure               - an exception during persistence propagates and the whole
    SION planning transaction is rolled back (no partial plan rows).
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import pytest

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
    SionPlanningRule,
)
from apps.license.services.canonical_planning_service import CanonicalPlanningService
from apps.license.services.sion_planning_execution import SionPlanningExecutionService

pytestmark = pytest.mark.django_db

MATCH_HS = "15079010"  # matched by the rule below
NO_MATCH_HS = "15119000"  # not matched by the rule


def _sion():
    head = HeadSIONNormsModel.objects.create(name="Persist outcomes")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="P1", is_active=True)
    SionPlanningRule.objects.create(
        sion=sion, name="Oil", unit="kg", max_unit_price=Decimal("5.00"), priority=1, is_active=True,
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "1507"},
    )
    return sion


def _hs(code):
    hs, _ = HSCodeModel.objects.get_or_create(
        hs_code=code,
        defaults={"product_description": "Oil " + code, "unit_price": Decimal("1.00"), "unit": "kg"},
    )
    return hs


def _licence(sion, index, *, hs_code=MATCH_HS, export_cif="1000.00", usage_cif=None):
    company = CompanyModel.objects.create(iec=f"PERSIST{index:03d}", name=f"Persist Co {index}")
    licence = LicenseDetailsModel.objects.create(
        license_number=f"PERSIST-LIC-{index}",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=90),
        exporter=company,
    )
    LicenseExportItemModel.objects.create(
        license=licence, description="Export P1", norm_class=sion, cif_fc=Decimal(export_cif),
    )
    item = LicenseImportItemsModel.objects.create(
        license=licence, serial_number=1, description="Oil", hs_code=_hs(hs_code),
        quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
        available_value=Decimal("100.00"), condition_type="",
    )
    if usage_cif is not None:
        usage = AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000.00"))
        AllotmentItems.objects.create(allotment=usage, item=item, qty=Decimal("10.000"), cif_fc=Decimal(usage_cif))
    return licence


def _plan_rows(licence):
    return LicenseItemPlan.objects.filter(license=licence).count()


def _persist(sion, licences):
    return SionPlanningExecutionService.plan_sion(
        sion, [lic.pk for lic in licences], persist=True, mode="ALL",
    )


def _row(result, licence):
    rows = [row for row in result["licenses"] if row["license_id"] == licence.pk]
    assert len(rows) == 1, result
    return rows[0]


def test_blocked_over_utilised_writes_nothing_and_is_not_a_write_result():
    sion = _sion()
    blocked = _licence(sion, 1, export_cif="1000.00", usage_cif="1200.00")

    result = _persist(sion, [blocked])

    assert _row(result, blocked)["status"] == "BLOCKED_OVER_UTILISED"
    assert result["write_results"] == [{
        "license_id": blocked.pk,
        "status": "BLOCKED_OVER_UTILISED",
        "reason": _row(result, blocked)["reason"],
    }]
    assert result["over_utilised_count"] == 1
    assert result["planned_licenses"] == 0
    assert _plan_rows(blocked) == 0


def test_skipped_no_match_is_a_write_result_with_no_plan_rows():
    sion = _sion()
    licence = _licence(sion, 2, hs_code=NO_MATCH_HS)

    result = _persist(sion, [licence])

    assert _row(result, licence)["status"] == "SKIPPED_NO_MATCH"
    assert len(result["write_results"]) == 1, result
    assert result["write_results"][0] == {
        "license_id": licence.pk,
        "status": "SKIPPED_NO_MATCH",
        "reason": "Active saved rules produced no persistable planning lines.",
    }
    assert _plan_rows(licence) == 0


def test_successful_persistence_writes_plan_rows_and_reports_planned():
    sion = _sion()
    licence = _licence(sion, 3)

    result = _persist(sion, [licence])

    assert _row(result, licence)["status"] == "PLANNED"
    assert [wr["status"] for wr in result["write_results"]] == ["PLANNED"]
    assert result["write_results"][0]["license_id"] == licence.pk
    assert _plan_rows(licence) > 0


def test_failed_persistence_propagates_and_rolls_back_earlier_licences():
    sion = _sion()
    first = _licence(sion, 4)
    failing = _licence(sion, 5)
    # Licences with a strategy architecture persist via build_theoretical_strategy_plan;
    # the canonical builder is the fallback.  Fail whichever one is used for `failing`.
    original_strategy = CanonicalPlanningService.build_theoretical_strategy_plan
    original_canonical = CanonicalPlanningService.build_canonical_plan
    first_rows_seen_at_failure = []

    def _guard(original):
        def wrapped(**kwargs):
            if kwargs["license_id"] == failing.pk:
                # Proves `first` was written before the failure, so the rollback is real.
                first_rows_seen_at_failure.append(_plan_rows(first))
                raise RuntimeError("persistence failed")
            return original(**kwargs)
        return wrapped

    with mock.patch.object(CanonicalPlanningService, "build_theoretical_strategy_plan", side_effect=_guard(original_strategy)), \
            mock.patch.object(CanonicalPlanningService, "build_canonical_plan", side_effect=_guard(original_canonical)):
        with pytest.raises(RuntimeError, match="persistence failed"):
            _persist(sion, [first, failing])

    assert first_rows_seen_at_failure and first_rows_seen_at_failure[0] > 0
    assert _plan_rows(first) == 0
    assert _plan_rows(failing) == 0


def test_mixed_outcomes_report_each_licence_correctly_and_write_only_planned():
    sion = _sion()
    blocked = _licence(sion, 6, export_cif="1000.00", usage_cif="1200.00")
    skipped = _licence(sion, 7, hs_code=NO_MATCH_HS)
    planned = _licence(sion, 8)
    total_plan_rows_before = LicenseItemPlan.objects.count()

    result = _persist(sion, [blocked, skipped, planned])

    assert _row(result, blocked)["status"] == "BLOCKED_OVER_UTILISED"
    assert _row(result, skipped)["status"] == "SKIPPED_NO_MATCH"
    assert _row(result, planned)["status"] == "PLANNED"

    # write_results: one entry per evaluated licence; only PLANNED rows wrote plan rows.
    assert {wr["license_id"]: wr["status"] for wr in result["write_results"]} == {
        blocked.pk: "BLOCKED_OVER_UTILISED",
        skipped.pk: "SKIPPED_NO_MATCH",
        planned.pk: "PLANNED",
    }
    assert result["over_utilised_count"] == 1
    assert result["planned_licenses"] == 1

    assert _plan_rows(blocked) == 0
    assert _plan_rows(skipped) == 0
    assert _plan_rows(planned) > 0
    assert LicenseItemPlan.objects.count() - total_plan_rows_before == _plan_rows(planned)
