"""
Golden test suite for ``CanonicalPlanningService`` (Module 2).

Covers the ten golden scenarios named in the Module 2 implementation contract,
plus the cross-cutting guarantees the forensic audit called out as unverified:

  1.  single_item        — one import item, planned qty < available
  2.  multiple_items     — 3 items, sequential allocation
  3.  priority_ordering  — items allocated in priority order (lowest first)
  4.  partial_usage      — requested qty < available qty
  5.  exact_usage        — requested qty == available qty
  6.  insufficient       — requested qty > available qty (errors)
  7.  zero_qty           — requested qty == 0
  8.  decimal_qty        — 0.123 quantity survives at Decimal(15,3)
  9.  multiple_companies — company mismatch errors
  10. multiple_licenses  — license mismatch errors

Cross-cutting:
  * BL-PLAN-01 invariant ``planned_cif_fc == planned_quantity × unit_price``
    holds on every persisted row of every scenario (the defect the E126/E132
    engines still carry — see MODULE_2_PLANNING_CALCULATIONS.md §2.2).
  * Full-replace persistence is atomic (a mid-write failure must not leave the
    license with a deleted-but-not-recreated plan).
  * The CIF waterfall never overspends the LIVE license balance.
  * The canonical module references none of the legacy per-norm planners.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.models import CompanyModel, HSCodeModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
)
from apps.license.services.canonical_planning_service import (
    CanonicalPlanningService,
    CompanyIsolationError,
    InsufficientQuantityError,
    InvalidPlanInputError,
    LicenseMismatchError,
    LicenseNotFoundError,
    STATUS_PLANNED,
    STATUS_SKIPPED_ALREADY_PLANNED,
    quantize_cif,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------

_IEC_SEQ = iter(range(1000000000, 1000009999))


def _company(name: str) -> CompanyModel:
    return CompanyModel.objects.create(iec=str(next(_IEC_SEQ)), name=name)


def _hs(code: str) -> HSCodeModel:
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


def make_license(*, company=None, balance_cif="10000.00", number=None) -> LicenseDetailsModel:
    """A DFIA license whose LIVE ``get_balance_cif`` equals ``balance_cif``.

    With no BOEs, no trades and no allotments, ``calculate_financial_balance``
    collapses to ``calculate_opening_balance`` == ``calculate_credit`` == the sum
    of the license's export-item CIF, so a single export item sets the balance
    exactly.
    """
    company = company or _company("Golden Exporter")
    number = number or f"GOLD-{LicenseDetailsModel.objects.count() + 1:04d}"
    lic = LicenseDetailsModel.objects.create(
        license_number=number,
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=180),
        exporter=company,
    )
    LicenseExportItemModel.objects.create(license=lic, cif_fc=Decimal(balance_cif))
    return lic


def add_item(lic, *, serial, description, available, hs="10011000") -> LicenseImportItemsModel:
    """An import item with a distinct description, so each is its own plan group.

    ``plan_group_key`` is HSN + normalized description; giving every item a
    different description keeps one item == one group, which is what the golden
    scenarios describe.
    """
    qty = Decimal(str(available))
    return LicenseImportItemsModel.objects.create(
        license=lic,
        serial_number=serial,
        description=description,
        hs_code=_hs(hs),
        quantity=qty,
        available_quantity=qty,
    )


def plan(lic, items, **kwargs):
    """Invoke the service with sane defaults for the golden scenarios."""
    kwargs.setdefault("norm_class", "E1")
    kwargs.setdefault("force_replan", True)
    return CanonicalPlanningService.build_canonical_plan(
        license_id=lic.pk, items=items, **kwargs,
    )


def assert_cif_invariant(license_obj):
    """BL-PLAN-01: every persisted row must satisfy cif == qty × price.

    This is the invariant the E126/E132 engines violate by flooring the quantity
    without recomputing the CIF. The canonical service must never produce a row
    that fails it.
    """
    rows = LicenseItemPlan.objects.filter(license=license_obj)
    assert rows.exists(), "expected at least one persisted plan row to check"
    for row in rows:
        expected = quantize_cif(row.planned_quantity * row.unit_price)
        assert row.planned_cif_fc == expected, (
            f"BL-PLAN-01 violated on plan {row.pk}: "
            f"cif={row.planned_cif_fc} but qty({row.planned_quantity}) "
            f"× price({row.unit_price}) = {expected}"
        )


# ---------------------------------------------------------------------------
# 1. single_item
# ---------------------------------------------------------------------------

class TestGoldenSingleItem:
    def test_single_item_under_available_is_planned(self):
        lic = make_license(balance_cif="10000.00")
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        result = plan(lic, [
            {"import_item_id": item.id, "requested_quantity": "100.000", "unit_price": "3.00"},
        ])

        assert result["status"] == STATUS_PLANNED
        assert result["license_id"] == lic.pk
        assert result["norm_class"] == "E1"
        assert result["plan_id"].startswith(f"plan-{lic.pk}-")

        (line,) = result["allocated_items"]
        assert line["allocated_quantity"] == Decimal("100.000")
        assert line["unit_price"] == Decimal("3.00")
        assert line["planned_cif_fc"] == Decimal("300.00")
        assert line["status"] == "ALLOCATED"

        summary = result["allocation_summary"]
        assert summary["opening_balance_cif"] == Decimal("10000.00")
        assert summary["consumed_cif"] == Decimal("300.00")
        assert summary["remaining_balance_cif"] == Decimal("9700.00")
        assert summary["lines_created"] == 1
        assert summary["fully_allocated"] is True

        (row,) = LicenseItemPlan.objects.filter(license=lic)
        assert row.import_item_id == item.id
        assert row.planned_quantity == Decimal("100.000")
        assert row.planned_cif_fc == Decimal("300.00")
        # A fresh line's independently-draining balance starts at the plan.
        assert row.remaining_quantity == Decimal("100.000")
        assert row.remaining_cif_fc == Decimal("300.00")
        assert_cif_invariant(lic)

    def test_module_1_style_alias_is_the_same_entry_point(self):
        """``build_canonical_planning_dataset`` mirrors Module 1's
        ``build_canonical_ledger_dataset`` naming and must not drift from
        ``build_canonical_plan``."""
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        result = CanonicalPlanningService.build_canonical_planning_dataset(
            license_id=lic.pk,
            norm_class="E1",
            items=[{"import_item_id": item.id, "requested_quantity": "10.000", "unit_price": "2.00"}],
            force_replan=True,
        )
        assert result["status"] == STATUS_PLANNED
        assert result["allocated_items"][0]["planned_cif_fc"] == Decimal("20.00")

    def test_plan_id_is_deterministic_for_identical_input(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        payload = [{"import_item_id": item.id, "requested_quantity": "100.000", "unit_price": "3.00"}]

        first = plan(lic, payload)
        second = plan(lic, payload)
        assert first["plan_id"] == second["plan_id"]


# ---------------------------------------------------------------------------
# 2. multiple_items
# ---------------------------------------------------------------------------

class TestGoldenMultipleItems:
    def test_three_items_allocate_sequentially_against_one_pool(self):
        lic = make_license(balance_cif="10000.00")
        a = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        b = add_item(lic, serial=2, description="MILK POWDER", available="400.000")
        c = add_item(lic, serial=3, description="FRUIT JUICE", available="300.000")

        result = plan(lic, [
            {"import_item_id": a.id, "requested_quantity": "100.000", "unit_price": "10.00"},
            {"import_item_id": b.id, "requested_quantity": "200.000", "unit_price": "5.00"},
            {"import_item_id": c.id, "requested_quantity": "300.000", "unit_price": "2.50"},
        ])

        cifs = [line["planned_cif_fc"] for line in result["allocated_items"]]
        assert cifs == [Decimal("1000.00"), Decimal("1000.00"), Decimal("750.00")]

        summary = result["allocation_summary"]
        assert summary["consumed_cif"] == Decimal("2750.00")
        assert summary["remaining_balance_cif"] == Decimal("7250.00")
        assert summary["total_allocated_quantity"] == Decimal("600.000")
        assert summary["lines_created"] == 3

        assert LicenseItemPlan.objects.filter(license=lic).count() == 3
        assert_cif_invariant(lic)

    def test_full_replace_discards_the_previous_plan(self):
        lic = make_license()
        a = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        b = add_item(lic, serial=2, description="MILK POWDER", available="400.000")

        plan(lic, [
            {"import_item_id": a.id, "requested_quantity": "100.000", "unit_price": "3.00"},
            {"import_item_id": b.id, "requested_quantity": "100.000", "unit_price": "3.00"},
        ])
        assert LicenseItemPlan.objects.filter(license=lic).count() == 2

        plan(lic, [
            {"import_item_id": a.id, "requested_quantity": "50.000", "unit_price": "4.00"},
        ])

        rows = LicenseItemPlan.objects.filter(license=lic)
        assert rows.count() == 1
        assert rows.first().import_item_id == a.id
        assert rows.first().planned_quantity == Decimal("50.000")


# ---------------------------------------------------------------------------
# 3. priority_ordering
# ---------------------------------------------------------------------------

class TestGoldenPriorityOrdering:
    def test_lowest_priority_number_is_allocated_first(self):
        lic = make_license(balance_cif="10000.00")
        a = add_item(lic, serial=1, description="ALUMINIUM FOIL", available="500.000")
        b = add_item(lic, serial=2, description="COCOA MASS", available="500.000")
        c = add_item(lic, serial=3, description="TARTARIC ACID", available="500.000")

        # Supplied out of order; priority (not input order) must drive the run.
        result = plan(lic, [
            {"import_item_id": a.id, "requested_quantity": "10.000", "unit_price": "4.50", "priority": 30},
            {"import_item_id": b.id, "requested_quantity": "10.000", "unit_price": "10.00", "priority": 10},
            {"import_item_id": c.id, "requested_quantity": "10.000", "unit_price": "1.50", "priority": 20},
        ])

        assert [line["import_item_id"] for line in result["allocated_items"]] == [b.id, c.id, a.id]
        assert [line["priority"] for line in result["allocated_items"]] == [10, 20, 30]

    def test_priority_decides_who_gets_the_scarce_cif(self):
        """The waterfall is order-sensitive: the winner takes its full ceiling
        price and the loser absorbs the shortfall at a reduced rate."""
        lic = make_license(balance_cif="1000.00")
        rich = add_item(lic, serial=1, description="COCOA MASS", available="100.000")
        poor = add_item(lic, serial=2, description="FRUIT JUICE", available="100.000")

        result = plan(lic, [
            {"import_item_id": poor.id, "requested_quantity": "100.000", "unit_price": "8.00", "priority": 2},
            {"import_item_id": rich.id, "requested_quantity": "100.000", "unit_price": "8.00", "priority": 1},
        ])

        first, second = result["allocated_items"]
        assert first["import_item_id"] == rich.id
        assert first["planned_cif_fc"] == Decimal("800.00")
        assert first["status"] == "ALLOCATED"

        # Only 200.00 left for a 100 × 8.00 = 800.00 ask -> rate drops to 2.00.
        assert second["import_item_id"] == poor.id
        assert second["unit_price"] == Decimal("2.00")
        assert second["planned_cif_fc"] == Decimal("200.00")
        assert second["status"] == "CIF_CONSTRAINED"

        assert result["allocation_summary"]["remaining_balance_cif"] == Decimal("0.00")
        assert result["allocation_summary"]["fully_allocated"] is False
        assert_cif_invariant(lic)

    def test_absent_priority_preserves_caller_order(self):
        lic = make_license()
        a = add_item(lic, serial=1, description="AAA", available="100.000")
        b = add_item(lic, serial=2, description="BBB", available="100.000")

        result = plan(lic, [
            {"import_item_id": b.id, "requested_quantity": "1.000", "unit_price": "1.00"},
            {"import_item_id": a.id, "requested_quantity": "1.000", "unit_price": "1.00"},
        ])
        assert [line["import_item_id"] for line in result["allocated_items"]] == [b.id, a.id]


# ---------------------------------------------------------------------------
# 4. partial_usage  /  5. exact_usage  /  6. insufficient
# ---------------------------------------------------------------------------

class TestGoldenQuantityBoundaries:
    def test_partial_usage_leaves_group_capacity_unspent(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        result = plan(lic, [
            {"import_item_id": item.id, "requested_quantity": "499.999", "unit_price": "1.00"},
        ])
        (line,) = result["allocated_items"]
        assert line["allocated_quantity"] == Decimal("499.999")
        assert line["available_capacity"] == Decimal("500.000")
        assert line["status"] == "ALLOCATED"
        assert_cif_invariant(lic)

    def test_exact_usage_is_accepted(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        result = plan(lic, [
            {"import_item_id": item.id, "requested_quantity": "500.000", "unit_price": "1.00"},
        ])
        (line,) = result["allocated_items"]
        assert line["allocated_quantity"] == Decimal("500.000")
        assert line["allocated_quantity"] == line["available_capacity"]
        assert LicenseItemPlan.objects.filter(license=lic).count() == 1
        assert_cif_invariant(lic)

    def test_insufficient_quantity_raises_and_writes_nothing(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        with pytest.raises(InsufficientQuantityError) as exc:
            plan(lic, [
                {"import_item_id": item.id, "requested_quantity": "500.001", "unit_price": "1.00"},
            ])

        assert exc.value.code == "INSUFFICIENT_QUANTITY"
        assert exc.value.details["import_item_id"] == item.id
        assert exc.value.details["available_capacity"] == "500.000"
        assert not LicenseItemPlan.objects.filter(license=lic).exists()

    def test_insufficient_rolls_back_and_preserves_the_existing_plan(self):
        """A rejected re-plan must leave the previous plan exactly as it was."""
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        plan(lic, [{"import_item_id": item.id, "requested_quantity": "100.000", "unit_price": "3.00"}])
        before = list(LicenseItemPlan.objects.filter(license=lic).values_list("id", "planned_quantity"))

        with pytest.raises(InsufficientQuantityError):
            plan(lic, [{"import_item_id": item.id, "requested_quantity": "9999.000", "unit_price": "3.00"}])

        after = list(LicenseItemPlan.objects.filter(license=lic).values_list("id", "planned_quantity"))
        assert after == before

    def test_two_lines_on_one_group_cannot_each_take_full_capacity(self):
        """Same HSN + same description == one plan group with one shared cap."""
        lic = make_license()
        a = add_item(lic, serial=1, description="MILK 0404", available="300.000", hs="04041010")
        b = add_item(lic, serial=2, description="MILK 0404", available="200.000", hs="04041010")

        # Group capacity is 500.000; 300 + 200 fits exactly.
        ok = plan(lic, [
            {"import_item_id": a.id, "requested_quantity": "300.000", "unit_price": "1.00"},
            {"import_item_id": b.id, "requested_quantity": "200.000", "unit_price": "1.00"},
        ])
        assert ok["allocation_summary"]["total_allocated_quantity"] == Decimal("500.000")

        # One more unit over the shared cap must be rejected.
        with pytest.raises(InsufficientQuantityError):
            plan(lic, [
                {"import_item_id": a.id, "requested_quantity": "300.000", "unit_price": "1.00"},
                {"import_item_id": b.id, "requested_quantity": "200.001", "unit_price": "1.00"},
            ])


# ---------------------------------------------------------------------------
# 7. zero_qty
# ---------------------------------------------------------------------------

class TestGoldenZeroQuantity:
    def test_zero_quantity_is_reported_but_never_persisted(self):
        """A 0-qty LicenseItemPlan row would pin the group's allotment cap to
        zero and block every future allocation, so it is reported and skipped."""
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        result = plan(lic, [
            {"import_item_id": item.id, "requested_quantity": "0", "unit_price": "3.00"},
        ])

        (line,) = result["allocated_items"]
        assert line["allocated_quantity"] == Decimal("0.000")
        assert line["planned_cif_fc"] == Decimal("0.00")
        assert line["status"] == "ZERO_QUANTITY"

        summary = result["allocation_summary"]
        assert summary["items_requested"] == 1
        assert summary["lines_created"] == 0
        assert summary["items_zero_quantity"] == 1
        assert summary["consumed_cif"] == Decimal("0.00")
        assert not LicenseItemPlan.objects.filter(license=lic).exists()

    def test_zero_quantity_alongside_real_items_does_not_consume_balance(self):
        lic = make_license(balance_cif="1000.00")
        a = add_item(lic, serial=1, description="COCOA MASS", available="100.000")
        b = add_item(lic, serial=2, description="FRUIT JUICE", available="100.000")

        result = plan(lic, [
            {"import_item_id": a.id, "requested_quantity": "0", "unit_price": "99.00"},
            {"import_item_id": b.id, "requested_quantity": "100.000", "unit_price": "5.00"},
        ])

        assert result["allocation_summary"]["consumed_cif"] == Decimal("500.00")
        assert result["allocation_summary"]["remaining_balance_cif"] == Decimal("500.00")
        assert LicenseItemPlan.objects.filter(license=lic).count() == 1

    def test_negative_quantity_is_rejected(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        with pytest.raises(InvalidPlanInputError):
            plan(lic, [{"import_item_id": item.id, "requested_quantity": "-1.000", "unit_price": "3.00"}])


# ---------------------------------------------------------------------------
# 8. decimal_qty
# ---------------------------------------------------------------------------

class TestGoldenDecimalQuantity:
    def test_three_decimal_place_quantity_survives_the_round_trip(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="TARTARIC ACID", available="10.000")

        result = plan(lic, [
            {"import_item_id": item.id, "requested_quantity": "0.123", "unit_price": "1.50"},
        ])

        (line,) = result["allocated_items"]
        assert line["allocated_quantity"] == Decimal("0.123")
        # 0.123 × 1.50 = 0.1845 -> ROUND_HALF_UP at 2dp -> 0.18
        assert line["planned_cif_fc"] == Decimal("0.18")

        (row,) = LicenseItemPlan.objects.filter(license=lic)
        assert row.planned_quantity == Decimal("0.123")
        assert row.planned_cif_fc == Decimal("0.18")
        assert_cif_invariant(lic)

    def test_fourth_decimal_place_rounds_half_up_to_three(self):
        """Decimal(15,3) is the column precision; ROUND_HALF_UP matches Module 1."""
        lic = make_license()
        item = add_item(lic, serial=1, description="TARTARIC ACID", available="10.000")

        result = plan(lic, [
            {"import_item_id": item.id, "requested_quantity": "0.1235", "unit_price": "1.00"},
        ])
        assert result["allocated_items"][0]["allocated_quantity"] == Decimal("0.124")

    def test_decimal_quantities_accumulate_without_drift(self):
        lic = make_license(balance_cif="10000.00")
        items = [
            add_item(lic, serial=i, description=f"ITEM {i}", available="1.000")
            for i in range(1, 4)
        ]
        result = plan(lic, [
            {"import_item_id": it.id, "requested_quantity": "0.123", "unit_price": "2.00"}
            for it in items
        ])
        assert result["allocation_summary"]["total_allocated_quantity"] == Decimal("0.369")
        assert result["allocation_summary"]["consumed_cif"] == Decimal("0.75")  # 3 × 0.25
        assert_cif_invariant(lic)


# ---------------------------------------------------------------------------
# 9. multiple_companies
# ---------------------------------------------------------------------------

class TestGoldenCompanyIsolation:
    def test_company_mismatch_is_rejected(self):
        owner = _company("Owner Co")
        intruder = _company("Intruder Co")
        lic = make_license(company=owner)
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        with pytest.raises(CompanyIsolationError) as exc:
            plan(
                lic,
                [{"import_item_id": item.id, "requested_quantity": "10.000", "unit_price": "1.00"}],
                company_id=intruder.pk,
            )

        assert exc.value.code == "COMPANY_MISMATCH"
        assert exc.value.details["license_company_id"] == owner.pk
        assert exc.value.details["requested_company_id"] == intruder.pk
        assert not LicenseItemPlan.objects.filter(license=lic).exists()

    def test_matching_company_is_accepted(self):
        owner = _company("Owner Co")
        lic = make_license(company=owner)
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        result = plan(
            lic,
            [{"import_item_id": item.id, "requested_quantity": "10.000", "unit_price": "1.00"}],
            company_id=owner.pk,
        )
        assert result["status"] == STATUS_PLANNED
        assert LicenseItemPlan.objects.filter(license=lic).count() == 1

    def test_omitting_company_id_skips_the_check_for_internal_callers(self):
        lic = make_license(company=_company("Owner Co"))
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        result = plan(
            lic,
            [{"import_item_id": item.id, "requested_quantity": "10.000", "unit_price": "1.00"}],
            company_id=None,
        )
        assert result["status"] == STATUS_PLANNED


# ---------------------------------------------------------------------------
# 10. multiple_licenses
# ---------------------------------------------------------------------------

class TestGoldenLicenseIsolation:
    def test_item_from_another_license_is_rejected(self):
        lic_a = make_license(number="GOLD-A")
        lic_b = make_license(number="GOLD-B")
        own = add_item(lic_a, serial=1, description="COCOA MASS", available="500.000")
        foreign = add_item(lic_b, serial=1, description="COCOA MASS", available="500.000")

        with pytest.raises(LicenseMismatchError) as exc:
            plan(lic_a, [
                {"import_item_id": own.id, "requested_quantity": "10.000", "unit_price": "1.00"},
                {"import_item_id": foreign.id, "requested_quantity": "10.000", "unit_price": "1.00"},
            ])

        assert exc.value.code == "LICENSE_MISMATCH"
        assert exc.value.details["foreign_items"] == {foreign.id: lic_b.pk}
        # Rejected wholesale — the valid line in the same request is not written.
        assert not LicenseItemPlan.objects.filter(license=lic_a).exists()

    def test_nonexistent_item_is_rejected(self):
        lic = make_license()
        add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        with pytest.raises(LicenseMismatchError) as exc:
            plan(lic, [{"import_item_id": 99999999, "requested_quantity": "1.000", "unit_price": "1.00"}])
        assert exc.value.details["missing_items"] == [99999999]

    def test_unknown_license_is_rejected(self):
        with pytest.raises(LicenseNotFoundError):
            CanonicalPlanningService.build_canonical_plan(license_id=99999999, items=[])

    def test_planning_one_license_never_touches_another(self):
        lic_a = make_license(number="GOLD-A")
        lic_b = make_license(number="GOLD-B")
        item_a = add_item(lic_a, serial=1, description="COCOA MASS", available="500.000")
        item_b = add_item(lic_b, serial=1, description="COCOA MASS", available="500.000")

        plan(lic_b, [{"import_item_id": item_b.id, "requested_quantity": "42.000", "unit_price": "1.00"}])
        plan(lic_a, [{"import_item_id": item_a.id, "requested_quantity": "7.000", "unit_price": "1.00"}])

        # lic_a's full-replace must not have deleted lic_b's plan.
        assert LicenseItemPlan.objects.filter(license=lic_b).count() == 1
        assert LicenseItemPlan.objects.get(license=lic_b).planned_quantity == Decimal("42.000")
        assert LicenseItemPlan.objects.get(license=lic_a).planned_quantity == Decimal("7.000")


# ---------------------------------------------------------------------------
# Cross-cutting: live balance, force_replan, atomicity, precision
# ---------------------------------------------------------------------------

class TestLiveBalanceIsRespected:
    def test_waterfall_never_overspends_the_live_balance(self):
        lic = make_license(balance_cif="100.00")
        a = add_item(lic, serial=1, description="AAA", available="1000.000")
        b = add_item(lic, serial=2, description="BBB", available="1000.000")

        result = plan(lic, [
            {"import_item_id": a.id, "requested_quantity": "1000.000", "unit_price": "50.00", "priority": 1},
            {"import_item_id": b.id, "requested_quantity": "1000.000", "unit_price": "50.00", "priority": 2},
        ])

        total = sum(r.planned_cif_fc for r in LicenseItemPlan.objects.filter(license=lic))
        assert total <= Decimal("100.00")
        assert result["allocation_summary"]["remaining_balance_cif"] >= Decimal("0.00")
        assert_cif_invariant(lic)

    def test_zero_balance_still_plans_quantity_at_zero_value(self):
        """The quantity cap is worth persisting even when no CIF is left."""
        lic = make_license(balance_cif="0.00")
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")

        result = plan(lic, [
            {"import_item_id": item.id, "requested_quantity": "10.000", "unit_price": "3.00"},
        ])
        (line,) = result["allocated_items"]
        assert line["allocated_quantity"] == Decimal("10.000")
        assert line["planned_cif_fc"] == Decimal("0.00")
        assert line["status"] == "NO_BALANCE"
        assert_cif_invariant(lic)

    def test_constrained_rate_rounds_down_so_the_pool_is_never_breached(self):
        """3 units against a 10.00 pool: 10/3 = 3.333... must round DOWN to 3.33,
        not up to 3.34 (which would spend 10.02)."""
        lic = make_license(balance_cif="10.00")
        item = add_item(lic, serial=1, description="COCOA MASS", available="100.000")

        result = plan(lic, [
            {"import_item_id": item.id, "requested_quantity": "3.000", "unit_price": "99.00"},
        ])
        (line,) = result["allocated_items"]
        assert line["unit_price"] == Decimal("3.33")
        assert line["planned_cif_fc"] == Decimal("9.99")
        assert line["planned_cif_fc"] <= Decimal("10.00")
        assert_cif_invariant(lic)


class TestForceReplan:
    def _fully_plan(self, lic, item):
        # Consume 100% of the balance so the >= 99% "already planned" gate trips.
        return plan(lic, [
            {"import_item_id": item.id, "requested_quantity": "100.000", "unit_price": "10.00"},
        ])

    def test_already_planned_license_is_skipped_without_force(self):
        lic = make_license(balance_cif="1000.00")
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        self._fully_plan(lic, item)

        result = CanonicalPlanningService.build_canonical_plan(
            license_id=lic.pk,
            norm_class="E1",
            items=[{"import_item_id": item.id, "requested_quantity": "5.000", "unit_price": "1.00"}],
            force_replan=False,
        )

        assert result["status"] == STATUS_SKIPPED_ALREADY_PLANNED
        assert result["plan_id"] is None
        assert result["allocation_summary"]["lines_created"] == 0
        # Untouched: still the original 100 @ 10.00.
        (row,) = LicenseItemPlan.objects.filter(license=lic)
        assert row.planned_quantity == Decimal("100.000")

    def test_force_replan_overrides_the_already_planned_gate(self):
        lic = make_license(balance_cif="1000.00")
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        self._fully_plan(lic, item)

        result = CanonicalPlanningService.build_canonical_plan(
            license_id=lic.pk,
            norm_class="E1",
            items=[{"import_item_id": item.id, "requested_quantity": "5.000", "unit_price": "1.00"}],
            force_replan=True,
        )

        assert result["status"] == STATUS_PLANNED
        (row,) = LicenseItemPlan.objects.filter(license=lic)
        assert row.planned_quantity == Decimal("5.000")

    def test_partially_planned_license_is_not_skipped(self):
        """Below the 99% threshold the license is still plannable without force."""
        lic = make_license(balance_cif="1000.00")
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        plan(lic, [{"import_item_id": item.id, "requested_quantity": "10.000", "unit_price": "1.00"}])

        result = CanonicalPlanningService.build_canonical_plan(
            license_id=lic.pk,
            norm_class="E1",
            items=[{"import_item_id": item.id, "requested_quantity": "20.000", "unit_price": "1.00"}],
            force_replan=False,
        )
        assert result["status"] == STATUS_PLANNED
        assert LicenseItemPlan.objects.get(license=lic).planned_quantity == Decimal("20.000")

    def test_unplanned_license_is_never_treated_as_already_planned(self):
        lic = make_license(balance_cif="0.00")
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        result = CanonicalPlanningService.build_canonical_plan(
            license_id=lic.pk,
            items=[{"import_item_id": item.id, "requested_quantity": "1.000", "unit_price": "0.00"}],
            force_replan=False,
        )
        assert result["status"] == STATUS_PLANNED


class TestWritesAreTransactional:
    def test_failure_midway_through_the_write_rolls_back_the_delete(self, monkeypatch):
        """Full-replace deletes before it inserts. If an insert blows up, the
        DELETE must roll back too — otherwise the license silently loses its
        plan."""
        lic = make_license()
        a = add_item(lic, serial=1, description="AAA", available="500.000")
        b = add_item(lic, serial=2, description="BBB", available="500.000")

        plan(lic, [
            {"import_item_id": a.id, "requested_quantity": "11.000", "unit_price": "1.00"},
            {"import_item_id": b.id, "requested_quantity": "22.000", "unit_price": "1.00"},
        ])
        before = sorted(
            LicenseItemPlan.objects.filter(license=lic).values_list("import_item_id", "planned_quantity")
        )
        assert len(before) == 2

        original_save = LicenseItemPlan.save
        calls = {"n": 0}

        def exploding_save(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:  # blow up after the first row is inserted
                raise RuntimeError("simulated DB failure mid-write")
            return original_save(self, *args, **kwargs)

        monkeypatch.setattr(LicenseItemPlan, "save", exploding_save)

        with pytest.raises(RuntimeError, match="simulated DB failure"):
            plan(lic, [
                {"import_item_id": a.id, "requested_quantity": "33.000", "unit_price": "1.00"},
                {"import_item_id": b.id, "requested_quantity": "44.000", "unit_price": "1.00"},
            ])

        monkeypatch.undo()
        after = sorted(
            LicenseItemPlan.objects.filter(license=lic).values_list("import_item_id", "planned_quantity")
        )
        assert after == before, "the pre-existing plan must survive a failed re-plan"

    def test_empty_items_clears_the_plan(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        plan(lic, [{"import_item_id": item.id, "requested_quantity": "10.000", "unit_price": "1.00"}])
        assert LicenseItemPlan.objects.filter(license=lic).count() == 1

        result = plan(lic, [])
        assert result["status"] == STATUS_PLANNED
        assert result["allocation_summary"]["lines_created"] == 0
        assert not LicenseItemPlan.objects.filter(license=lic).exists()


class TestBaselineSnapshot:
    def test_new_lines_are_stamped_with_the_group_usage_baseline(self):
        """Baseline snapshot is what makes "used since this plan" correct when an
        allotment is amended in place (forensic audit §3.3). With no allotments
        yet it is zero, but it must be stamped, not left null."""
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        plan(lic, [{"import_item_id": item.id, "requested_quantity": "10.000", "unit_price": "1.00"}])

        (row,) = LicenseItemPlan.objects.filter(license=lic)
        assert row.baseline_used_quantity == Decimal("0.000")
        assert row.baseline_used_cif_fc == Decimal("0.00")
        assert row.license_id == lic.pk  # denormalized FK populated


class TestInputValidation:
    def test_non_dict_item_is_rejected(self):
        lic = make_license()
        with pytest.raises(InvalidPlanInputError):
            plan(lic, ["not-a-dict"])

    def test_missing_import_item_id_is_rejected(self):
        lic = make_license()
        with pytest.raises(InvalidPlanInputError):
            plan(lic, [{"requested_quantity": "1.000"}])

    def test_unparseable_quantity_is_rejected(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        with pytest.raises(InvalidPlanInputError):
            plan(lic, [{"import_item_id": item.id, "requested_quantity": "abc"}])

    def test_negative_unit_price_is_rejected(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        with pytest.raises(InvalidPlanInputError):
            plan(lic, [{"import_item_id": item.id, "requested_quantity": "1.000", "unit_price": "-5.00"}])

    @pytest.mark.parametrize("bad", ["abc", "1O0", "nan", "Infinity", True, object()])
    def test_garbage_quantity_never_degrades_into_a_silent_zero(self, bad):
        """A quantity that cannot be parsed must error. If it silently became 0
        the line would be dropped from the plan and the caller would never know."""
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        with pytest.raises(InvalidPlanInputError):
            plan(lic, [{"import_item_id": item.id, "requested_quantity": bad, "unit_price": "1.00"}])

    def test_garbage_unit_price_is_rejected(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        with pytest.raises(InvalidPlanInputError):
            plan(lic, [{"import_item_id": item.id, "requested_quantity": "1.000", "unit_price": "abc"}])

    def test_quantity_beyond_the_column_range_is_rejected(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        with pytest.raises(InvalidPlanInputError, match="Decimal\\(15,3\\)"):
            plan(lic, [{"import_item_id": item.id, "requested_quantity": "1" + "0" * 12}])

    def test_none_quantity_is_treated_as_zero(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        result = plan(lic, [{"import_item_id": item.id, "requested_quantity": None, "unit_price": "1.00"}])
        assert result["allocated_items"][0]["status"] == "ZERO_QUANTITY"

    def test_numeric_types_other_than_str_are_accepted(self):
        lic = make_license()
        item = add_item(lic, serial=1, description="COCOA MASS", available="500.000")
        result = plan(lic, [
            {"import_item_id": item.id, "requested_quantity": 12.5, "unit_price": Decimal("2")},
        ])
        (line,) = result["allocated_items"]
        assert line["allocated_quantity"] == Decimal("12.500")
        assert line["planned_cif_fc"] == Decimal("25.00")


class TestNoLegacyPlannerReferences:
    """The canonical service must stand alone — it may not reach into any of the
    legacy per-norm planners, or it inherits their defects (BL-PLAN-01) and their
    dispatch coupling."""

    LEGACY_MODULES = (
        "e1_auto_plan", "e5_auto_plan", "e126_auto_plan", "e132_auto_plan",
        "a3627_auto_plan", "e1_plan", "e5_plan", "e126_plan", "e132_plan",
        "planner_factory", "norm_plan", "milk_planner",
    )

    def test_canonical_module_imports_no_legacy_planner(self):
        import ast
        import inspect

        from apps.license.services import canonical_planning_service as mod

        tree = ast.parse(inspect.getsource(mod))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module)
                imported.update(f"{node.module}.{a.name}" for a in node.names if node.module)

        offenders = sorted(
            name for name in imported
            if any(legacy in name for legacy in self.LEGACY_MODULES)
        )
        assert offenders == [], f"canonical planning must not import legacy planners: {offenders}"
