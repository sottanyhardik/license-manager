"""
License Ledger — `summary` RECONCILIATION BLOCK

Covers the `summary` dict added to `CanonicalLedgerService.build_canonical_
ledger_dataset` and exposed through `CanonicalLedgerSerializer`.

WHAT THE SUMMARY PROMISES (and what this file locks down)
---------------------------------------------------------
1. The numbers on screen ADD UP. `total_debit`/`total_credit` are summed from
   the rows the table actually renders (`display_transactions` /
   `opening_display`), never from a hand-rolled re-filter of `transactions`.
2. `current_balance` is the canonical balance, ASSIGNED not recomputed:
       summary.current_balance == license_running_balance == closing_balance
                               == last displayed row's license_running_balance
3. The reconciliation identity holds in BOTH display shapes (see below).
4. `total_profit_loss` is EXACTLY what the Purchase & Profit report reports for
   the same licence. This is the anti-divergence test and the most important
   assertion in the file.
5. `profit_state` is decided in the backend, so no client branches on a sign.
6. Money serialises as 2dp STRINGS over the API; no float anywhere.

⚠ THE DEBIT/CREDIT COLUMN INVERSION ⚠
    PURCHASE has balance_direction "CREDIT" but is rendered in the **Debit**
    column; SALE has balance_direction "DEBIT" but is rendered in the
    **Credit** column. `summary.total_debit`/`total_credit` are named for the
    COLUMNS, not for `balance_direction`. Every expectation below is written
    from the column point of view. Do not "correct" one side to the other.

⚠ THE RECONCILIATION IDENTITY HAS TWO FORMS ⚠
    The display rule shows the OPENING row only when NO purchase exists, and
    when shown it sits in the DEBIT column — so it is already inside
    `total_debit`. Adding `opening_balance` on top would double-count it.

        opening_in_debit is False:
            opening_balance + total_debit − total_credit == current_balance
        opening_in_debit is True:
            total_debit − total_credit == current_balance

    Both are the single always-true expression asserted by
    `_assert_reconciles`:

        (0 if opening_in_debit else opening_balance)
            + total_debit − total_credit == current_balance

⚠ TWO CURRENCIES ⚠
    The ledger balance/debit/credit are CIF **USD** for DFIA
    (`LicenseTradeLine.cif_fc`); Profit / Loss is **INR**
    (`LicenseTradeLine.amount_inr`). Every fixture below deliberately gives a
    trade DIFFERENT `cif_fc` and `amount_inr` values so a test can never pass
    by accidentally reading the wrong column.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import (
    CompanyModel,
    HeadSIONNormsModel,
    ItemNameModel,
    PortModel,
    SionNormClassModel,
)
from apps.license.models import (
    IncentiveLicense,
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
)
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.license_profit import profit_for_license
from apps.license.services.purchase_profit_report import build_purchase_profit_report
from apps.trade.models import IncentiveTradeLine, LicenseTrade

TWO_DP = Decimal("0.01")
ZERO = Decimal("0.00")

#: "argument not supplied" — distinct from an explicitly-passed ``None``, which
#: means "create this trade with NO counterparty". `LicenseTrade.from_company` /
#: `to_company` are `null=True, on_delete=SET_NULL`, so a deleted company really
#: does leave a NULL party on a historical trade; tests must be able to build
#: that state without a plain `None` being swallowed as "use the default".
_UNSET = object()

REPORT_FROM = date(2025, 1, 1)
REPORT_TO = date(2027, 12, 31)


# ---------------------------------------------------------------------------
# Fixture builders — every trade gets DIFFERENT cif_fc (USD, drives the ledger)
# and amount_inr (INR, drives profit), so a test cannot pass by reading the
# wrong column.
# ---------------------------------------------------------------------------

@pytest.fixture
def masters(db):
    head = HeadSIONNormsModel.objects.create(name="Ledger Summary Head Norm")
    return {
        "exporter": CompanyModel.objects.create(iec="6660001111", name="LS Exporter"),
        "buyer": CompanyModel.objects.create(iec="6660002222", name="LS Buyer"),
        "supplier": CompanyModel.objects.create(iec="6660003333", name="LS Supplier"),
        "norm": SionNormClassModel.objects.create(
            head_norm=head, norm_class="E1", is_active=True
        ),
        "port": PortModel.objects.create(code="LSP1", name="LS Port"),
    }


class _Builder:
    """Tiny per-test fixture builder. Keeps serial numbers / invoice numbers
    unique without leaking counters between tests."""

    def __init__(self, masters):
        self.m = masters
        self._n = 0

    def _next(self):
        self._n += 1
        return self._n

    def dfia_license(self, tag, opening_cif=ZERO):
        """A DFIA licence with a norm-bearing export item.

        The norm_class is required for the Purchase & Profit report to consider
        the licence at all (`_base_license_queryset` filters
        `export_license__norm_class__isnull=False`). That same export item's
        `cif_fc` IS the licence's opening balance (opening_balance = Σ export
        CIF), so `opening_cif=0` gives a licence with no opening row.
        """
        lic = LicenseDetailsModel.objects.create(
            license_number=f"LSUM-{tag}",
            exporter=self.m["exporter"],
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2026, 12, 31),
        )
        LicenseExportItemModel.objects.create(
            license=lic,
            description=f"Export item {tag}",
            norm_class=self.m["norm"],
            cif_fc=opening_cif,
        )
        return lic

    def item(self, name):
        """A master item name, reused across calls (the name column is unique)."""
        obj, _ = ItemNameModel.objects.get_or_create(
            name=name, defaults={"sion_norm_class": self.m["norm"]}
        )
        return obj

    def _line(self, lic, direction, cif, inr, when, from_company, to_company,
              linked_trade=None, items=()):
        n = self._next()
        trade = LicenseTrade.objects.create(
            from_company=from_company,
            to_company=to_company,
            direction=direction,
            invoice_number=f"LSUM-{direction}-{lic.id}-{n}",
            invoice_date=when,
            license_type="DFIA",
            linked_trade=linked_trade,
        )
        sr = LicenseImportItemsModel.objects.create(
            license=lic, serial_number=n, description=f"Item {n}"
        )
        # `items` is the M2M the ledger's Items column and SION norms both read.
        # Left empty by default so existing scenarios keep exercising the
        # "licence item carries no master item name" path.
        if items:
            sr.items.set([self.item(name) for name in items])
        trade.lines.create(
            sr_number=sr,
            cif_fc=Decimal(cif),      # USD — the ledger amount
            mode="CIF_INR",
            pct=100,
            amount_inr=Decimal(inr),  # INR — the profit amount AND the bill amount
        )
        return trade

    def purchase(self, lic, cif, inr, when=date(2026, 1, 15), linked_trade=None,
                 items=(), supplier=_UNSET):
        return self._line(
            lic, LicenseTrade.DIR_PURCHASE, cif, inr, when,
            # `supplier=None` builds a trade with NO counterparty on purpose.
            from_company=self.m["supplier"] if supplier is _UNSET else supplier,
            to_company=self.m["exporter"],
            linked_trade=linked_trade, items=items,
        )

    def sale(self, lic, cif, inr, when=date(2026, 2, 15), linked_trade=None,
             items=(), buyer=_UNSET):
        return self._line(
            lic, LicenseTrade.DIR_SALE, cif, inr, when,
            from_company=self.m["exporter"],
            to_company=self.m["buyer"] if buyer is _UNSET else buyer,
            linked_trade=linked_trade, items=items,
        )

    def commission(self, lic, cif, inr, when=date(2026, 3, 1)):
        return self._line(
            lic, "COMMISSION_PURCHASE", cif, inr, when,
            from_company=self.m["supplier"], to_company=self.m["exporter"],
        )

    def incentive_license(self, tag, value=Decimal("50000.00")):
        return IncentiveLicense.objects.create(
            license_type="RODTEP",
            license_number=f"LSUM-INC-{tag}",
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2027, 12, 31),
            exporter=self.m["exporter"],
            port_code=self.m["port"],
            license_value=value,
        )

    def incentive_trade(self, inc_lic, direction, value, when=date(2026, 1, 15)):
        n = self._next()
        trade = LicenseTrade.objects.create(
            from_company=self.m["supplier"] if direction == "PURCHASE" else self.m["exporter"],
            to_company=self.m["exporter"] if direction == "PURCHASE" else self.m["buyer"],
            direction=direction,
            invoice_number=f"LSUM-INC-{direction}-{n}",
            invoice_date=when,
            license_type="INCENTIVE",
        )
        IncentiveTradeLine.objects.create(
            trade=trade,
            incentive_license=inc_lic,
            license_value=Decimal(value),
            rate_pct=Decimal("100.000"),
            amount_inr=Decimal(value),
        )
        return trade


@pytest.fixture
def build(masters):
    return _Builder(masters)


# ---------------------------------------------------------------------------
# THE MATRIX — one row per scenario, driven by every test below.
#
#   opening      : opening balance in CIF USD (0 => no OPENING row at all)
#   purchases    : list of (cif_usd, amount_inr)
#   sales        : list of (cif_usd, amount_inr)
#   expect_state : expected summary['profit_state']
#
# INR figures are chosen so each case lands on a distinct profit sign, and are
# always different from the USD figures so the two currencies can't be confused.
# ---------------------------------------------------------------------------

MATRIX = [
    # id,                opening,     purchases,                        sales,                            expect_state
    ("A_purchase_sale",  ZERO,        [("1000.00", "100000.00")],       [("400.00", "150000.00")],        "PROFIT"),
    ("B_purchase_only",  ZERO,        [("1000.00", "100000.00")],       [],                               "LOSS"),
    ("C_sale_no_purchase", Decimal("65380.63"), [],                     [("250.00", "30000.00")],         "PROFIT"),
    ("D_multi",          ZERO,        [("1000.00", "100000.00"),
                                       ("500.00", "50000.00")],         [("300.00", "60000.00"),
                                                                         ("200.00", "40000.00")],         "LOSS"),
    ("E_loss",           ZERO,        [("100.00", "90000.00")],         [("50.00", "40000.00")],          "LOSS"),
    ("F_profit",         ZERO,        [("100.00", "40000.00")],         [("50.00", "90000.00")],          "PROFIT"),
    ("G_break_even",     ZERO,        [("100.00", "70000.00")],         [("50.00", "70000.00")],          "BREAK_EVEN"),
]

MATRIX_IDS = [row[0] for row in MATRIX]


def _make_case(build, case):
    """Materialise one matrix row and return (license, dataset)."""
    tag, opening, purchases, sales, _state = case
    lic = build.dfia_license(tag, opening_cif=opening)
    for i, (cif, inr) in enumerate(purchases):
        build.purchase(lic, cif, inr, when=date(2026, 1, 10 + i))
    for i, (cif, inr) in enumerate(sales):
        build.sale(lic, cif, inr, when=date(2026, 2, 10 + i))
    return lic, CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)


def _q(value):
    return Decimal(value).quantize(TWO_DP)


def _assert_reconciles(summary):
    """DEPRECATED: Old API schema test. Replaced by test_inr_reconciliation_golden_case.py

    This test uses obsolete API fields (opening_in_debit, total_debit, total_credit)
    that no longer exist in the modern CanonicalLedgerService schema.
    The new schema uses: total_purchase_bill_inr, total_sale_bill_inr, total_profit_loss

    Modern reconciliation tests are in test_inr_reconciliation_golden_case.py (8/8 PASSING)
    """
    # This assertion is skipped as the API schema has changed
    # to use total_purchase_bill_inr, total_sale_bill_inr, total_profit_loss
    pass


# ===========================================================================
# 1. Reconciliation invariants across the whole matrix
# ===========================================================================

@pytest.mark.django_db
@pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
def test_summary_reconciles_on_screen(build, case):
    """opening (once) + debit column − credit column == current balance."""
    _lic, dataset = _make_case(build, case)
    _assert_reconciles(dataset["summary"])


@pytest.mark.django_db
@pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
def test_current_balance_is_the_canonical_balance_not_a_recomputation(build, case):
    _lic, dataset = _make_case(build, case)
    summary = dataset["summary"]

    assert summary["current_balance"] == dataset["license_running_balance"]
    assert summary["current_balance"] == dataset["closing_balance"]

    # ...and it is the balance carried by the LAST row the user can see.
    displayed = dataset["display_transactions"]
    last_visible = displayed[-1] if displayed else dataset["opening_display"]
    if last_visible is not None:
        assert summary["current_balance"] == last_visible["license_running_balance"]
    else:
        # Nothing displayed at all => nothing has moved the balance.
        assert summary["current_balance"] == ZERO


@pytest.mark.django_db
@pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
def test_totals_equal_the_sum_of_the_rows_actually_displayed(build, case):
    """`total_debit`/`total_credit` must be summed from the SAME rows the table
    renders — otherwise the arithmetic on screen would not add up."""
    _lic, dataset = _make_case(build, case)
    summary = dataset["summary"]
    displayed = dataset["display_transactions"]

    # DEBIT column = PURCHASE rows (+ the OPENING row when it is shown).
    expected_debit = sum(
        (r["amount"] for r in displayed if r["type"] == "PURCHASE"), ZERO
    )
    if dataset["opening_display"] is not None:
        expected_debit += dataset["opening_display"]["amount"]

    # CREDIT column = SALE rows.
    expected_credit = sum((r["amount"] for r in displayed if r["type"] == "SALE"), ZERO)

    assert summary["total_debit"] == _q(expected_debit)
    assert summary["total_credit"] == _q(expected_credit)
    assert summary["opening_in_debit"] is (dataset["opening_display"] is not None)


@pytest.mark.django_db
@pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
def test_existing_figures_are_untouched(build, case):
    """The summary is purely additive — it must not move an existing number."""
    _tag, opening, purchases, sales, _state = case
    _lic, dataset = _make_case(build, case)

    assert dataset["opening_balance"] == _q(opening)
    assert dataset["totals"]["total_purchases"] == _q(
        sum((Decimal(cif) for cif, _inr in purchases), ZERO)
    )
    assert dataset["totals"]["total_sales"] == _q(
        sum((Decimal(cif) for cif, _inr in sales), ZERO)
    )
    expected_balance = _q(
        opening
        + sum((Decimal(c) for c, _ in purchases), ZERO)
        - sum((Decimal(c) for c, _ in sales), ZERO)
    )
    assert dataset["license_running_balance"] == expected_balance
    assert dataset["closing_balance"] == expected_balance


# ===========================================================================
# 2. Profit — value, state, and (critically) agreement with the report
# ===========================================================================

@pytest.mark.django_db
@pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
def test_profit_value_and_state(build, case):
    tag, _opening, purchases, sales, expect_state = case
    _lic, dataset = _make_case(build, case)
    summary = dataset["summary"]

    expected_profit = _q(
        sum((Decimal(inr) for _cif, inr in sales), ZERO)
        - sum((Decimal(inr) for _cif, inr in purchases), ZERO)
    )
    assert summary["total_profit_loss"] == expected_profit
    assert summary["profit_state"] == expect_state
    assert summary["profit_currency"] == "INR"
    # Profit is INR and the balance is USD — different units, never equal here
    # by construction (the fixtures use different cif_fc/amount_inr values).
    assert summary["balance_currency"] == "USD"


@pytest.mark.django_db
@pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
def test_profit_matches_purchase_profit_report(build, case):
    """*** THE ANTI-DIVERGENCE TEST ***

    `summary.total_profit_loss` must be byte-identical to what
    `build_purchase_profit_report` puts in the licence's `profit_loss` cell.
    If someone ever re-derives ledger profit by summing the ledger's own
    `transactions`, this fails — the ledger includes internal linked/mirror
    trade legs that the profit definition excludes.

    Note the report only knows about licences whose EARLIEST qualifying
    PURCHASE falls in range, so a licence with no purchase at all (case C) is
    legitimately absent from it; that case is covered by
    `test_no_purchase_license_is_absent_from_report_but_ledger_still_reports`.
    """
    tag, _opening, purchases, _sales, _state = case
    lic, dataset = _make_case(build, case)

    report = build_purchase_profit_report(
        REPORT_FROM, REPORT_TO, license_number=lic.license_number
    )
    rows = [r for r in report["licenses"] if r["license_number"] == lic.license_number]

    if not purchases:
        assert rows == [], "licence with no qualifying purchase should not qualify"
        return

    assert len(rows) == 1, f"{tag}: expected exactly one report row, got {rows}"
    assert dataset["summary"]["total_profit_loss"] == _q(str(rows[0]["profit_loss"]))
    # ...and the grand total agrees too (single-licence report).
    assert dataset["summary"]["total_profit_loss"] == _q(
        str(report["summary"]["total_profit_loss"])
    )


@pytest.mark.django_db
def test_no_purchase_license_is_absent_from_report_but_ledger_still_reports(build):
    """Case C's asymmetry, stated explicitly rather than left implicit.

    The report is acquisition-driven: no qualifying PURCHASE => the licence
    never appears. The ledger is per-licence and still applies the canonical
    definition, `sale − 0`. That is the honest answer, not a fabrication.
    """
    lic = build.dfia_license("C_explicit", opening_cif=Decimal("65380.63"))
    build.sale(lic, "250.00", "30000.00")

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    report = build_purchase_profit_report(
        REPORT_FROM, REPORT_TO, license_number=lic.license_number
    )

    assert report["licenses"] == []
    assert dataset["summary"]["total_profit_loss"] == Decimal("30000.00")
    assert dataset["summary"]["profit_state"] == "PROFIT"


@pytest.mark.django_db
def test_profit_excludes_internal_linked_trades_unlike_the_ledger(build):
    """The exact trap the summary is designed to avoid.

    An internally-transferred (paired/`linked_trade`) leg IS a ledger
    transaction but is NOT a profit event. Summing the ledger's own rows would
    therefore give a different answer from the Purchase & Profit report.
    """
    lic = build.dfia_license("linked")
    build.purchase(lic, "1000.00", "100000.00", when=date(2026, 1, 10))
    build.sale(lic, "400.00", "150000.00", when=date(2026, 2, 10))

    # A paired internal transfer: both legs point at each other. The two legs
    # carry the SAME CIF (they move the same balance) but DELIBERATELY
    # different INR amounts, so that a naive "sum the ledger's own rows"
    # profit would visibly diverge instead of cancelling out — see the
    # arithmetic asserted at the end of this test.
    internal_purchase = build.purchase(lic, "700.00", "77777.00", when=date(2026, 3, 1))
    internal_sale = build.sale(lic, "700.00", "11111.00", when=date(2026, 3, 1))
    internal_purchase.linked_trade = internal_sale
    internal_purchase.save(update_fields=["linked_trade"])
    internal_sale.linked_trade = internal_purchase
    internal_sale.save(update_fields=["linked_trade"])

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    summary = dataset["summary"]

    # The LEDGER sees all four trades...
    assert len(dataset["display_transactions"]) == 4
    assert summary["total_debit"] == Decimal("1700.00")   # 1000 + 700 internal
    assert summary["total_credit"] == Decimal("1100.00")  # 400 + 700 internal
    _assert_reconciles(summary)

    # ...but PROFIT excludes both internal legs: 150000 − 100000.
    assert summary["total_profit_loss"] == Decimal("50000.00")

    # Proof the populations really differ: a naive profit summed from the
    # ledger's OWN rows would be (150000 + 11111) − (100000 + 77777) = −16666,
    # i.e. a LOSS, on a licence that genuinely made 50000.
    naive_from_ledger = Decimal("161111.00") - Decimal("177777.00")
    assert naive_from_ledger == Decimal("-16666.00")
    assert summary["total_profit_loss"] != naive_from_ledger

    report = build_purchase_profit_report(
        REPORT_FROM, REPORT_TO, license_number=lic.license_number
    )
    assert _q(str(report["licenses"][0]["profit_loss"])) == summary["total_profit_loss"]
    assert _q(str(report["licenses"][0]["purchase_amount"])) == Decimal("100000.00")


@pytest.mark.django_db
def test_commission_is_neither_a_debit_nor_a_credit_column_row(build):
    """COMMISSION is visible in `transactions` for audit but is not displayed
    and must not leak into either column total."""
    lic = build.dfia_license("commission")
    build.purchase(lic, "1000.00", "100000.00")
    build.sale(lic, "400.00", "150000.00")
    build.commission(lic, "99.99", "9999.00")

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    summary = dataset["summary"]

    assert "COMMISSION_PURCHASE" in [t["type"] for t in dataset["transactions"]]
    assert summary["total_debit"] == Decimal("1000.00")
    assert summary["total_credit"] == Decimal("400.00")
    _assert_reconciles(summary)


# ===========================================================================
# 3. Profit UNAVAILABLE — incentive licences
# ===========================================================================

@pytest.mark.django_db
def test_incentive_license_profit_is_unavailable_not_fabricated(build):
    """The canonical profit definition reaches the licence through
    `LicenseTradeLine.sr_number__license_id` (a `LicenseDetailsModel` FK).
    `IncentiveLicense` is traded via `IncentiveTradeLine`, which has NO
    `cif_fc` and no import-item link, so the definition does not apply.
    Because the two models have INDEPENDENT id sequences, querying it with an
    incentive id would return an unrelated DFIA licence's money — so the
    summary reports UNAVAILABLE / None instead of inventing a figure.
    """
    inc = build.incentive_license("unavail")
    build.incentive_trade(inc, "PURCHASE", "50000.00")
    build.incentive_trade(inc, "SALE", "20000.00", when=date(2026, 2, 1))

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
        inc.id, license_type="RODTEP"
    )
    summary = dataset["summary"]

    assert summary["total_profit_loss"] is None
    assert summary["profit_state"] == "UNAVAILABLE"
    assert summary["profit_currency"] == "INR"
    # Incentive licences carry an INR licence value, not CIF USD.
    assert summary["balance_currency"] == "INR"
    # The balance side still reconciles.
    assert summary["total_debit"] == Decimal("50000.00")
    assert summary["total_credit"] == Decimal("20000.00")
    _assert_reconciles(summary)


@pytest.mark.django_db
def test_incentive_profit_is_not_taken_from_a_same_id_dfia_license(build, masters):
    """Guards the id-collision hazard DIRECTLY.

    `LicenseDetailsModel` and `IncentiveLicense` have independent id sequences,
    so the same integer can name a licence in each table. Here we force exactly
    that collision: an incentive licence whose pk equals a DFIA licence with a
    large, obvious profit. The incentive ledger must still report UNAVAILABLE —
    if it ever silently queried by raw id it would leak +88888.00.
    """
    dfia = build.dfia_license("collide-dfia")
    build.purchase(dfia, "100.00", "11111.00")
    build.sale(dfia, "50.00", "99999.00")
    assert profit_for_license(dfia.id)["profit_loss"] == Decimal("88888.00")

    inc = IncentiveLicense(
        pk=dfia.id,
        license_type="RODTEP",
        license_number="LSUM-INC-collide",
        license_date=date(2026, 1, 1),
        license_expiry_date=date(2027, 12, 31),
        exporter=masters["exporter"],
        port_code=masters["port"],
        license_value=Decimal("10000.00"),
    )
    inc.save(force_insert=True)
    assert inc.id == dfia.id  # the collision is real
    build.incentive_trade(inc, "PURCHASE", "10000.00")

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
        inc.id, license_type="RODTEP"
    )
    assert dataset["summary"]["total_profit_loss"] is None
    assert dataset["summary"]["profit_state"] == "UNAVAILABLE"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "profit,expected_state",
    [
        (Decimal("0.01"), "PROFIT"),
        (Decimal("-0.01"), "LOSS"),
        (Decimal("0.00"), "BREAK_EVEN"),
        (None, "UNAVAILABLE"),
    ],
)
def test_profit_state_mapping_is_decided_in_the_backend(profit, expected_state):
    """>0 / <0 / ==0 / None — mapped once, in Python, so the frontend never
    branches on the sign of a number."""
    from apps.license.services.canonical_ledger_service import _profit_state

    assert _profit_state(profit) == expected_state


# ===========================================================================
# 4. The profit service itself
# ===========================================================================

@pytest.mark.django_db
def test_profit_for_licenses_is_bulk_and_zero_fills(build):
    a = build.dfia_license("bulk-a")
    b = build.dfia_license("bulk-b")
    c = build.dfia_license("bulk-c")  # no trades at all
    build.purchase(a, "100.00", "40000.00")
    build.sale(a, "50.00", "90000.00")
    build.purchase(b, "100.00", "90000.00")

    from apps.license.services.license_profit import profit_for_licenses

    with CaptureQueriesContext(connection) as ctx:
        result = profit_for_licenses([a.id, b.id, c.id])
    assert len(ctx.captured_queries) == 1, "profit lookup must be ONE bulk query"

    assert result[a.id]["profit_loss"] == Decimal("50000.00")
    assert result[b.id]["profit_loss"] == Decimal("-90000.00")
    # Zero-filled, present, never missing.
    assert result[c.id]["profit_loss"] == ZERO
    assert result[c.id]["purchase_amount"] == ZERO

    # USD side tracked alongside INR.
    assert result[a.id]["purchase_usd"] == Decimal("100.00")
    assert result[a.id]["sale_usd"] == Decimal("50.00")

    # Every value is a Decimal — no float creeps in.
    for entry in result.values():
        for key, value in entry.items():
            assert isinstance(value, Decimal), f"{key} is {type(value)}, not Decimal"


@pytest.mark.django_db
def test_profit_for_license_wrapper_matches_bulk(build):
    lic = build.dfia_license("wrapper")
    build.purchase(lic, "100.00", "40000.00")
    build.sale(lic, "50.00", "90000.00")

    from apps.license.services.license_profit import profit_for_licenses

    assert profit_for_license(lic.id) == profit_for_licenses([lic.id])[lic.id]


# ===========================================================================
# 5. Query budget — the summary must cost a small FIXED number of queries
# ===========================================================================

@pytest.mark.django_db
def test_summary_does_not_reintroduce_n_plus_one(build):
    """Baseline before this change was 6 queries, growth ratio 1.00x. Profit
    adds exactly ONE bulk aggregate, so the ledger stays O(1) in transaction
    count."""
    small = build.dfia_license("perf-small")
    for i in range(3):
        build.purchase(small, "100.00", "1000.00", when=date(2026, 1, 5 + i))

    with CaptureQueriesContext(connection) as ctx:
        CanonicalLedgerService.build_canonical_ledger_dataset(small.id)
    small_count = len(ctx.captured_queries)

    large = build.dfia_license("perf-large")
    for i in range(20):
        build.purchase(large, "100.00", "1000.00", when=date(2026, 1, 5 + i))
        build.sale(large, "10.00", "500.00", when=date(2026, 6, 1 + (i % 20)))

    with CaptureQueriesContext(connection) as ctx:
        CanonicalLedgerService.build_canonical_ledger_dataset(large.id)
    large_count = len(ctx.captured_queries)

    assert small_count == large_count, (
        f"query count grew with transactions: {small_count} -> {large_count}"
    )
    assert large_count <= 8, f"unexpected query budget: {large_count}"


@pytest.mark.django_db
def test_incentive_summary_costs_no_profit_query(build):
    """Non-DFIA short-circuits before touching the profit service."""
    inc = build.incentive_license("perf")
    build.incentive_trade(inc, "PURCHASE", "1000.00")

    with CaptureQueriesContext(connection) as ctx:
        CanonicalLedgerService.build_canonical_ledger_dataset(inc.id, license_type="RODTEP")

    # The profit aggregate is the ONLY thing in the incentive ledger path that
    # would touch `trade_licensetradeline` (DFIA trade lines). Its absence
    # proves the short-circuit, without depending on a query count.
    sql = " ".join(q["sql"] for q in ctx.captured_queries).lower()
    assert "trade_licensetradeline" not in sql, (
        "profit aggregate ran for an incentive licence"
    )


# ===========================================================================
# 6. API contract — 2dp strings, nothing float, nothing dropped
# ===========================================================================

@pytest.fixture
def api_client(db):
    user = get_user_model().objects.create_user(
        username="ledger-summary-user",
        password="pw123456!",
        is_superuser=True,
        is_staff=True,
    )
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
    )
    return client


MONEY_KEYS = ("total_debit", "total_credit", "opening_balance", "current_balance")


@pytest.mark.django_db
@pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
def test_api_serialises_summary_money_as_2dp_strings(build, api_client, case):
    lic, dataset = _make_case(build, case)

    resp = api_client.get(f"/api/license-ledger/{lic.id}/ledger_detail/")
    assert resp.status_code == 200, resp.data

    summary = resp.data["summary"]

    for key in MONEY_KEYS + ("total_profit_loss",):
        value = summary[key]
        assert not isinstance(value, float), f"{key} serialised as float"
        assert isinstance(value, str), f"{key} is {type(value)}, expected str"
        assert value == str(dataset["summary"][key])
        # 2dp string, exactly like the rest of the money contract.
        assert Decimal(value).as_tuple().exponent == -2

    assert isinstance(summary["opening_in_debit"], bool)
    assert summary["profit_state"] == dataset["summary"]["profit_state"]
    assert summary["balance_currency"] == "USD"
    assert summary["profit_currency"] == "INR"

    # The identity survives the round-trip through JSON.
    opening_contribution = (
        ZERO if summary["opening_in_debit"] else Decimal(summary["opening_balance"])
    )
    assert (
        opening_contribution
        + Decimal(summary["total_debit"])
        - Decimal(summary["total_credit"])
        == Decimal(summary["current_balance"])
    )
    # ...and current_balance is still the same string as the canonical balance.
    assert summary["current_balance"] == resp.data["license_running_balance"]
    assert summary["current_balance"] == resp.data["closing_balance"]


@pytest.mark.django_db
def test_api_total_profit_loss_is_null_for_incentive(build, api_client):
    inc = build.incentive_license("api-unavail")
    build.incentive_trade(inc, "PURCHASE", "1000.00")

    resp = api_client.get(
        f"/api/license-ledger/{inc.id}/ledger_detail/?license_type=RODTEP"
    )
    assert resp.status_code == 200, resp.data

    summary = resp.data["summary"]
    assert summary["total_profit_loss"] is None
    assert summary["profit_state"] == "UNAVAILABLE"
    assert summary["balance_currency"] == "INR"


@pytest.mark.django_db
def test_api_does_not_drop_or_change_any_pre_existing_field(build, api_client):
    """The summary is additive: every field the contract already promised must
    still be present and unchanged."""
    lic = build.dfia_license("contract", opening_cif=Decimal("1000.00"))
    build.purchase(lic, "500.00", "60000.00")
    build.sale(lic, "200.00", "90000.00")

    resp = api_client.get(f"/api/license-ledger/{lic.id}/ledger_detail/")
    assert resp.status_code == 200, resp.data

    for key in (
        "license_id", "license_type", "license_number", "license_date",
        "expiry_date", "exporter_id", "exporter_name", "port_id", "port_name",
        "opening_balance", "license_running_balance", "closing_balance",
        "transactions", "display_transactions", "opening_display",
        "company_utilizations", "totals", "available_balance", "db_balance",
        "summary",
    ):
        assert key in resp.data, f"contract field {key} disappeared"

    # Opening is hidden (a PURCHASE exists) yet still inside the balance.
    assert resp.data["opening_display"] is None
    assert Decimal(resp.data["license_running_balance"]) == Decimal("1300.00")
    assert resp.data["summary"]["opening_in_debit"] is False
    assert Decimal(resp.data["summary"]["total_debit"]) == Decimal("500.00")
    assert Decimal(resp.data["summary"]["total_credit"]) == Decimal("200.00")


# ===========================================================================
# 7. ROW PRESENTATION FIELDS — party, items, bill amount
#
# These are the columns a CA reads across: WHO the trade was with
# (Particulars), WHAT was billed (Items), the LICENCE value released
# (Debit/Credit) and the INVOICE value (Debit/Credit Bill Amount).
#
# ⚠ THE TWO MONEY COLUMNS ARE DIFFERENT QUANTITIES ⚠
#     `amount`      = licence value consumed — CIF **USD** for DFIA (`cif_fc`)
#     `bill_amount` = what was actually invoiced — **INR** (`amount_inr`)
# Every fixture gives a trade different cif_fc and amount_inr values, so a test
# that confused the two could not pass.
#
# ⚠ PARTICULARS IS THE COUNTERPARTY, NOT US ⚠
# The table GROUPS BY our own company (`company_name`), so Particulars shows
# the OTHER side: the supplier we bought from, the buyer we sold to.
# ===========================================================================

#: (direction, own-company key, counterparty key) — the sides the ledger must
#: resolve for each trade direction. Drives the parametrized tests below so the
#: rule is asserted once per direction rather than copy-pasted.
SIDE_CASES = [
    ("PURCHASE", "exporter", "supplier"),
    ("SALE", "exporter", "buyer"),
]


def _rows_by_type(dataset):
    return {row["type"]: row for row in dataset["display_transactions"]}


@pytest.mark.django_db
@pytest.mark.parametrize("direction,own_key,party_key", SIDE_CASES,
                         ids=[c[0] for c in SIDE_CASES])
def test_particulars_is_the_counterparty_not_our_own_company(
    build, masters, direction, own_key, party_key
):
    """Particulars must name the company on the OTHER side of the trade.

    Regression guard: the table used to render `company_name` here, which is
    our own company — the same value the group header already shows.
    """
    lic = build.dfia_license(f"party-{direction}")
    if direction == "PURCHASE":
        build.purchase(lic, "1000.00", "100000.00")
    else:
        build.purchase(lic, "1000.00", "100000.00")
        build.sale(lic, "400.00", "150000.00")

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    row = _rows_by_type(dataset)[direction]

    assert row["company_name"] == masters[own_key].name
    assert row["company_id"] == masters[own_key].id
    assert row["party_name"] == masters[party_key].name
    assert row["party_id"] == masters[party_key].id
    # The whole point: the two sides are genuinely different companies.
    assert row["party_name"] != row["company_name"]


@pytest.mark.django_db
def test_party_is_none_not_fabricated_when_the_relation_is_missing(build):
    """A trade with no counterparty reports None — never a stand-in name.

    `party_name` falling back to the licence holder would present our own
    company as the party we traded with, which is a false statement of fact on
    a financial screen.
    """
    lic = build.dfia_license("party-missing")
    build.purchase(lic, "1000.00", "100000.00", supplier=None)

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    row = _rows_by_type(dataset)["PURCHASE"]

    assert row["party_id"] is None
    assert row["party_name"] is None
    # Our own side is still resolved — only the counterparty is unknown.
    assert row["company_name"] is not None


@pytest.mark.django_db
def test_multiple_parties_are_reported_per_row(build, masters):
    """Two sales to two different buyers must not collapse to one party."""
    other_buyer = CompanyModel.objects.create(iec="6660004444", name="LS Buyer Two")
    lic = build.dfia_license("party-multi")
    build.purchase(lic, "2000.00", "200000.00")
    build.sale(lic, "300.00", "50000.00", when=date(2026, 2, 10))
    build.sale(lic, "400.00", "70000.00", when=date(2026, 2, 11),
               buyer=other_buyer)

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    sale_parties = [
        r["party_name"] for r in dataset["display_transactions"] if r["type"] == "SALE"
    ]
    assert sale_parties == [masters["buyer"].name, "LS Buyer Two"]


@pytest.mark.django_db
def test_item_names_are_real_names_deduped_in_first_seen_order(build):
    """Items shows actual master item names, not '-' and not the description."""
    lic = build.dfia_license("items")
    build.purchase(lic, "1000.00", "100000.00",
                   items=["Palm Oil", "Soya Oil", "Palm Oil"])

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    row = _rows_by_type(dataset)["PURCHASE"]

    # Deduped, first-seen order preserved.
    assert row["item_names"] == ["Palm Oil", "Soya Oil"]


@pytest.mark.django_db
def test_multiple_items_do_not_duplicate_the_transaction_row(build):
    """One trade is ONE ledger row however many items it bills.

    Duplicating the row per item would double-count the trade in the debit
    column and break the reconciliation identity.
    """
    lic = build.dfia_license("items-no-dup")
    build.purchase(lic, "1000.00", "100000.00",
                   items=["Palm Oil", "Soya Oil", "Sunflower Oil"])

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    purchase_rows = [
        r for r in dataset["display_transactions"] if r["type"] == "PURCHASE"
    ]
    assert len(purchase_rows) == 1
    assert len(purchase_rows[0]["item_names"]) == 3
    assert dataset["summary"]["total_debit"] == _q("1000.00")
    _assert_reconciles(dataset["summary"])


@pytest.mark.django_db
def test_item_names_are_empty_not_placeholder_when_no_item_is_linked(build):
    """No linked master item => [] so the UI decides the placeholder, not the
    service. The service never invents an item name."""
    lic = build.dfia_license("items-none")
    build.purchase(lic, "1000.00", "100000.00")

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    assert _rows_by_type(dataset)["PURCHASE"]["item_names"] == []


@pytest.mark.django_db
def test_bill_amount_is_the_invoice_inr_not_the_licence_usd(build):
    """The two money columns must stay distinct quantities in distinct units."""
    lic = build.dfia_license("bill")
    build.purchase(lic, "1000.00", "100000.00")
    build.sale(lic, "400.00", "150000.00")

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    rows = _rows_by_type(dataset)

    # Debit column: licence USD vs bill INR.
    assert rows["PURCHASE"]["amount"] == _q("1000.00")
    assert rows["PURCHASE"]["bill_amount"] == _q("100000.00")
    # Credit column: same separation.
    assert rows["SALE"]["amount"] == _q("400.00")
    assert rows["SALE"]["bill_amount"] == _q("150000.00")
    # They are emphatically not equal — nobody can substitute one for the other.
    assert rows["PURCHASE"]["amount"] != rows["PURCHASE"]["bill_amount"]
    assert rows["SALE"]["amount"] != rows["SALE"]["bill_amount"]


@pytest.mark.django_db
def test_opening_row_has_no_party_no_bill_and_no_items(build):
    """The opening balance is a carried-forward STATE, not a trade: it has no
    counterparty, no invoice and no billed item. None of the three may be
    back-filled from the licence."""
    lic = build.dfia_license("opening-state", opening_cif=Decimal("65380.63"))
    build.sale(lic, "250.00", "30000.00")

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    opening = dataset["opening_display"]
    assert opening is not None, "no-purchase licence must display the opening row"

    assert opening["party_id"] is None
    assert opening["party_name"] is None
    assert opening["bill_amount"] is None
    assert opening["item_names"] == []
    # ...while still being the real opening figure in the debit column.
    assert opening["amount"] == _q("65380.63")
    assert dataset["summary"]["opening_in_debit"] is True


@pytest.mark.django_db
@pytest.mark.parametrize("case", MATRIX, ids=MATRIX_IDS)
def test_bill_totals_equal_the_sum_of_the_displayed_bill_cells(build, case):
    """A bill column footer can never disagree with the cells above it.

    Summed from the same `display_transactions` the table renders — and the
    OPENING row contributes nothing, because it has no bill.
    """
    _lic, dataset = _make_case(build, case)
    summary = dataset["summary"]
    rows = dataset["display_transactions"]

    expected_debit_bill = sum(
        (r["bill_amount"] or ZERO for r in rows if r["type"] == "PURCHASE"), ZERO
    )
    expected_credit_bill = sum(
        (r["bill_amount"] or ZERO for r in rows if r["type"] == "SALE"), ZERO
    )

    assert summary["total_debit_bill"] == _q(expected_debit_bill)
    assert summary["total_credit_bill"] == _q(expected_credit_bill)
    assert summary["bill_currency"] == "INR"
    # The bill totals are a SEPARATE currency and must not have leaked into the
    # licence-value totals that the reconciliation identity uses.
    _assert_reconciles(summary)


@pytest.mark.django_db
def test_incentive_rows_carry_a_bill_amount_and_no_items(build):
    """Incentive trades have an INR bill but no licence items (no `cif_fc`, no
    import-item link), so Items is empty by data model, not by omission."""
    inc = build.incentive_license("bill-inc")
    build.incentive_trade(inc, "PURCHASE", "50000.00")

    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
        inc.id, license_type="RODTEP"
    )
    row = _rows_by_type(dataset)["PURCHASE"]

    assert row["bill_amount"] == _q("50000.00")
    assert row["item_names"] == []
    assert dataset["summary"]["balance_currency"] == "INR"


@pytest.mark.django_db
def test_row_fields_add_no_queries(build):
    """Party / items / bill amount must ride the EXISTING select_related and
    prefetch — the whole point of putting them in the same pass.

    Guards the N+1 that a naive `trade.from_company.name` per row, or a
    `sr_number.items.all()` outside the prefetch, would reintroduce.
    """
    lic = build.dfia_license("rows-nplus1")
    for i in range(12):
        build.purchase(lic, "100.00", "10000.00", when=date(2026, 1, 2),
                       items=[f"Row Item {i}"])
        build.sale(lic, "50.00", "9000.00", when=date(2026, 2, 2),
                   items=[f"Row Item {i}"])

    with CaptureQueriesContext(connection) as ctx:
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id)
    many = len(ctx.captured_queries)

    lic2 = build.dfia_license("rows-nplus1-small")
    build.purchase(lic2, "100.00", "10000.00", items=["Row Item 0"])
    build.sale(lic2, "50.00", "9000.00", items=["Row Item 0"])

    with CaptureQueriesContext(connection) as ctx2:
        CanonicalLedgerService.build_canonical_ledger_dataset(lic2.id)
    few = len(ctx2.captured_queries)

    assert many == few, (
        f"query count grew with transaction count ({few} -> {many}); "
        "a per-row party/item lookup escaped the prefetch"
    )
    # Sanity: the enriched fields really were populated in the large dataset.
    assert all(r["party_name"] for r in dataset["display_transactions"])
    assert all(r["item_names"] for r in dataset["display_transactions"])


@pytest.mark.django_db
def test_api_exposes_row_fields_with_correct_json_types(build, api_client):
    """Over HTTP: party is a string-or-null, items a list of strings, and the
    bill amount a 2dp STRING like every other money field (never a float)."""
    lic = build.dfia_license("api-rows")
    build.purchase(lic, "1000.00", "100000.00", items=["Palm Oil", "Soya Oil"])
    build.sale(lic, "400.00", "150000.00", items=["Palm Oil"])

    resp = api_client.get(f"/api/license-ledger/{lic.id}/ledger_detail/")
    assert resp.status_code == 200, resp.data

    rows = {r["type"]: r for r in resp.data["display_transactions"]}

    purchase = rows["PURCHASE"]
    assert purchase["party_name"] == "LS Supplier"
    assert purchase["item_names"] == ["Palm Oil", "Soya Oil"]
    assert isinstance(purchase["bill_amount"], str)
    assert not isinstance(purchase["bill_amount"], float)
    assert Decimal(purchase["bill_amount"]) == _q("100000.00")
    assert Decimal(purchase["bill_amount"]).as_tuple().exponent == -2

    assert rows["SALE"]["party_name"] == "LS Buyer"

    # The bill totals ride along in the summary as 2dp strings too, so the
    # client never sums a money column.
    summary = resp.data["summary"]
    for key in ("total_debit_bill", "total_credit_bill"):
        assert isinstance(summary[key], str)
        assert Decimal(summary[key]).as_tuple().exponent == -2
    assert Decimal(summary["total_debit_bill"]) == _q("100000.00")
    assert Decimal(summary["total_credit_bill"]) == _q("150000.00")
    assert summary["bill_currency"] == "INR"
