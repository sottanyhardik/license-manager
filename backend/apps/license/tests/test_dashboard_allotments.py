"""
Dashboard allotment activity: the engine-backed figures per allotment, the four distinct quantities,
partial and multiple BOE utilisation, direct BOEs, deleted allotments, and reconciliation with the
licence-side engine. Contract: docs/09-module-implementation/dashboard.md.

Reservation figures follow the engine's current rule. A BOE-linked allotment reports zero reserved CIF,
and the CIF the engine neither reserves nor counts as utilised is shown as `not_reserved_cif` (ISS-008).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.license.services import dashboard_summary as summary
from apps.license.services.balance_calculator import LicenseBalanceCalculator as C
from apps.reconciliation.models import BOEAllotmentAllocation

from .test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


def _scope(**kwargs):
    return summary.DashboardScope(as_of=date.today(), **kwargs)


def _row(section, allotment):
    return next(r for r in section["recent"] if r["id"] == allotment.pk)


class AllotmentFixtureMixin(LicenseBalanceLedgerFixtureMixin):
    def make_allotment(self, company):
        return AllotmentModel.objects.create(company=company, item_name="Test Allotment Item")

    def make_allotment_item(self, allotment, item, cif_fc, qty=Decimal("100.000")):
        return AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"), qty=qty,
        )

    def link_boe(self, allotment, boe):
        boe.allotment.add(allotment)

    def allocate(self, boe, allotment_item, cif, qty, debit_row):
        return BOEAllotmentAllocation.objects.create(
            row_details=debit_row,
            allotment_item=allotment_item,
            allocated_qty=Decimal(qty),
            allocated_cif_fc=Decimal(cif),
            allocated_cif_inr=Decimal(cif) * Decimal("84.5"),
            status=BOEAllotmentAllocation.STATUS_ACTIVE,
            is_current=True,
        )


class OpenAllotmentTests(AllotmentFixtureMixin, TestCase):
    def test_an_unlinked_allotment_reserves_its_full_cif_and_quantity(self):
        company = self.make_company()
        licence = self.make_license(company)
        allotment = self.make_allotment(company)
        self.make_allotment_item(allotment, self.make_item(licence, 1), cif_fc=Decimal("500.00"), qty=Decimal("60.000"))

        row = _row(summary.build_allotment_activity(_scope()), allotment)

        self.assertEqual(row["status"], "open")
        self.assertEqual(row["allotted_cif"], "500.00")
        self.assertEqual(row["consumed_cif"], "0.00")
        self.assertEqual(row["reserved_cif"], "500.00")
        self.assertEqual(row["not_reserved_cif"], "0.00")
        self.assertEqual(row["remaining_quantity"], "60.00")
        self.assertEqual(row["boe_count"], 0)

    def test_original_quantity_and_quantity_on_items_are_kept_apart(self):
        company = self.make_company()
        licence = self.make_license(company)
        allotment = self.make_allotment(company)
        allotment.required_quantity = Decimal("100.00")
        allotment.save()
        self.make_allotment_item(allotment, self.make_item(licence, 1), cif_fc=Decimal("300.00"), qty=Decimal("60.000"))

        row = _row(summary.build_allotment_activity(_scope()), allotment)

        self.assertEqual(row["original_quantity"], "100.00")
        self.assertEqual(row["allocated_quantity"], "60.00")
        self.assertEqual(row["unplaced_quantity"], "40.00", "requested minus placed on items")
        self.assertEqual(row["remaining_quantity"], "60.00")


class BoeUtilisationTests(AllotmentFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.licence = self.make_license(self.company)
        self.item = self.make_item(self.licence, 1)
        self.allotment = self.make_allotment(self.company)
        self.allotted = self.make_allotment_item(self.allotment, self.item, cif_fc=Decimal("100.00"), qty=Decimal("100.000"))

    def test_partial_utilisation_is_partly_utilised_and_the_rest_is_reported_as_not_reserved(self):
        boe = self.make_boe(self.company, number="BOE-PARTIAL")
        debit = self.make_debit_row(boe, self.item, cif_fc=Decimal("40.00"), qty=Decimal("40.000"))
        self.link_boe(self.allotment, boe)
        self.allocate(boe, self.allotted, cif="40.00", qty="40.000", debit_row=debit)

        row = _row(summary.build_allotment_activity(_scope()), self.allotment)

        self.assertEqual(row["status"], "partly_consumed")
        self.assertEqual(row["consumed_cif"], "40.00")
        self.assertEqual(row["reserved_cif"], "0.00", "the engine reports no reservation for a BOE-linked allotment (ISS-008)")
        self.assertEqual(row["not_reserved_cif"], "60.00")
        self.assertEqual(row["boe_count"], 1)

    def test_full_utilisation_is_fully_utilised_not_partly(self):
        boe = self.make_boe(self.company, number="BOE-FULL")
        debit = self.make_debit_row(boe, self.item, cif_fc=Decimal("100.00"))
        self.link_boe(self.allotment, boe)
        self.allocate(boe, self.allotted, cif="100.00", qty="100.000", debit_row=debit)

        row = _row(summary.build_allotment_activity(_scope()), self.allotment)

        self.assertEqual(row["status"], "consumed")
        self.assertEqual(row["consumed_cif"], "100.00")
        self.assertEqual(row["not_reserved_cif"], "0.00")

    def test_several_boes_against_one_allotment_are_summed_and_the_allotment_is_counted_once(self):
        first = self.make_boe(self.company, number="BOE-A")
        second = self.make_boe(self.company, number="BOE-B")
        debit_a = self.make_debit_row(first, self.item, cif_fc=Decimal("40.00"))
        debit_b = self.make_debit_row(second, self.item, cif_fc=Decimal("30.00"))
        self.link_boe(self.allotment, first)
        self.link_boe(self.allotment, second)
        self.allocate(first, self.allotted, cif="40.00", qty="40.000", debit_row=debit_a)
        self.allocate(second, self.allotted, cif="30.00", qty="30.000", debit_row=debit_b)

        section = summary.build_allotment_activity(_scope())
        row = _row(section, self.allotment)

        self.assertEqual(row["consumed_cif"], "70.00")
        self.assertEqual(row["boe_count"], 2)
        self.assertEqual(section["total"], 1, "one allotment, however many BOEs are linked")
        self.assertEqual(sum(section["counts"].values()), 1)
        self.assertEqual(section["totals"]["consumed_cif"], "70.00")

    def test_a_boe_link_with_no_allocation_is_boe_linked_and_all_of_its_cif_is_not_reserved(self):
        boe = self.make_boe(self.company, number="BOE-UNALLOCATED")
        self.make_debit_row(boe, self.item, cif_fc=Decimal("100.00"))
        self.link_boe(self.allotment, boe)

        row = _row(summary.build_allotment_activity(_scope()), self.allotment)

        self.assertEqual(row["status"], "boe_linked")
        self.assertEqual(row["consumed_cif"], "0.00", "no allocation record exists, so nothing is recorded as utilised")
        self.assertEqual(row["reserved_cif"], "0.00")
        self.assertEqual(row["not_reserved_cif"], "100.00")

    def test_a_direct_boe_is_not_an_allotment_and_does_not_change_the_section(self):
        before = summary.build_allotment_activity(_scope())
        direct = self.make_boe(self.company, number="BOE-DIRECT")
        self.make_debit_row(direct, self.item, cif_fc=Decimal("25.00"))

        after = summary.build_allotment_activity(_scope())

        self.assertEqual(after["total"], before["total"])
        self.assertEqual(after["totals"], before["totals"])
        self.assertEqual(after["counts"], before["counts"])


class ScopeAndIdentityTests(AllotmentFixtureMixin, TestCase):
    def test_deleting_an_allotment_removes_it_from_every_figure(self):
        """There is no cancelled state. Cancellation is a hard delete (ISS-010), so a deleted allotment must vanish."""
        company = self.make_company()
        licence = self.make_license(company)
        kept = self.make_allotment(company)
        self.make_allotment_item(kept, self.make_item(licence, 1), cif_fc=Decimal("100.00"))
        gone = self.make_allotment(company)
        self.make_allotment_item(gone, self.make_item(licence, 2), cif_fc=Decimal("900.00"))

        gone.delete()
        section = summary.build_allotment_activity(_scope())

        self.assertEqual(section["total"], 1)
        self.assertEqual(section["totals"]["allotted_cif"], "100.00")
        self.assertFalse(any(r["id"] == gone.pk for r in section["recent"]))

    def test_a_row_lists_every_licence_behind_its_items_once(self):
        company = self.make_company()
        first = self.make_license(company)
        second = self.make_license(company)
        allotment = self.make_allotment(company)
        self.make_allotment_item(allotment, self.make_item(first, 1), cif_fc=Decimal("50.00"))
        self.make_allotment_item(allotment, self.make_item(first, 2), cif_fc=Decimal("50.00"))
        self.make_allotment_item(allotment, self.make_item(second, 1), cif_fc=Decimal("50.00"))

        row = _row(summary.build_allotment_activity(_scope()), allotment)

        self.assertEqual(row["licence_count"], 2)
        self.assertEqual(
            sorted(licence["license_number"] for licence in row["licences"]),
            sorted([first.license_number, second.license_number]),
        )

    def test_the_section_totals_reconcile_and_match_the_licence_side_engine(self):
        company = self.make_company()
        licence = self.make_license(company)
        item = self.make_item(licence, 1)
        plain = self.make_allotment(company)
        self.make_allotment_item(plain, item, cif_fc=Decimal("200.00"))
        linked = self.make_allotment(company)
        linked_item = self.make_allotment_item(linked, self.make_item(licence, 2), cif_fc=Decimal("300.00"))
        boe = self.make_boe(company, number="BOE-RECON")
        debit = self.make_debit_row(boe, linked_item.item, cif_fc=Decimal("120.00"))
        self.link_boe(linked, boe)
        self.allocate(boe, linked_item, cif="120.00", qty="120.000", debit_row=debit)

        section = summary.build_allotment_activity(_scope())
        totals = {key: Decimal(value) for key, value in section["totals"].items()}

        self.assertEqual(totals["allotted_cif"], totals["consumed_cif"] + totals["reserved_cif"] + totals["not_reserved_cif"])
        self.assertEqual(totals["allotted_cif"], Decimal("500.00"))
        self.assertEqual(totals["consumed_cif"], Decimal("120.00"))
        self.assertEqual(totals["not_reserved_cif"], Decimal("180.00"))
        self.assertEqual(totals["reserved_cif"], Decimal("200.00"))
        licence_side = sum(C.calculate_allotment_for_licenses([licence.pk]).values(), Decimal(0))
        self.assertEqual(totals["reserved_cif"], licence_side.quantize(Decimal("0.01")),
                         "the allotment-side reservation must equal the licence-side engine total")

    def test_the_date_range_bounds_the_allotments_counted(self):
        company = self.make_company()
        licence = self.make_license(company)
        recent = self.make_allotment(company)
        self.make_allotment_item(recent, self.make_item(licence, 1), cif_fc=Decimal("10.00"))
        old = self.make_allotment(company)
        self.make_allotment_item(old, self.make_item(licence, 2), cif_fc=Decimal("20.00"))
        AllotmentModel.objects.filter(pk=old.pk).update(created_on=_days_ago(400))

        section = summary.build_allotment_activity(_scope(company=company, date_from=_days_ago(30).date()))

        self.assertEqual(section["total"], 1)
        self.assertEqual(section["recent"][0]["id"], recent.pk)

    def test_the_query_count_does_not_grow_with_the_number_of_allotments(self):
        def build(n):
            company = self.make_company()
            licence = self.make_license(company)
            for index in range(n):
                allotment = self.make_allotment(company)
                self.make_allotment_item(allotment, self.make_item(licence, index + 1), cif_fc=Decimal("10.00"))
                boe = self.make_boe(company, number=f"BOE-Q-{n}-{index}")
                self.link_boe(allotment, boe)
            with CaptureQueriesContext(connection) as queries:
                summary.build_allotment_activity(_scope(company=company))
            return len(queries.captured_queries)

        self.assertEqual(build(2), build(8))


def _days_ago(days):
    from django.utils import timezone

    return timezone.now() - timedelta(days=days)


class AllotmentContractTests(AllotmentFixtureMixin, TestCase):
    ROW_KEYS = {
        "id", "reference", "item_name", "company_name", "created_on", "licences", "licence_count",
        "original_quantity", "allocated_quantity", "unplaced_quantity", "allotted_cif", "consumed_cif", "reserved_cif",
        "not_reserved_cif", "remaining_quantity", "boe_count", "status",
    }

    def test_the_endpoint_returns_the_documented_row_and_totals_shape(self):
        from django.contrib.auth.models import Group
        from django.urls import reverse
        from rest_framework.test import APIClient

        company = self.make_company()
        licence = self.make_license(company)
        allotment = self.make_allotment(company)
        self.make_allotment_item(allotment, self.make_item(licence, 1), cif_fc=Decimal("100.00"))
        user = self.make_plain_user()
        user.groups.add(Group.objects.get_or_create(name="ALLOTMENT_VIEWER")[0])
        client = APIClient()
        client.force_authenticate(user=user)

        body = client.get(reverse("license:dashboard"), {"section": "allotment_activity"}).json()
        section = body["allotment_activity"]

        self.assertEqual(set(section["recent"][0].keys()), self.ROW_KEYS)
        self.assertEqual(set(section["totals"].keys()), {"allotted_cif", "consumed_cif", "reserved_cif", "not_reserved_cif"})
        self.assertEqual(set(section["counts"].keys()), {"open", "partly_consumed", "consumed", "boe_linked"})

    def test_a_partly_utilised_boe_linked_allotment_is_never_labelled_consumed(self):
        """Regression: the first version labelled this row 'consumed' because the engine reports zero reservation."""
        company = self.make_company()
        licence = self.make_license(company)
        item = self.make_item(licence, 1)
        allotment = self.make_allotment(company)
        allotted = self.make_allotment_item(allotment, item, cif_fc=Decimal("100.00"), qty=Decimal("100.000"))
        boe = self.make_boe(company, number="BOE-REGRESSION")
        debit = self.make_debit_row(boe, item, cif_fc=Decimal("40.00"))
        self.link_boe(allotment, boe)
        self.allocate(boe, allotted, cif="40.00", qty="40.000", debit_row=debit)

        row = _row(summary.build_allotment_activity(_scope()), allotment)

        self.assertNotEqual(row["status"], "consumed")
        self.assertEqual(row["status"], "partly_consumed")
