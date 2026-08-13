"""
License Ledger — TRANSACTION DISPLAY RULE

Covers the display rule implemented once in
`apps.license.domain.transaction_semantics.select_display_rows`:

    * Only PURCHASE and SALE are shown as ordinary transaction rows.
    * OPENING is shown ONLY when no PURCHASE exists, and then only as the
      starting-state row — never as an ordinary transaction.

    | PURCHASE | SALE | OPENING | displayed              |
    |----------|------|---------|------------------------|
    | yes      | yes  | yes     | PURCHASE + SALE        |
    | yes      | no   | yes     | PURCHASE               |
    | no       | yes  | yes     | OPENING (state) + SALE |
    | no       | no   | yes     | OPENING (state)        |
    | no       | no   | no      | nothing (empty state)  |

The matrix is expressed ONCE (`DISPLAY_MATRIX`) and driven three ways — the
pure classifier, the canonical dataset, and the HTTP API — rather than being
retyped per case.

Financial safety is asserted explicitly: the display rule must not move
opening_balance, running/closing balance or any total, and `transactions` must
keep the full financial record (including OPENING) even when it is not displayed.
"""

from decimal import Decimal
from datetime import date

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

from apps.license.domain.transaction_semantics import (
    DISPLAY_ROW_TYPES,
    OPENING_ROW_TYPE,
    PURCHASE_PRESENCE_TYPES,
    select_display_rows,
)
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.tests.test_canonical_ledger_service import (
    CanonicalLedgerServiceTestBase,
)


# ── The matrix, declared once ────────────────────────────────────────────────
# (case id, has_purchase, has_sale, has_opening, expected displayed types,
#  expect_opening_state)
DISPLAY_MATRIX = [
    ("purchase+sale", True, True, True, ["PURCHASE", "SALE"], False),
    ("purchase_only", True, False, True, ["PURCHASE"], False),
    ("opening+sale", False, True, True, ["SALE"], True),
    ("opening_only", False, False, True, [], True),
    ("empty", False, False, False, [], False),
]

OPENING_AMOUNT = Decimal("65380.63")
PURCHASE_AMOUNT = Decimal("1000.00")
SALE_AMOUNT = Decimal("250.00")


def _txn(txn_type, txn_id, amount="100.00"):
    """Minimal canonical-shaped transaction row."""
    return {
        "type": txn_type,
        "id": txn_id,
        "amount": Decimal(amount),
        "company_id": None if txn_type == OPENING_ROW_TYPE else 1,
    }


# ── 1. The pure classifier (no database) ─────────────────────────────────────

@pytest.mark.parametrize(
    "case_id,has_purchase,has_sale,has_opening,expected_types,expect_opening",
    DISPLAY_MATRIX,
    ids=[row[0] for row in DISPLAY_MATRIX],
)
def test_classifier_matrix(
    case_id, has_purchase, has_sale, has_opening, expected_types, expect_opening
):
    rows = []
    if has_opening:
        rows.append(_txn(OPENING_ROW_TYPE, 0, OPENING_AMOUNT))
    if has_purchase:
        rows.append(_txn("PURCHASE", 1, PURCHASE_AMOUNT))
    if has_sale:
        rows.append(_txn("SALE", 2, SALE_AMOUNT))

    result = select_display_rows(rows)

    assert [t["type"] for t in result["display_transactions"]] == expected_types
    assert (result["opening_row"] is not None) is expect_opening
    if expect_opening:
        assert result["opening_row"]["type"] == OPENING_ROW_TYPE


def test_classifier_never_puts_opening_in_display_rows():
    """OPENING is never an ordinary row, even when it is displayed."""
    rows = [_txn(OPENING_ROW_TYPE, 0), _txn("SALE", 2)]
    result = select_display_rows(rows)

    assert OPENING_ROW_TYPE not in [t["type"] for t in result["display_transactions"]]
    assert result["opening_row"] is not None


@pytest.mark.parametrize("commission_type", ["COMMISSION", "COMMISSION_PURCHASE", "COMMISSION_SALE"])
def test_classifier_excludes_commission_types(commission_type):
    """Only PURCHASE and SALE are displayed."""
    rows = [_txn("PURCHASE", 1), _txn(commission_type, 3), _txn("SALE", 2)]
    result = select_display_rows(rows)
    assert [t["type"] for t in result["display_transactions"]] == ["PURCHASE", "SALE"]


def test_commission_purchase_does_not_suppress_opening():
    """A commission purchase is non-balance-affecting, so it cannot stand in
    for the licence's opening position."""
    rows = [_txn(OPENING_ROW_TYPE, 0), _txn("COMMISSION_PURCHASE", 3)]
    result = select_display_rows(rows)

    assert "COMMISSION_PURCHASE" not in PURCHASE_PRESENCE_TYPES
    assert result["opening_row"] is not None


