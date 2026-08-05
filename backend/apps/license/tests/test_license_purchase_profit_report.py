"""
Tests for the License Purchase & Profit Report
(`apps.license.services.purchase_profit_report.build_purchase_profit_report`
and `apps.license.views.license_purchase_profit_report.LicensePurchaseProfitReportView`).

Covers:
- Purchase Cost consolidation across multiple `LicensePurchase` invoices.
- Item-wise allocation reconciling exactly to the license's allocated purchase.
- The decision-1/decision-2 asymmetry: Debited CIF is date-scoped, Purchase
  Cost never is.
- Hidden (previous-owner) BOE rows excluded from Debited CIF.
- Norm bucketing (exact / Others / no-norm-excluded / All).
- Item -> License -> Norm -> Grand Total reconciliation.
- View-level contract: JSON shape, Excel export, param validation, permissions.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from openpyxl import load_workbook
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.constants import DEBIT
from apps.core.models import CompanyModel, HSCodeModel, HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.bill_of_entry.models import BillOfEntryModel, OTH_INVOICE_MARKER, RowDetails
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.models.core import LicensePurchase
from apps.license.services.purchase_profit_report import build_purchase_profit_report

User = get_user_model()

REPORT_URL = "/api/reports/license-purchase-profit/"

FROM_DATE = date.today() - timedelta(days=30)
TO_DATE = date.today()
OUT_OF_RANGE_DATE = date.today() - timedelta(days=90)


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def report_viewer_client(db):
    user = User.objects.create_user(
        username="ppr-viewer",
        email="ppr-viewer@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="REPORT_VIEWER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def no_role_client(db):
    user = User.objects.create_user(
        username="ppr-norole",
        email="ppr-norole@example.com",
        password="RoleP@ssw0rd123",
    )
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


# ---------------------------------------------------------------------------
# Master-data / fixture builders
# ---------------------------------------------------------------------------

@pytest.fixture
def ppr_masters(db):
    head_norm = HeadSIONNormsModel.objects.create(name="PPR Test Head Norm")
    return {
        "exporter": CompanyModel.objects.create(iec="7770001111", name="PPR Exporter"),
        "hs_code": HSCodeModel.objects.create(hs_code="88888888", product_description="PPR Test Product"),
        "item_a": ItemNameModel.objects.create(name="PPR Item A"),
        "item_b": ItemNameModel.objects.create(name="PPR Item B"),
        "e1_norm": SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E1", is_active=True),
        "other_norm": SionNormClassModel.objects.create(head_norm=head_norm, norm_class="PPROTHER", is_active=True),
    }


def _make_license(number, exporter):
    return LicenseDetailsModel.objects.create(
        license_number=number,
        license_date=date.today() - timedelta(days=180),
        license_expiry_date=date.today() + timedelta(days=180),
        exporter=exporter,
    )


def _make_export_item(license_obj, norm_class, cif_fc):
    return LicenseExportItemModel.objects.create(
        license=license_obj,
        description=f"Export item for {license_obj.license_number}",
        norm_class=norm_class,
        cif_fc=cif_fc,
        cif_inr=cif_fc * Decimal("84.5"),
    )


def _make_import_item(license_obj, hs_code, serial, item_names=None, description=None):
    item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=serial,
        description=description or f"Import item {serial}",
        hs_code=hs_code,
        quantity=Decimal("1000.000"),
        available_quantity=Decimal("1000.000"),
    )
    if item_names:
        item.items.set(item_names)
    return item


def _make_purchase(license_obj, amount, invoice_date=None):
    """Uses MODE_QTY (qty=1 x rate=amount) so `amount_inr` == amount exactly,
    without fighting `LicensePurchase.save()`'s markup-based computation."""
    return LicensePurchase.objects.create(
        license=license_obj,
        mode=LicensePurchase.MODE_QTY,
        quantity_kg=Decimal("1.000"),
        rate_inr=Decimal(amount),
        invoice_date=invoice_date or date.today(),
    )


