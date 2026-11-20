"""Product-wise Item Report (``reports/item-report/products/`` + drill-down + Excel), built on the Item Pivot engine.

Identity = Item Name x SION; every item (planned or not) is a product; totals equal the pivot's ``grand_total`` for the same
scope; every figure traces to BOE / allotment / invoice rows. Owner decisions D1-D3 (2026-11-20) apply through the engine.
"""
import io
from datetime import date, timedelta
from decimal import Decimal

import openpyxl
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT, GE
from apps.core.models import (CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, NotificationNumber, PurchaseStatus,
                              SionNormClassModel)
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services import item_report_products as service
from apps.license.services.item_report_products import METRIC_FIELDS
from apps.license.views.item_pivot_report import ItemPivotReportView
from apps.trade.models import LicenseTrade, LicenseTradeLine

URL = "/api/reports/item-report/products/"
DRILL = "/api/reports/item-report/products/drilldown/"
BASE = {"license_status": "all", "min_balance": "-1000000000", "norms": "E1"}


class ProductReportTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="prod-report", email="prod-report@example.com", password="RoleP@ssw0rd123")
        user.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
        self.company = CompanyModel.objects.create(iec="PRODREP1", name="Product Report Exporter")
        self.other_company = CompanyModel.objects.create(iec="PRODREP2", name="Product Report Other")
        self.status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
        head = HeadSIONNormsModel.objects.create(name="Product report")
        self.sion, _ = SionNormClassModel.objects.get_or_create(norm_class="E1", defaults={"head_norm": head, "is_active": True})
        self.pko = ItemNameModel.objects.create(name="PKO PRODTEST", sion_norm_class=self.sion)
        self.palm = ItemNameModel.objects.create(name="PALM KERNEL OIL PRODTEST", sion_norm_class=self.sion)
        self.whey = ItemNameModel.objects.create(name="WHEY PRODTEST", sion_norm_class=self.sion)
        self.hsn_oil, _ = HSCodeModel.objects.get_or_create(hs_code="15132110")
        self.hsn_whey, _ = HSCodeModel.objects.get_or_create(hs_code="04041000")
        self.l1 = self.licence("PRODREP-001", self.company)
        self.l2 = self.licence("PRODREP-002", self.other_company, notification="NOTIF/PROD")
        # L1: PKO planned (60 qty / 300 CIF), with a BOE and an outstanding allotment mapped to it
        self.pko_src = self.item(self.l1, 1, "Palm kernel oil refined", "100", "500", [self.pko], self.hsn_oil)
        LicenseItemPlan.objects.create(license=self.l1, import_item=self.pko_src, item_name=self.pko, planned_quantity=Decimal("60"),
                                       planned_cif_fc=Decimal("300"), allocation_provenance={"strategy": "STANDARD", "source_item_ids": [self.pko_src.pk], "sion": "E1"})
        self.pko_boe = self.debit(self.pko_src, "10", "50", target=self.pko, number="PRODBOE-1")
        self.pko_allot = self.allot(self.pko_src, "5", "25", target=self.pko)
        # a BOE mapped to an item this source does not plan -> NOT ATTRIBUTED (TARGET MISSING), reason target_not_planned
        self.missing_boe = self.debit(self.pko_src, "1", "5", target=self.whey, number="PRODBOE-2")
        # PALM KERNEL OIL: a different Item Name, unplanned, with a BOE
        self.palm_src = self.item(self.l1, 2, "PALM KERNEL OIL", "50", "250", [self.palm], self.hsn_oil)
        self.palm_boe = self.debit(self.palm_src, "4", "20", number="PRODBOE-3")
        # WHEY: unplanned; invoice (billed without BOE) of 2 / 10, plus an invoice that carries a BOE (never counted as billed)
        self.whey_src = self.item(self.l1, 3, "Whey powder", "30", "90", [self.whey], self.hsn_whey)
        self.invoice = self.sale_line(self.whey_src, "2", "10", "INV-PROD-1")
        covered = self.sale_line(self.whey_src, "7", "70", "INV-PROD-2")
        covered.trade.boes.add(BillOfEntryModel.objects.get(bill_of_entry_number="PRODBOE-3"))
        # an allotment already turned into a BOE is not outstanding: never counted twice
        netted = self.allot(self.palm_src, "9", "90")
        BillOfEntryModel.objects.get(bill_of_entry_number="PRODBOE-3").allotment.add(netted.allotment)
        # a source with no Item Name at all
        self.noname_src = self.item(self.l1, 4, "Mystery goods", "20", "60", [], self.hsn_whey)
        # L2: PKO unplanned on this licence, with a BOE
        self.pko_src2 = self.item(self.l2, 1, "PKO refined", "40", "200", [self.pko], self.hsn_oil)
        self.debit(self.pko_src2, "3", "15", number="PRODBOE-4")

    # -- builders ------------------------------------------------------------------------------------------------------
    def licence(self, number, company, notification=None):
        notif = NotificationNumber.objects.get_or_create(code=notification, defaults={"label": notification})[0] if notification else None
        lic = LicenseDetailsModel.objects.create(license_number=number, license_date=date.today() - timedelta(days=1),
                                                 license_expiry_date=date.today() + timedelta(days=60), exporter=company,
                                                 purchase_status=self.status, notification_number=notif)
        LicenseExportItemModel.objects.create(license=lic, norm_class=self.sion, cif_fc=Decimal("10000"))
        return lic

    def item(self, lic, serial, description, qty, cif, names, hsn):
        row = LicenseImportItemsModel.objects.create(license=lic, serial_number=serial, hs_code=hsn, description=description, quantity=Decimal(qty),
                                                     available_quantity=Decimal(qty), cif_fc=Decimal(cif))
        row.items.set(names)
        return row

    def debit(self, item, qty, cif, target=None, number="PRODBOE"):
        boe = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number=number, bill_of_entry_date=date(2026, 1, 5),
                                              exchange_rate=Decimal("80"), product_name="X")
        BillOfEntryModel.objects.filter(pk=boe.pk).update(planning_target_item=target, planning_mapping_status="MAPPED_EXPLICIT" if target else "UNMAPPED_AMBIGUOUS")
        return RowDetails.objects.create(bill_of_entry=boe, sr_number=item, transaction_type=DEBIT, qty=Decimal(qty), cif_fc=Decimal(cif), cif_inr=Decimal(cif) * 80)

    def allot(self, item, qty, cif, target=None):
        allotment = AllotmentModel.objects.create(company=self.company, item_name="ALLOT", required_quantity=Decimal(qty), invoice="ALLOT-REF")
        AllotmentModel.objects.filter(pk=allotment.pk).update(planning_target_item=target, planning_mapping_status="MAPPED_EXPLICIT" if target else "UNMAPPED_AMBIGUOUS")
        return AllotmentItems.objects.create(allotment=allotment, item=item, qty=Decimal(qty), cif_fc=Decimal(cif), cif_inr=Decimal(cif) * 80)

    def sale_line(self, item, qty, cif, number):
        trade = LicenseTrade.objects.create(direction=LicenseTrade.DIR_SALE, from_company=self.company, invoice_number=number, invoice_date=date(2026, 2, 1))
        return LicenseTradeLine.objects.create(trade=trade, sr_number=item, description="sale", mode=LicenseTradeLine.MODE_CIF_INR,
                                               cif_fc=Decimal(cif), cif_inr=Decimal(cif) * 80, qty_kg=Decimal(qty))

    def get(self, **params):
        response = self.client.get(URL, {**BASE, **params})
        assert response.status_code == 200, response.content
        return response.json()

    def product(self, data, name):
        return next(p for p in data["products"] if p["item_name"] == name)

    # -- identity ------------------------------------------------------------------------------------------------------
    def test_pko_and_palm_kernel_oil_stay_separate_rows(self):
        data = self.get()
        names = {p["item_name"] for p in data["products"]}
        assert {"PKO PRODTEST", "PALM KERNEL OIL PRODTEST"} <= names
        assert self.product(data, "PKO PRODTEST")["canonical_item_id"] == self.pko.pk != self.product(data, "PALM KERNEL OIL PRODTEST")["canonical_item_id"]
        assert len({p["key"] for p in data["products"]}) == len(data["products"])

    def test_every_item_is_a_product_and_unattributed_rows_are_included(self):
        data = self.get()
        assert not self.product(data, "WHEY PRODTEST")["is_planned"] and self.product(data, "PKO PRODTEST")["is_planned"]
        assert not self.product(data, "PALM KERNEL OIL PRODTEST")["is_planned"]
        names = {p["item_name"] for p in data["products"]}
        assert service.NO_ITEM_NAME_CATEGORY in names and "NOT ATTRIBUTED (TARGET MISSING)" in names
        assert data["planning_counts"] == {"all": len(data["products"]), "planned": 1, "unplanned": len(data["products"]) - 1}

    def test_metric_sources_and_no_double_counting(self):
        data = self.get()
        pko = self.product(data, "PKO PRODTEST")
        assert (pko["debited_qty"], pko["debited_cif"]) == ("13.000", "65.00")  # L1 mapped BOE 10/50 + L2 3/15, each once; the target-missing BOE is not here
        assert (pko["allotted_qty"], pko["allotted_cif"]) == ("5.000", "25.00")
        assert (pko["planned_qty"], pko["planned_cif"]) == ("60.000", "300.00")
        assert pko["license_count"] == 2
        whey = self.product(data, "WHEY PRODTEST")
        assert (whey["invoice_qty"], whey["invoice_cif"]) == ("2.000", "10.00")  # the invoice carrying a BOE is not billed-without-BOE
        assert whey["debited_cif"] == "0.00" and whey["allotted_cif"] == "0.00"
        assert self.product(data, "PALM KERNEL OIL PRODTEST")["debited_cif"] == "20.00"

    def test_zero_is_preserved_and_missing_is_null(self):
        data = self.get()
        missing = self.product(data, "NOT ATTRIBUTED (TARGET MISSING)")
        assert missing["total_cif"] is None and missing["balance_cif"] is None  # never invented
        assert missing["debited_cif"] == "5.00" and missing["planned_cif"] == "0.00"
        whey = self.product(data, "WHEY PRODTEST")
        assert whey["total_cif"] == "90.00" and whey["balance_cif"] is not None
        assert whey["allotted_qty"] == "0.000"  # zero, not null

    # -- filters -------------------------------------------------------------------------------------------------------
    def test_filters(self):
        base = {p["key"] for p in self.get()["products"]}
        assert self.get(norms="NO-SUCH-NORM")["products"] == []
        only_pko = self.get(item_names=str(self.pko.pk))
        assert [p["item_name"] for p in only_pko["products"]] == ["PKO PRODTEST"]
        assert {p["item_name"] for p in self.get(hsn_code="0404")["products"]} >= {"WHEY PRODTEST"}
        assert all(any("0404" in h for h in p["hsn_codes"]) for p in self.get(hsn_code="0404")["products"])
        one = self.get(license_numbers="PRODREP-002")
        assert one["scope"]["licence_count"] == 1 and [p["item_name"] for p in one["products"]] == ["PKO PRODTEST"]
        assert one["products"][0]["debited_cif"] == "15.00" and one["products"][0]["is_planned"] is False
        assert self.get(notification_numbers="NOTIF/PROD")["scope"]["licence_count"] == 1
        assert self.get(exclude_company_ids=str(self.other_company.pk))["scope"]["licence_count"] == 1
        assert self.get(company_ids=str(self.other_company.pk))["scope"]["licence_count"] == 1
        assert self.get(purchase_status="NOPE")["products"] == []
        assert self.get(expiry_date_to=(date.today() - timedelta(days=5)).isoformat())["products"] == []
        assert self.get(min_balance="999999999")["products"] == []
        planned, unplanned = self.get(planning_status="planned"), self.get(planning_status="unplanned")
        assert [p["item_name"] for p in planned["products"]] == ["PKO PRODTEST"]
        assert {p["key"] for p in unplanned["products"]} == base - {planned["products"][0]["key"]}
        assert planned["planning_counts"] == unplanned["planning_counts"] == self.get()["planning_counts"]  # counts ignore the status filter
        assert self.client.get(URL, {**BASE, "planning_status": "bogus"}).status_code == 400
        assert self.client.get(URL, {**BASE, "item_names": "x"}).status_code == 400
        assert self.client.get(DRILL, BASE).status_code == 400

    def test_permission_is_the_report_permission(self):
        assert APIClient().get(URL, BASE).status_code in (401, 403)

    # -- reconciliation with the pivot ---------------------------------------------------------------------------------
    def test_totals_equal_the_pivot_grand_total_for_the_same_scope(self):
        data = self.get()
        assert data["reconciliation"]["reconciled"]
        pivot = ItemPivotReportView().generate_report(min_balance=-10 ** 9, license_status="all", sion_norm="E1")["grand_total"]["item_summary_totals"]
        mine = data["totals"]
        for ours, theirs in (("total_qty", "total_qty"), ("allotted_qty", "allotted_qty"), ("allotted_cif", "allotted_cif"), ("debited_qty", "boe_used_qty"),
                             ("debited_cif", "boe_used_cif"), ("invoice_qty", "billed_qty"), ("invoice_cif", "billed_cif"), ("balance_qty", "available_qty"),
                             ("planned_qty", "planned_qty"), ("planned_cif", "planned_cif"), ("total_cif", "item_total_cif"), ("balance_cif", "capacity_balance_cif")):
            assert Decimal(mine[ours]) == Decimal(pivot[theirs]), ours
        assert set(data["reconciliation"]["metrics"]) == set(METRIC_FIELDS)
        assert all(m["difference"] == "0.00" or Decimal(m["difference"]) == 0 for m in data["reconciliation"]["metrics"].values())

    # -- drill-down ----------------------------------------------------------------------------------------------------
    def drill(self, product, **params):
        response = self.client.get(DRILL, {**BASE, "key": product["key"], **params})
        assert response.status_code == 200, response.content
        return response.json()

    def assert_traced(self, licence):
        def total(rows, field):
            return sum((Decimal(r[field]) for r in rows), Decimal("0"))
        assert total(licence["boes"], "qty") == Decimal(licence["debited_qty"]) and total(licence["boes"], "cif") == Decimal(licence["debited_cif"])
        assert total(licence["allotments"], "qty") == Decimal(licence["allotted_qty"]) and total(licence["allotments"], "cif") == Decimal(licence["allotted_cif"])
        assert total(licence["invoices"], "qty") == Decimal(licence["invoice_qty"]) and total(licence["invoices"], "cif") == Decimal(licence["invoice_cif"])

    def test_drilldown_traces_every_figure_to_its_rows(self):
        data = self.get()
        pko = self.product(data, "PKO PRODTEST")
        drill = self.drill(pko)
        assert drill["product"]["key"] == pko["key"]
        assert {l["license_number"] for l in drill["licences"]} == {"PRODREP-001", "PRODREP-002"}
        for licence in drill["licences"]:
            self.assert_traced(licence)
        l1 = next(l for l in drill["licences"] if l["license_number"] == "PRODREP-001")
        assert [(b["boe_id"], b["bill_of_entry_number"], b["row_id"], b["date"]) for b in l1["boes"]] == [(self.pko_boe.bill_of_entry_id, "PRODBOE-1", self.pko_boe.pk, "2026-01-05")]
        assert [(a["row_id"], a["reference"], a["outstanding"]) for a in l1["allotments"]] == [(self.pko_allot.pk, "ALLOT-REF", True)]
        assert l1["import_items"][0]["import_item_id"] == self.pko_src.pk and l1["import_items"][0]["total_cif"] == "500.00"
        # product figures = sum of its licences
        for metric in ("debited_cif", "allotted_cif", "invoice_cif"):
            assert sum(Decimal(l[metric]) for l in drill["licences"]) == Decimal(pko[metric])
        whey = self.drill(self.product(data, "WHEY PRODTEST"))["licences"][0]
        assert [(i["invoice_number"], Decimal(i["qty"]), i["cif"]) for i in whey["invoices"]] == [("INV-PROD-1", Decimal("2"), "10.00")]
        assert whey["invoices"][0]["line_id"] == self.invoice.pk and whey["invoices"][0]["date"] == "2026-02-01"
        self.assert_traced(whey)
        missing = self.drill(self.product(data, "NOT ATTRIBUTED (TARGET MISSING)"))["licences"][0]
        assert [b["row_id"] for b in missing["boes"]] == [self.missing_boe.pk] and missing["balance_cif"] is None
        self.assert_traced(missing)

    def test_every_product_of_the_report_is_fully_traced(self):
        data = self.get()
        for product in data["products"]:
            for licence in self.drill(product)["licences"]:
                self.assert_traced(licence)

    def test_drilldown_unknown_key_is_404(self):
        assert self.client.get(DRILL, {**BASE, "key": "0:E1"}).status_code == 404

    def test_d1_apportioned_rows_carry_their_share_in_the_drilldown(self):
        # owner decision D1 2026-11-20: two STANDARD plans on one source share an unmapped BOE by planned CIF, counted once
        lic = self.licence("PRODREP-003", self.company)
        src = self.item(lic, 1, "Shared oil", "100", "500", [self.pko, self.palm], self.hsn_oil)
        for target, cif in ((self.pko, "100"), (self.palm, "200")):
            LicenseItemPlan.objects.create(license=lic, import_item=src, item_name=target, planned_quantity=Decimal("10"), planned_cif_fc=Decimal(cif),
                                           allocation_provenance={"strategy": "STANDARD", "source_item_ids": [src.pk], "sion": "E1"})
        self.debit(src, "3", "100.00", number="PRODBOE-D1")
        data = self.get(license_numbers="PRODREP-003")
        pko, palm = self.product(data, "PKO PRODTEST"), self.product(data, "PALM KERNEL OIL PRODTEST")
        assert (pko["debited_cif"], palm["debited_cif"]) == ("33.33", "66.67")
        assert Decimal(data["totals"]["debited_cif"]) == Decimal("100.00")  # the row once in total
        pko_boe = self.drill(pko, license_numbers="PRODREP-003")["licences"][0]["boes"]
        palm_boe = self.drill(palm, license_numbers="PRODREP-003")["licences"][0]["boes"]
        assert [(b["cif"], b["qty"], b["share"]) for b in pko_boe] == [("33.33", "1.000", "0.333333")]
        assert [(b["cif"], b["qty"]) for b in palm_boe] == [("66.67", "2.000")]
        assert data["reconciliation"]["reconciled"]

    # -- excel ---------------------------------------------------------------------------------------------------------
    def test_excel_equals_json(self):
        data = self.get()
        response = self.client.get(URL, {**BASE, "_format": "excel"})
        assert response.status_code == 200 and "spreadsheetml" in response["Content-Type"]
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        assert wb.sheetnames == ["Products", "Licence detail"]
        ws = wb["Products"]
        rows = [[c.value for c in row] for row in ws.iter_rows(min_row=1)]
        assert [h for h in rows[0]] == [label for _f, label in service.PRODUCT_COLUMNS]
        body, total = rows[1:-1], rows[-1]
        assert len(body) == len(data["products"])
        for row, product in zip(body, data["products"]):
            for (field, _label), value in zip(service.PRODUCT_COLUMNS, row):
                expected = product[field]
                if field in ("hsn_codes", "units"):
                    expected = ", ".join(expected)
                if field in dict((n, k) for n, _s, k in service.METRICS) or field in ("license_count", "canonical_item_id"):
                    assert (value is None) == (expected is None), (product["key"], field)
                    if expected is not None:
                        assert Decimal(str(value)) == Decimal(str(expected)), (product["key"], field)
                else:
                    assert (value if value is not None else "") == (expected if expected is not None else ""), (product["key"], field)
        first_metric = [f for f, _ in service.PRODUCT_COLUMNS].index("total_qty")
        assert total[0] == "TOTAL" and str(total[first_metric]).startswith("=SUM(")
        # null totals stay empty; the totals row formulas cover exactly the data rows
        assert all(str(v).endswith(f"{1 + len(body)})") for v in total[first_metric:] if v is not None)
        for index, (field, _label) in enumerate(service.PRODUCT_COLUMNS):
            if field in data["totals"]:
                assert (total[index] is None) == (data["totals"][field] is None)
                if total[index] is not None:
                    column_sum = sum(Decimal(str(r[index])) for r in body if r[index] is not None)
                    assert column_sum == Decimal(data["totals"][field]), field
        detail = [[c.value for c in row] for row in wb["Licence detail"].iter_rows(min_row=2)]
        expected_detail = []
        for product in data["products"]:
            for licence in self.drill(product)["licences"]:
                for b in licence["boes"]:
                    expected_detail.append((product["key"], licence["license_number"], "BOE", b["bill_of_entry_number"], b["row_id"], Decimal(b["qty"]), Decimal(b["cif"])))
                for a in licence["allotments"]:
                    expected_detail.append((product["key"], licence["license_number"], "ALLOTMENT", a["reference"], a["row_id"], Decimal(a["qty"]), Decimal(a["cif"])))
                for i in licence["invoices"]:
                    expected_detail.append((product["key"], licence["license_number"], "INVOICE", i["invoice_number"], i["line_id"], Decimal(i["qty"]), Decimal(i["cif"])))
        got = [(r[0], r[3], r[4], r[5], r[7], Decimal(str(r[8])), Decimal(str(r[9]))) for r in detail]
        assert got == expected_detail
        assert any(isinstance(r[6], date) for r in detail if r[4] == "BOE")  # real date cells, not text

    # -- performance ---------------------------------------------------------------------------------------------------
    def test_query_count_does_not_grow_with_the_number_of_licences(self):
        with CaptureQueriesContext(connection) as small:
            self.get()
        import re, collections
        shape = lambda ctx: collections.Counter(re.sub(r"\d+", "N", q["sql"])[:120] for q in ctx.captured_queries)
        for n in range(4):
            lic = self.licence(f"PRODREP-Q{n}", self.company)
            src = self.item(lic, 1, "Extra", "10", "50", [self.pko], self.hsn_oil)
            self.debit(src, "1", "5", number=f"PRODBOE-Q{n}")
            self.sale_line(src, "1", "5", f"INV-Q{n}")
        with CaptureQueriesContext(connection) as large:
            self.get()
        grown = shape(large) - shape(small)
        # The only per-licence query is the pivot engine's pre-existing ``latest_transfer`` lookup (1 per licence, not introduced
        # here); the product report itself adds no per-licence / per-product / per-row query.
        assert all("licensetransfermodel" in sql for sql in grown), list(grown.items())
        assert len(large) <= len(small) + 4, (len(small), len(large), list(grown.items()))
        assert len(large) < 120