def test_classifier_preserves_input_order_and_does_not_duplicate():
    rows = [
        _txn(OPENING_ROW_TYPE, 0),
        _txn("PURCHASE", 1),
        _txn("SALE", 2),
        _txn("SALE", 3),
        _txn("SALE", 4),
    ]
    result = select_display_rows(rows)
    ids = [t["id"] for t in result["display_transactions"]]

    assert ids == [1, 2, 3, 4]          # chronological order preserved
    assert len(ids) == len(set(ids))    # no duplicate rows


def test_classifier_handles_empty_and_none():
    for empty in ([], None):
        result = select_display_rows(empty)
        assert result["display_transactions"] == []
        assert result["opening_row"] is None


def test_display_row_types_constant_is_exactly_purchase_and_sale():
    assert set(DISPLAY_ROW_TYPES) == {"PURCHASE", "SALE"}


# ── 2. Through the canonical dataset + HTTP API ──────────────────────────────

class LedgerDisplayRuleIntegrationTests(CanonicalLedgerServiceTestBase):
    """Drives the same matrix through the real service and the real endpoint,
    reusing the existing fixture helpers rather than rebuilding them."""

    def _fresh_license(self, tag):
        """An isolated licence, so matrix cases cannot bleed into each other.

        Reuses the exporter/company built by the base setUp (re-running setUp
        would collide on CompanyModel's unique IEC).
        """
        return LicenseDetailsModel.objects.create(
            license_number=f'DISPLAY-RULE-{tag}',
            exporter=self.license.exporter,
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2026, 12, 31),
        )

    def _build(self, has_purchase, has_sale, has_opening, license_obj=None):
        lic = license_obj if license_obj is not None else self.license
        if has_opening:
            LicenseExportItemModel.objects.create(
                license=lic,
                description='Opening Balance Export',
                cif_fc=OPENING_AMOUNT,
            )
        if has_purchase:
            self._create_purchase_trade(
                lic, self.company_a, PURCHASE_AMOUNT, date(2026, 1, 15)
            )
        if has_sale:
            self._create_sale_trade(
                lic, self.company_a, SALE_AMOUNT, date(2026, 2, 1)
            )
        return CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)

    def test_dataset_matrix(self):
        for case_id, has_p, has_s, has_o, expected_types, expect_opening in DISPLAY_MATRIX:
            with self.subTest(case=case_id):
                lic = self._fresh_license(case_id)
                dataset = self._build(has_p, has_s, has_o, license_obj=lic)

                self.assertEqual(
                    [t["type"] for t in dataset["display_transactions"]],
                    expected_types,
                    f"{case_id}: wrong displayed rows",
                )
                self.assertEqual(
                    dataset["opening_display"] is not None,
                    expect_opening,
                    f"{case_id}: opening state presence wrong",
                )
                # OPENING is never an ordinary displayed row.
                self.assertNotIn(
                    OPENING_ROW_TYPE,
                    [t["type"] for t in dataset["display_transactions"]],
                )

    def test_opening_never_displayed_when_purchase_exists(self):
        dataset = self._build(has_purchase=True, has_sale=True, has_opening=True)

        self.assertIsNone(dataset["opening_display"])
        self.assertNotIn(
            OPENING_ROW_TYPE, [t["type"] for t in dataset["display_transactions"]]
        )
        # ...but it is still present in the financial record.
        self.assertIn(OPENING_ROW_TYPE, [t["type"] for t in dataset["transactions"]])

    def test_sale_visible_regardless_of_purchase(self):
        with_purchase = self._build(
            True, True, True, license_obj=self._fresh_license("with-purchase")
        )
        self.assertIn("SALE", [t["type"] for t in with_purchase["display_transactions"]])

        without_purchase = self._build(
            False, True, True, license_obj=self._fresh_license("no-purchase")
        )
        self.assertIn("SALE", [t["type"] for t in without_purchase["display_transactions"]])

    def test_financial_figures_are_untouched_by_display_selection(self):
        """The display rule must not move a single financial number."""
        dataset = self._build(has_purchase=True, has_sale=True, has_opening=True)

        # Opening balance still computed and reported.
        self.assertEqual(dataset["opening_balance"], OPENING_AMOUNT)

        # Running balance is still derived from the FULL record, i.e. it still
        # includes the opening balance even though OPENING is not displayed.
        expected = (OPENING_AMOUNT + PURCHASE_AMOUNT - SALE_AMOUNT).quantize(
            Decimal("0.01")
        )
        self.assertEqual(dataset["license_running_balance"], expected)
        self.assertEqual(dataset["closing_balance"], expected)

        # Totals unchanged.
        self.assertEqual(dataset["totals"]["total_purchases"], PURCHASE_AMOUNT)
        self.assertEqual(dataset["totals"]["total_sales"], SALE_AMOUNT)

        # The financial record keeps every row.
        self.assertEqual(len(dataset["transactions"]), 3)  # OPENING + PURCHASE + SALE
        self.assertEqual(len(dataset["display_transactions"]), 2)

    def test_display_rows_are_the_same_objects_not_recomputed_copies(self):
        """Selection must not clone or re-derive amounts."""
        dataset = self._build(has_purchase=True, has_sale=True, has_opening=True)
        financial_by_id = {t["id"]: t for t in dataset["transactions"]}

        for row in dataset["display_transactions"]:
            self.assertIs(row, financial_by_id[row["id"]])

    def test_no_duplicate_rows_and_chronological_order(self):
        self._set_opening_balance(OPENING_AMOUNT)
        self._create_purchase_trade(self.license, self.company_a, PURCHASE_AMOUNT, date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, SALE_AMOUNT, date(2026, 2, 1))
        self._create_sale_trade(self.license, self.company_a, SALE_AMOUNT, date(2026, 3, 1))
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        rows = dataset["display_transactions"]
        ids = [r["id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)), "duplicate display rows")

        dates = [r["date"] for r in rows if r.get("date")]
        self.assertEqual(dates, sorted(dates), "display rows not chronological")

    def test_api_exposes_display_fields(self):
        self._set_opening_balance(OPENING_AMOUNT)
        self._create_sale_trade(self.license, self.company_a, SALE_AMOUNT, date(2026, 2, 1))

        user = get_user_model().objects.create_user(
            username="display-rule-user", password="pw123456!", is_superuser=True, is_staff=True
        )
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
        )

        resp = client.get(f"/api/license-ledger/{self.license.id}/ledger_detail/")
        self.assertEqual(resp.status_code, 200, resp.data)

        self.assertIn("display_transactions", resp.data)
        self.assertIn("opening_display", resp.data)

        # No PURCHASE -> opening is the starting state, sale is displayed.
        self.assertIsNotNone(resp.data["opening_display"])
        self.assertEqual(resp.data["opening_display"]["type"], OPENING_ROW_TYPE)
        self.assertEqual(
            [t["type"] for t in resp.data["display_transactions"]], ["SALE"]
        )

        # Financial payload still intact and still string-serialised Decimals.
        self.assertEqual(Decimal(resp.data["opening_balance"]), OPENING_AMOUNT)
        self.assertIsInstance(resp.data["license_running_balance"], str)


# ── 3. Backend PDF exporter obeys the same rule ──────────────────────────────

class LedgerPdfDisplayRuleTests(CanonicalLedgerServiceTestBase):
    """`ledger_pdf.get_license_transactions` used to emit the OPENING row only
    when there were NO trades at all, so a licence with sales but no purchase
    lost its opening row — a third, divergent expression of the display rule.
    It now shares `PURCHASE_PRESENCE_TYPES` with the API and the screens.
    """

    def _pdf_rows(self, license_obj):
        from apps.license.services.exporters.ledger_pdf import get_license_transactions
        return get_license_transactions({'id': license_obj.id, 'license_type': 'DFIA'})

    def _types(self, rows):
        # The PDF stores DISPLAY LABELS, not canonical type keys, and is
        # inconsistent about case ('OPENING' but 'Purchase'/'Sale'). Normalise so
        # these tests assert the display RULE, not the label styling.
        return [str(r.get('type') or '').upper() for r in rows]

    def test_opening_shown_when_sales_exist_but_no_purchase(self):
        lic = self._fresh_pdf_license('sale-no-purchase')
        LicenseExportItemModel.objects.create(
            license=lic, description='Opening', cif_fc=OPENING_AMOUNT
        )
        self._create_sale_trade(lic, self.company_a, SALE_AMOUNT, date(2026, 2, 1))

        types = self._types(self._pdf_rows(lic))
        self.assertIn(OPENING_ROW_TYPE, types)
        self.assertIn('SALE', types)

    def test_opening_hidden_when_purchase_exists(self):
        lic = self._fresh_pdf_license('with-purchase')
        LicenseExportItemModel.objects.create(
            license=lic, description='Opening', cif_fc=OPENING_AMOUNT
        )
        self._create_purchase_trade(lic, self.company_a, PURCHASE_AMOUNT, date(2026, 1, 15))
        self._create_sale_trade(lic, self.company_a, SALE_AMOUNT, date(2026, 2, 1))

        types = self._types(self._pdf_rows(lic))
        self.assertNotIn(OPENING_ROW_TYPE, types)
        self.assertIn('PURCHASE', types)
        self.assertIn('SALE', types)

    def test_opening_shown_when_no_trades_at_all(self):
        """Pre-existing behaviour preserved."""
        lic = self._fresh_pdf_license('no-trades')
        LicenseExportItemModel.objects.create(
            license=lic, description='Opening', cif_fc=OPENING_AMOUNT
        )
        self.assertIn(OPENING_ROW_TYPE, self._types(self._pdf_rows(lic)))

    def _fresh_pdf_license(self, tag):
        return LicenseDetailsModel.objects.create(
            license_number=f'PDF-DISPLAY-{tag}',
            exporter=self.license.exporter,
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2026, 12, 31),
        )