def _make_boe(company, boe_date, invoice_no=""):
    return BillOfEntryModel.objects.create(
        company=company,
        bill_of_entry_number=str(uuid.uuid4().int)[:9],
        bill_of_entry_date=boe_date,
        exchange_rate=Decimal("84.50"),
        invoice_no=invoice_no,
    )


def _make_debit_row(boe, item, cif_fc, qty):
    return RowDetails.objects.create(
        bill_of_entry=boe,
        sr_number=item,
        transaction_type=DEBIT,
        cif_fc=cif_fc,
        cif_inr=cif_fc * Decimal("84.5"),
        qty=qty,
    )


def _hide_boe(boe):
    """Mirrors the real hide flow's audit trail — see
    `test_balance_calculator.py::TestHiddenBoeExclusion._make_boe`'s own
    comment: a BOE only counts as genuinely hidden if a `ReconciliationLog`
    entry confirms a real hide, not merely `invoice_no == OTH_INVOICE_MARKER`
    colliding with unrelated legacy free-text data."""
    from apps.reconciliation.models import ReconciliationLog

    ReconciliationLog.objects.create(
        action=ReconciliationLog.ACTION_HIDE_BOE,
        bill_of_entry=boe,
        before={"is_hidden": False, "invoice_no": ""},
        after={"is_hidden": True, "bill_of_entry_number": boe.bill_of_entry_number},
    )


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_single_license_single_invoice_single_item_profit(ppr_masters):
    lic = _make_license("PPR-001", ppr_masters["exporter"])
    _make_export_item(lic, ppr_masters["e1_norm"], Decimal("95000.00"))
    item = _make_import_item(lic, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])
    _make_purchase(lic, "60000.00")
    boe = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe, item, Decimal("90000.00"), Decimal("500.000"))

    report = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="All")

    e1 = next(n for n in report["norms"] if n["norm"] == "E1")
    lic_row = e1["licenses"][0]
    assert lic_row["license_number"] == "PPR-001"
    assert lic_row["purchase_cost"] == 60000.00
    assert lic_row["debited_cif"] == 90000.00
    assert lic_row["remaining_cif"] == 5000.00  # 95000 export credit - 90000 all-time BOE debit
    assert lic_row["allocated_purchase"] == 60000.00
    assert lic_row["realized_profit"] == 30000.00
    assert lic_row["profit_pct"] == 50.00

    assert len(e1["items"]) == 1
    item_row = e1["items"][0]
    assert item_row["debited_cif"] == 90000.00
    assert item_row["allocated_purchase"] == 60000.00
    assert item_row["profit"] == 30000.00
    assert item_row["pct_share"] == 100.00
    assert item_row["item"] == "PPR Item A"


@pytest.mark.django_db
def test_multiple_invoices_consolidate_to_one_purchase_cost(ppr_masters):
    """Core acceptance criterion: one license, many supplier invoices ->
    one Purchase Cost row, consolidated to their sum."""
    lic = _make_license("PPR-002", ppr_masters["exporter"])
    _make_export_item(lic, ppr_masters["e1_norm"], Decimal("50000.00"))
    item = _make_import_item(lic, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])
    _make_purchase(lic, "20000.00", invoice_date=date.today() - timedelta(days=200))
    _make_purchase(lic, "15000.00", invoice_date=date.today() - timedelta(days=100))
    _make_purchase(lic, "5000.00", invoice_date=date.today() - timedelta(days=10))
    boe = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe, item, Decimal("30000.00"), Decimal("100.000"))

    report = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="All")

    e1 = next(n for n in report["norms"] if n["norm"] == "E1")
    lic_row = next(r for r in e1["licenses"] if r["license_number"] == "PPR-002")
    assert lic_row["purchase_cost"] == 40000.00  # 20000 + 15000 + 5000


