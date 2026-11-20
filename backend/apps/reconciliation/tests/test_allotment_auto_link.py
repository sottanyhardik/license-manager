"""SAT-DEF-150 / C-2: exact allotment<->BOE auto-link. Original CIF 100.00; values hand-computed."""
import io
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin
from apps.bill_of_entry.models import OTH_INVOICE_MARKER
from apps.reconciliation.models import ReconciliationLog
from apps.reconciliation.services.allotment_auto_link import (
    apply_exact_links,
    reverse_batch,
    review_candidates,
)

D = Decimal


class AutoLinkTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.lic = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=self.lic, cif_fc=D("100.00"))
        self.item = self.make_item(self.lic, 1)
        self.item2 = self.make_item(self.lic, 2)

    def allot(self, specs, company=None):
        a = AllotmentModel.objects.create(company=company or self.company, item_name="C2", type="AT")
        for item, cif, qty in specs:
            AllotmentItems.objects.create(item=item, allotment=a, cif_fc=cif, cif_inr=cif * D("84.5"), qty=qty)
        return a

    def boe_with(self, specs, **kw):
        boe = self.make_boe(kw.pop("company", self.company), **kw)
        for item, cif, qty in specs:
            self.make_debit_row(boe, item, cif, qty)
        return boe

    def bal(self):
        return LBC.calculate_balance(self.lic)

    def apply(self):
        return apply_exact_links([self.lic.id], dry_run=False)

    def test_single_exact_links_and_stops_double_count(self):
        a = self.allot([(self.item, D("30.00"), D("10.000"))])
        boe = self.boe_with([(self.item, D("30.00"), D("10.000"))])
        before = self.bal()
        self.assertEqual(before, D("40.00"))  # 100 - 30 debit - 30 allotment
        res = self.apply()
        self.assertEqual(len(res["linked"]), 1)
        self.assertTrue(boe.allotment.filter(pk=a.pk).exists())
        a.refresh_from_db()
        self.assertTrue(a.is_boe)
        self.assertEqual(self.bal(), D("70.00"))
        log = ReconciliationLog.objects.get(action="AUTO_LINK_ALLOTMENT")
        self.assertEqual(log.bill_of_entry_id, boe.id)
        self.assertEqual(log.before, {"is_boe": False})
        self.assertEqual(log.after["batch_id"], res["batch_id"])
        self.assertEqual(log.after["match"], "EXACT")
        self.assertIn("SAT-DEF-150 / C-2", log.reason)

    def test_multi_item_exact(self):
        a = self.allot([(self.item, D("10.00"), D("1.000")), (self.item2, D("20.00"), D("2.000"))])
        boe = self.boe_with([(self.item, D("10.00"), D("1.000")), (self.item2, D("20.00"), D("2.000"))])
        self.apply()
        self.assertTrue(boe.allotment.filter(pk=a.pk).exists())
        self.assertEqual(self.bal(), D("70.00"))

    def test_qty_diff_review_not_linked(self):
        a = self.allot([(self.item, D("30.00"), D("10.000"))])
        boe = self.boe_with([(self.item, D("30.00"), D("9.000"))])
        self.assertEqual(self.apply()["linked"], [])
        self.assertFalse(boe.allotment.exists())
        r = review_candidates([self.lic.id])
        self.assertEqual([(x["allotment_id"], x["boe_id"], x["reason"]) for x in r], [(a.id, boe.id, "QTY_DIFF")])
        self.assertEqual(r[0]["qty_delta"], D("-1.000"))

    def test_cif_diff_review(self):
        self.allot([(self.item, D("30.00"), D("10.000"))])
        boe = self.boe_with([(self.item, D("25.00"), D("10.000"))])
        self.assertEqual(self.apply()["linked"], [])
        r = review_candidates([self.lic.id])
        self.assertEqual(r[0]["reason"], "CIF_DIFF")
        self.assertEqual(r[0]["cif_delta"], D("-5.00"))
        self.assertFalse(boe.allotment.exists())

    def test_partial_items_review(self):
        self.allot([(self.item, D("10.00"), D("1.000")), (self.item2, D("20.00"), D("2.000"))])
        self.boe_with([(self.item, D("10.00"), D("1.000"))])
        self.assertEqual(self.apply()["linked"], [])
        self.assertEqual(review_candidates([self.lic.id])[0]["reason"], "PARTIAL_ITEMS")

    def test_different_company_no_candidate(self):
        self.allot([(self.item, D("30.00"), D("10.000"))])
        self.boe_with([(self.item, D("30.00"), D("10.000"))], company=self.make_company("Other"))
        self.assertEqual(self.apply()["linked"], [])
        self.assertEqual(review_candidates([self.lic.id]), [])

    def test_hidden_boe_no_candidate(self):
        self.allot([(self.item, D("30.00"), D("10.000"))])
        self.boe_with([(self.item, D("30.00"), D("10.000"))], invoice_no=OTH_INVOICE_MARKER)
        self.assertEqual(self.apply()["linked"], [])
        self.assertEqual(review_candidates([self.lic.id]), [])

    def test_already_linked_boe_skipped(self):
        other = self.allot([(self.item, D("30.00"), D("10.000"))])
        boe = self.boe_with([(self.item, D("30.00"), D("10.000"))])
        boe.allotment.add(other)
        self.allot([(self.item, D("30.00"), D("10.000"))])
        self.assertEqual(self.apply()["linked"], [])
        self.assertEqual(boe.allotment.count(), 1)

    def test_two_allotments_one_boe_ambiguous(self):
        a1 = self.allot([(self.item, D("30.00"), D("10.000"))])
        a2 = self.allot([(self.item, D("30.00"), D("10.000"))])
        boe = self.boe_with([(self.item, D("30.00"), D("10.000"))])
        self.assertEqual(self.apply()["linked"], [])
        r = review_candidates([self.lic.id])
        self.assertEqual({(x["allotment_id"], x["reason"]) for x in r}, {(a1.id, "AMBIGUOUS"), (a2.id, "AMBIGUOUS")})
        self.assertFalse(boe.allotment.exists())

    def test_sibling_item_review_never_linked(self):
        a = self.allot([(self.item, D("30.00"), D("10.000"))])
        boe = self.boe_with([(self.item2, D("30.00"), D("10.000"))])
        self.assertEqual(self.apply()["linked"], [])
        r = review_candidates([self.lic.id])
        self.assertEqual([(x["allotment_id"], x["boe_id"], x["reason"]) for x in r], [(a.id, boe.id, "SIBLING_ITEM")])
        self.assertFalse(boe.allotment.exists())

    def test_dry_run_writes_nothing(self):
        self.allot([(self.item, D("30.00"), D("10.000"))])
        boe = self.boe_with([(self.item, D("30.00"), D("10.000"))])
        res = apply_exact_links([self.lic.id])
        self.assertEqual(len(res["exact"]), 1)
        self.assertEqual(res["linked"], [])
        self.assertFalse(boe.allotment.exists())
        self.assertFalse(ReconciliationLog.objects.filter(action="AUTO_LINK_ALLOTMENT").exists())

    def test_reverse_batch_and_idempotence(self):
        a = self.allot([(self.item, D("30.00"), D("10.000"))])
        boe = self.boe_with([(self.item, D("30.00"), D("10.000"))])
        res = self.apply()
        self.assertEqual(self.bal(), D("70.00"))
        rev = reverse_batch(res["batch_id"])
        self.assertEqual(len(rev["reversed"]), 1)
        a.refresh_from_db()
        self.assertFalse(a.is_boe)
        self.assertFalse(boe.allotment.exists())
        self.assertEqual(self.bal(), D("40.00"))
        self.assertEqual(reverse_batch(res["batch_id"])["reversed"], [])
        self.assertEqual(ReconciliationLog.objects.filter(action="REVERSE_AUTO_LINK_ALLOTMENT").count(), 1)
        self.assertEqual(ReconciliationLog.objects.filter(action="AUTO_LINK_ALLOTMENT").count(), 1)

    def test_reapply_idempotent(self):
        self.allot([(self.item, D("30.00"), D("10.000"))])
        self.boe_with([(self.item, D("30.00"), D("10.000"))])
        self.apply()
        self.assertEqual(self.apply()["linked"], [])
        self.assertEqual(ReconciliationLog.objects.filter(action="AUTO_LINK_ALLOTMENT").count(), 1)

    @override_settings(ALLOTMENT_AUTO_LINK_ON_BOE=True)
    def test_signal_links_on_row_creation(self):
        a = self.allot([(self.item, D("30.00"), D("10.000"))])
        with self.captureOnCommitCallbacks(execute=True):
            boe = self.boe_with([(self.item, D("30.00"), D("10.000"))])
        self.assertTrue(boe.allotment.filter(pk=a.pk).exists())

    def test_signal_off_by_default(self):
        # Audit F6: OFF until the owner approves the C-2 data-repair run.
        self.allot([(self.item, D("30.00"), D("10.000"))])
        with self.captureOnCommitCallbacks(execute=True):
            boe = self.boe_with([(self.item, D("30.00"), D("10.000"))])
        self.assertFalse(boe.allotment.exists())

    def test_command_dry_run_default_and_csv(self):
        import os
        import tempfile

        self.allot([(self.item, D("30.00"), D("10.000"))])
        boe = self.boe_with([(self.item, D("30.00"), D("10.000"))])
        path = os.path.join(tempfile.mkdtemp(), "out.csv")
        out = io.StringIO()
        call_command("auto_link_allotments", license_ids=str(self.lic.id), csv=path, stdout=out)
        self.assertIn("DRY-RUN", out.getvalue())
        self.assertFalse(boe.allotment.exists())
        self.assertIn("EXACT", open(path).read())

    def test_boe_row_already_formally_allocated_is_never_auto_linked(self):
        """Audit F1: allotment B is formally allocated to BOE X's row; a
        duplicate allotment A (same item/qty/CIF/company) must NOT be released
        by auto-linking it to X."""
        from apps.reconciliation.services.allocation_service import create_boe_allotment_allocation

        b = self.allot([(self.item, D("30.00"), D("10.000"))])
        boe = self.boe_with([(self.item, D("30.00"), D("10.000"))])
        row = boe.item_details.get()
        create_boe_allotment_allocation(
            row, b.allotment_details.get(), qty=D("10.000"), cif_fc=D("30.00"), cif_inr=D("2535.00"), user=None,
        )
        a = self.allot([(self.item, D("30.00"), D("10.000"))])
        before = self.bal()
        res = self.apply()
        self.assertEqual(res["linked"], [])
        self.assertFalse(boe.allotment.filter(pk=a.pk).exists())
        self.assertEqual(self.bal(), before)