@pytest.mark.django_db
def test_multi_item_allocation_sums_exactly_to_license_allocated_purchase(ppr_masters):
    lic = _make_license("PPR-003", ppr_masters["exporter"])
    _make_export_item(lic, ppr_masters["e1_norm"], Decimal("200000.00"))
    item1 = _make_import_item(lic, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])
    item2 = _make_import_item(lic, ppr_masters["hs_code"], 2, item_names=[ppr_masters["item_b"]])
    _make_purchase(lic, "77777.00")  # deliberately awkward number to exercise rounding
    boe = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe, item1, Decimal("45000.00"), Decimal("300.000"))
    _make_debit_row(boe, item2, Decimal("30000.00"), Decimal("200.000"))

    report = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="All")

    e1 = next(n for n in report["norms"] if n["norm"] == "E1")
    lic_row = next(r for r in e1["licenses"] if r["license_number"] == "PPR-003")
    items = [it for it in e1["items"] if it["license_number"] == "PPR-003"]
    assert len(items) == 2

    total_allocated = sum(Decimal(str(it["allocated_purchase"])) for it in items)
    assert total_allocated == Decimal(str(lic_row["allocated_purchase"]))
    assert total_allocated == Decimal("77777.00")

    total_item_profit = sum(Decimal(str(it["profit"])) for it in items)
    assert total_item_profit == Decimal(str(lic_row["realized_profit"]))


@pytest.mark.django_db
def test_date_range_excludes_out_of_range_debit_but_not_purchase_cost(ppr_masters):
    """Decision-2 (Debited CIF is date-scoped) vs decision-1 (Purchase Cost
    is never date-scoped) asymmetry, tested explicitly."""
    lic = _make_license("PPR-004", ppr_masters["exporter"])
    _make_export_item(lic, ppr_masters["e1_norm"], Decimal("100000.00"))
    item = _make_import_item(lic, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])

    # Purchase invoice dated LONG before the report's date range.
    _make_purchase(lic, "40000.00", invoice_date=OUT_OF_RANGE_DATE - timedelta(days=365))

    in_range_boe = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(in_range_boe, item, Decimal("25000.00"), Decimal("100.000"))

    out_of_range_boe = _make_boe(ppr_masters["exporter"], OUT_OF_RANGE_DATE)
    _make_debit_row(out_of_range_boe, item, Decimal("10000.00"), Decimal("50.000"))

    report = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="All")

    e1 = next(n for n in report["norms"] if n["norm"] == "E1")
    lic_row = next(r for r in e1["licenses"] if r["license_number"] == "PPR-004")
    # Debited CIF only counts the in-range row.
    assert lic_row["debited_cif"] == 25000.00
    # Purchase Cost counts the invoice regardless of its own (out-of-range) date.
    assert lic_row["purchase_cost"] == 40000.00


@pytest.mark.django_db
def test_hidden_boe_row_excluded_from_debited_cif(ppr_masters):
    lic = _make_license("PPR-005", ppr_masters["exporter"])
    _make_export_item(lic, ppr_masters["e1_norm"], Decimal("100000.00"))
    item = _make_import_item(lic, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])
    _make_purchase(lic, "10000.00")

    hidden_boe = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1), invoice_no=OTH_INVOICE_MARKER)
    _hide_boe(hidden_boe)
    _make_debit_row(hidden_boe, item, Decimal("50000.00"), Decimal("400.000"))

    visible_boe = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=2))
    _make_debit_row(visible_boe, item, Decimal("15000.00"), Decimal("100.000"))

    report = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="All")

    e1 = next(n for n in report["norms"] if n["norm"] == "E1")
    lic_row = next(r for r in e1["licenses"] if r["license_number"] == "PPR-005")
    # Only the visible row's 15000.00 counts — the hidden row's 50000.00 must
    # be dropped, not merely coincidentally not double-counted.
    assert lic_row["debited_cif"] == 15000.00


@pytest.mark.django_db
def test_norm_bucketing_exact_others_and_no_norm_exclusion(ppr_masters):
    # E1 exact match.
    lic_e1 = _make_license("PPR-NORM-E1", ppr_masters["exporter"])
    _make_export_item(lic_e1, ppr_masters["e1_norm"], Decimal("50000.00"))
    item_e1 = _make_import_item(lic_e1, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])
    _make_purchase(lic_e1, "10000.00")
    boe_e1 = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe_e1, item_e1, Decimal("20000.00"), Decimal("100.000"))

    # A norm_class outside CONVERSION_NORMS -> "Others" catch-all.
    lic_other = _make_license("PPR-NORM-OTHER", ppr_masters["exporter"])
    _make_export_item(lic_other, ppr_masters["other_norm"], Decimal("50000.00"))
    item_other = _make_import_item(lic_other, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_b"]])
    _make_purchase(lic_other, "10000.00")
    boe_other = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe_other, item_other, Decimal("20000.00"), Decimal("100.000"))

    # No norm_class at all -> out of scope, excluded entirely.
    lic_no_norm = _make_license("PPR-NORM-NONE", ppr_masters["exporter"])
    item_no_norm = _make_import_item(lic_no_norm, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])
    _make_purchase(lic_no_norm, "10000.00")
    boe_no_norm = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe_no_norm, item_no_norm, Decimal("20000.00"), Decimal("100.000"))

    all_report = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="All")
    all_license_numbers = {
        lic["license_number"] for n in all_report["norms"] for lic in n["licenses"]
    }
    assert "PPR-NORM-E1" in all_license_numbers
    assert "PPR-NORM-OTHER" in all_license_numbers
    assert "PPR-NORM-NONE" not in all_license_numbers

    e1_only = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="E1")
    e1_license_numbers = {
        lic["license_number"] for n in e1_only["norms"] for lic in n["licenses"]
    }
    assert e1_license_numbers == {"PPR-NORM-E1"}

    others_only = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="Others")
    others_license_numbers = {
        lic["license_number"] for n in others_only["norms"] for lic in n["licenses"]
    }
    assert others_license_numbers == {"PPR-NORM-OTHER"}


@pytest.mark.django_db
def test_multi_norm_license_buckets_under_active_filter_not_arbitrary_pick(ppr_masters):
    """A license with export items spanning two distinct norm_class values
    (E1 and an "Others" norm) must land in whichever norm section the
    request actually asked for -- not an arbitrary/DB-order-dependent pick
    that could contradict the `norm` filter that put it in scope."""
    lic = _make_license("PPR-MULTI-NORM", ppr_masters["exporter"])
    _make_export_item(lic, ppr_masters["e1_norm"], Decimal("50000.00"))
    _make_export_item(lic, ppr_masters["other_norm"], Decimal("50000.00"))
    item = _make_import_item(lic, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])
    _make_purchase(lic, "10000.00")
    boe = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe, item, Decimal("20000.00"), Decimal("100.000"))

    e1_report = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="E1")
    e1_norms_present = {n["norm"] for n in e1_report["norms"] if n["licenses"]}
    assert e1_norms_present == {"E1"}
    assert {lic_row["license_number"] for n in e1_report["norms"] for lic_row in n["licenses"]} == {"PPR-MULTI-NORM"}

    # norm="Others" uses an exclusion filter (`.exclude(norm_class__in=CONVERSION_NORMS)`),
    # so a license that also carries an E1 export item is out of scope for "Others"
    # entirely -- it isn't "purely other". That exclusion happens upstream in
    # `_base_license_queryset`, before bucketing ever runs.
    others_report = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="Others")
    others_license_numbers = {
        lic_row["license_number"] for n in others_report["norms"] for lic_row in n["licenses"]
    }
    assert "PPR-MULTI-NORM" not in others_license_numbers

    # "All": deterministic precedence (NORM_DISPLAY_ORDER) picks E1 over
    # Others for this license, and it appears in exactly one section, not both.
    all_report = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="All")
    sections_with_license = [
        n["norm"] for n in all_report["norms"]
        if "PPR-MULTI-NORM" in {lic_row["license_number"] for lic_row in n["licenses"]}
    ]
    assert sections_with_license == ["E1"]


@pytest.mark.django_db
def test_grand_total_reconciles_with_per_norm_summaries(ppr_masters):
    lic_e1 = _make_license("PPR-GT-E1", ppr_masters["exporter"])
    _make_export_item(lic_e1, ppr_masters["e1_norm"], Decimal("80000.00"))
    item_e1 = _make_import_item(lic_e1, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])
    _make_purchase(lic_e1, "30000.00")
    boe_e1 = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe_e1, item_e1, Decimal("40000.00"), Decimal("100.000"))

    lic_other = _make_license("PPR-GT-OTHER", ppr_masters["exporter"])
    _make_export_item(lic_other, ppr_masters["other_norm"], Decimal("60000.00"))
    item_other = _make_import_item(lic_other, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_b"]])
    _make_purchase(lic_other, "20000.00")
    boe_other = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe_other, item_other, Decimal("35000.00"), Decimal("100.000"))

    report = build_purchase_profit_report(FROM_DATE, TO_DATE, norm="All")

    sum_purchase = sum(Decimal(str(n["summary"]["total_purchase"])) for n in report["norms"])
    sum_debited = sum(Decimal(str(n["summary"]["total_debited_cif"])) for n in report["norms"])
    sum_profit = sum(Decimal(str(n["summary"]["total_profit"])) for n in report["norms"])

    grand_total = report["grand_summary"]["total"]
    assert sum_purchase == Decimal(str(grand_total["purchase"]))
    assert sum_debited == Decimal(str(grand_total["debited_cif"]))
    assert sum_profit == Decimal(str(grand_total["profit"]))

    # Also reconcile against the grand_summary rows list itself.
    rows_purchase = sum(Decimal(str(r["purchase"])) for r in report["grand_summary"]["rows"])
    assert rows_purchase == Decimal(str(grand_total["purchase"]))


# ---------------------------------------------------------------------------
# View-level tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_view_json_response_has_expected_top_level_keys(report_viewer_client, ppr_masters):
    lic = _make_license("PPR-VIEW-001", ppr_masters["exporter"])
    _make_export_item(lic, ppr_masters["e1_norm"], Decimal("50000.00"))
    item = _make_import_item(lic, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])
    _make_purchase(lic, "10000.00")
    boe = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe, item, Decimal("20000.00"), Decimal("100.000"))

    response = report_viewer_client.get(
        REPORT_URL, {"from_date": FROM_DATE.isoformat(), "to_date": TO_DATE.isoformat()}
    )
    assert response.status_code == 200
    data = response.json()
    assert "norms" in data
    assert "grand_summary" in data
    assert "rows" in data["grand_summary"]
    assert "total" in data["grand_summary"]


@pytest.mark.django_db
def test_view_excel_export_returns_valid_workbook(report_viewer_client, ppr_masters):
    lic = _make_license("PPR-VIEW-002", ppr_masters["exporter"])
    _make_export_item(lic, ppr_masters["e1_norm"], Decimal("50000.00"))
    item = _make_import_item(lic, ppr_masters["hs_code"], 1, item_names=[ppr_masters["item_a"]])
    _make_purchase(lic, "10000.00")
    boe = _make_boe(ppr_masters["exporter"], FROM_DATE + timedelta(days=1))
    _make_debit_row(boe, item, Decimal("20000.00"), Decimal("100.000"))

    response = report_viewer_client.get(
        REPORT_URL,
        {"from_date": FROM_DATE.isoformat(), "to_date": TO_DATE.isoformat(), "format": "excel"},
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    workbook = load_workbook(BytesIO(response.content))
    assert "Purchase & Profit Report" in workbook.sheetnames


@pytest.mark.django_db
def test_view_missing_date_params_returns_400(report_viewer_client):
    response = report_viewer_client.get(REPORT_URL)
    assert response.status_code == 400

    response = report_viewer_client.get(REPORT_URL, {"from_date": FROM_DATE.isoformat()})
    assert response.status_code == 400


@pytest.mark.django_db
def test_view_invalid_date_format_returns_400(report_viewer_client):
    response = report_viewer_client.get(
        REPORT_URL, {"from_date": "01-01-2026", "to_date": "31-01-2026"}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_view_requires_report_permission(no_role_client):
    response = no_role_client.get(
        REPORT_URL, {"from_date": FROM_DATE.isoformat(), "to_date": TO_DATE.isoformat()}
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_view_unauthenticated_is_rejected():
    client = APIClient()
    response = client.get(
        REPORT_URL, {"from_date": FROM_DATE.isoformat(), "to_date": TO_DATE.isoformat()}
    )
    assert response.status_code in (401, 403)
