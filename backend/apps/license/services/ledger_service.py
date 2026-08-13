"""
License Ledger Service

Pure business-logic functions extracted from LicenseLedgerViewSet.
The viewset becomes a thin HTTP coordinator; all data assembly lives here.
"""
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from django.db.models import Sum, Count, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_date

from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.license.services.ledger_accounting import (
    ALL_LICENSE_TYPES,
    DFIA_LICENSE_TYPE,
    INCENTIVE_LICENSE_TYPE,
    INCENTIVE_LICENSE_TYPES,
    INCENTIVE_SUBTYPES,
    LedgerFilterSpec,
    LicenseLedgerAccountingService,
    ReportingPeriod,
    license_index,
    net_of,
    parse_decimal,
    parse_int,
    text_param,
)

logger = logging.getLogger(__name__)

# The licence-type vocabulary, the filter parsers and the reporting period are
# all imported from `ledger_accounting` rather than restated here: this module
# is a PRESENTATION layer over that service, and a second copy of any of them is
# how the four ledger endpoints drifted apart in the first place.
TRADE_DIRECTIONS = ("PURCHASE", "SALE")
DECIMAL_ZERO = Decimal("0")


def _live_dfia_balance_map(dfia_qs) -> dict:
    """
    Live, batched-computed ``{license_id: Decimal}`` balance for every id
    currently in ``dfia_qs`` (a fixed number of queries, not one per
    license). BL-LEDGER-02: ``balance__balance_cif`` is a denormalized
    cache with no signal on reconciliation-allocation changes, so it can be
    stale -- every filter/aggregate/sort by DFIA balance in this module
    reads from this instead.
    """
    from apps.license.services.balance_calculator import LicenseBalanceCalculator
    ids = list(dfia_qs.values_list('id', flat=True))
    return LicenseBalanceCalculator.calculate_financial_balance_for_licenses(ids)


def _dfia_ids_with_min_live_balance(dfia_qs, min_balance) -> list:
    """Subset of ``dfia_qs``'s ids whose LIVE balance is >= ``min_balance``."""
    live_map = _live_dfia_balance_map(dfia_qs)
    return [lid for lid, bal in live_map.items() if bal >= min_balance]


# ---------------------------------------------------------------------------
# THE ONE FILTER + ACCOUNTING PIPELINE
#
# Every ledger endpoint in this module — the list, `summary`, `license_wise` and
# `company_wise` — is built from `_ledger_dataset()` below. They differ ONLY in
# how they group and label its rows.
#
# This is the module's central invariant, and it is what the Module 05 audit
# exists to protect. Before it, each endpoint re-read the query string and each
# disagreed with the others about at least one filter: `company_wise` read
# nothing but `search`, `license_wise` filtered the whole licence population by
# TRANSACTION date (so a licence held but quiet in the window vanished), and the
# list and summary applied the company filter with different role semantics.
#
# Nothing in this file parses a filter, compares a date to a licence or a trade,
# or computes a money figure. `ledger_accounting` owns all of it — see that
# module's docstring for the rules and the worked examples.
# ---------------------------------------------------------------------------

def _as_decimal(value) -> Decimal:
    return value if value is not None else DECIMAL_ZERO


def _as_model_list(queryset, *related_fields):
    if hasattr(queryset, "select_related"):
        return list(queryset.select_related(*related_fields))
    return list(queryset)


# ---------------------------------------------------------------------------
# Sold-status helper
# ---------------------------------------------------------------------------

def get_sold_status(total, balance) -> str:
    """Return 'YES', 'NO', or 'PARTIAL' based on how much of the license is sold."""
    total = _as_decimal(total)
    balance = _as_decimal(balance)
    if balance <= 0:
        return 'YES'
    if balance >= total:
        return 'NO'
    return 'PARTIAL'


# ---------------------------------------------------------------------------
# The shared pipeline: filters -> eligible licences -> canonical activity
# ---------------------------------------------------------------------------

def _base_license_querysets(spec: LedgerFilterSpec):
    """
    Both families narrowed by the CHEAP COLUMN filters — everything that can be
    answered from the licence row itself, before any accounting runs.

    Order matters only for cost: these run first so the eligibility and activity
    queries downstream see the smallest possible id set.
    """
    dfia_qs = LicenseDetailsModel.objects.select_related('exporter', 'port').all()
    incentive_qs = IncentiveLicense.objects.select_related('exporter', 'port_code').all()

    if spec.active_only:
        dfia_qs = dfia_qs.filter(flags__is_expired=False)
        incentive_qs = incentive_qs.filter(
            is_active=True, license_expiry_date__gte=timezone.now().date()
        )

    if spec.exporter_id:
        dfia_qs = dfia_qs.filter(exporter_id=spec.exporter_id)
        incentive_qs = incentive_qs.filter(exporter_id=spec.exporter_id)

    if spec.min_balance is not None:
        # BL-LEDGER-02: DFIA balance is resolved LIVE, never from the stale
        # denormalized column.
        dfia_qs = dfia_qs.filter(id__in=_dfia_ids_with_min_live_balance(dfia_qs, spec.min_balance))
        incentive_qs = incentive_qs.filter(balance_value__gte=spec.min_balance)

    # `norm` and `purchase_status` are DFIA-only columns, so the whole Incentive
    # family is dropped rather than left silently unfiltered — see
    # `LedgerFilterSpec.drops_incentive_licenses`.
    if spec.norm:
        dfia_qs = dfia_qs.filter(export_license__norm_class__norm_class=spec.norm).distinct()
    if spec.purchase_status:
        dfia_qs = dfia_qs.filter(purchase_status__code=spec.purchase_status)
    if spec.drops_incentive_licenses:
        incentive_qs = IncentiveLicense.objects.none()

    if spec.search_terms:
        dfia_qs, incentive_qs = _apply_search(spec, dfia_qs, incentive_qs)

    return _narrow_to_license_type(spec, dfia_qs, incentive_qs)


def _apply_search(spec: LedgerFilterSpec, dfia_qs, incentive_qs):
    """
    The ``search`` box, applied to the LICENCE — one substring term matches a
    licence number or an exporter name; several comma-separated terms are exact
    licence numbers (see `LedgerFilterSpec.search_terms`).

    Matching licences rather than trades is deliberate: searching a licence
    number must not also decide which of that licence's transactions are in the
    period. Only the reporting period does that.
    """
    terms = spec.search_terms
    if len(terms) == 1:
        term = terms[0]
        match = Q(license_number__icontains=term) | Q(exporter__name__icontains=term)
    else:
        match = Q(license_number__in=terms)
    return dfia_qs.filter(match), incentive_qs.filter(match)


def _narrow_to_license_type(spec: LedgerFilterSpec, dfia_qs, incentive_qs):
    """Drop the family the ``license_type`` filter excludes, at queryset level."""
    if spec.license_type == DFIA_LICENSE_TYPE:
        return dfia_qs, IncentiveLicense.objects.none()
    if spec.license_type in INCENTIVE_LICENSE_TYPES:
        if spec.license_type != INCENTIVE_LICENSE_TYPE:
            incentive_qs = incentive_qs.filter(license_type=spec.license_type)
        return LicenseDetailsModel.objects.none(), incentive_qs
    return dfia_qs, incentive_qs


def _company_scoped_licenses(spec: LedgerFilterSpec, dfia_qs, incentive_qs):
    """
    Narrow to the licences this company actually traded, in the ROLE the grids
    group by: buyer of a purchase, seller of a sale.

    The same rule `_own_and_party` applies inside the accounting service, so the
    licence set and the transactions listed under it agree. The previous
    "either side of the trade" filter admitted licences where the selected
    company was only the counterparty — the diagnosed NEELKANTH IMPEX /
    LABDHI GLOBAL LLP defect — and it disagreed with the grids, which never
    grouped those trades under the selected company anyway.
    """
    from apps.trade.models import LicenseTrade

    if not spec.company_id:
        return dfia_qs, incentive_qs

    role = (
        Q(direction=LicenseTrade.DIR_PURCHASE, to_company_id=spec.company_id)
        | Q(direction=LicenseTrade.DIR_SALE, from_company_id=spec.company_id)
    )
    dfia_ids = (
        LicenseTrade.objects.filter(role, license_type=DFIA_LICENSE_TYPE)
        .values_list('lines__sr_number__license_id', flat=True).distinct()
    )
    inc_ids = (
        LicenseTrade.objects.filter(role, license_type=INCENTIVE_LICENSE_TYPE)
        .values_list('incentive_lines__incentive_license_id', flat=True).distinct()
    )
    return dfia_qs.filter(id__in=dfia_ids), incentive_qs.filter(id__in=inc_ids)


def _ledger_dataset(query_params, *, with_index: bool = True) -> dict:
    """
    THE License Ledger dataset: one parse, one licence set, one activity map.

    Returns::

        {
          'spec':         LedgerFilterSpec,   # the parsed filters
          'period':       ReportingPeriod,
          'dfia_qs' / 'incentive_qs',         # the eligible licences, per family
          'activity':     {(family, id): entry},   # canonical accounting
          'index':        {(family, id): labels},  # license_number / date / type
          'totals':       grand totals over `activity`,
        }

    Order of operations is the one fixed in `ledger_accounting`'s section 4 and
    is not negotiable per endpoint:

        column filters -> ELIGIBILITY -> company scope -> PERIOD ACTIVITY

    The company scope lands AFTER eligibility so it can never influence a
    first-purchase decision, and the period lands last so it can never remove a
    licence — only move its transactions between opening and activity.
    """
    spec = LedgerFilterSpec.from_query_params(query_params)
    if spec.company_id is None and text_param(query_params, 'company'):
        logger.warning("Invalid company_id: %s", query_params.get('company'))

    dfia_qs, incentive_qs = _base_license_querysets(spec)
    dfia_qs, incentive_qs = LicenseLedgerAccountingService.apply_license_eligibility(
        dfia_qs, incentive_qs, spec
    )
    dfia_qs, incentive_qs = _company_scoped_licenses(spec, dfia_qs, incentive_qs)

    dfia_ids = list(dfia_qs.values_list('id', flat=True))
    incentive_ids = list(incentive_qs.values_list('id', flat=True))

    activity = LicenseLedgerAccountingService.build_period_activity(
        dfia_ids=dfia_ids,
        incentive_ids=incentive_ids,
        period=spec.period,
        company_id=spec.company_id,
    )

    return {
        'spec': spec,
        'period': spec.period,
        'dfia_qs': dfia_qs,
        'incentive_qs': incentive_qs,
        'dfia_ids': dfia_ids,
        'incentive_ids': incentive_ids,
        'activity': activity,
        'index': license_index(dfia_ids, incentive_ids) if with_index else {},
        'totals': _totals_from_activity(activity.values()),
    }


def _totals_from_activity(entries) -> dict:
    """
    Grand totals over canonical entries, summed as raw Decimals so rounding
    happens once, at the edge.

    ``profit_loss`` is `calculate_profit_loss` applied to the two published
    sums — never a sum of per-licence profits, which would round twice and could
    drift from ``credit_bill - debit_bill``.
    """
    credit_bill = DECIMAL_ZERO
    debit_bill = DECIMAL_ZERO
    opening_position = DECIMAL_ZERO
    for entry in entries:
        credit_bill += entry['credit_bill']
        debit_bill += entry['debit_bill']
        opening_position += entry['opening_position']
    return {
        'credit_bill': credit_bill,
        'debit_bill': debit_bill,
        'profit_loss': LicenseLedgerAccountingService.calculate_profit_loss(
            credit_bill, debit_bill
        ),
        'opening_position': opening_position,
        'closing_position': opening_position + net_of(credit_bill, debit_bill),
    }


# ---------------------------------------------------------------------------
# Canonical period money, projected onto a presentation row
# ---------------------------------------------------------------------------

def _activity_for(activity, *, dfia_ids=(), incentive_ids=()) -> dict:
    """
    Return the caller's canonical activity map, or build a LIFETIME one.

    The fallback exists for the callers that legitimately have no reporting
    period — `search_licenses`, the viewset's single-licence detail row, and any
    exporter that prepares rows directly. It is the unbounded period, which by
    construction gives zero opening and whole-history movement, so those callers
    see exactly what they saw before periods existed. It is never a different
    rule, only an open one.
    """
    if activity is not None:
        return activity
    return LicenseLedgerAccountingService.build_period_activity(
        dfia_ids=dfia_ids,
        incentive_ids=incentive_ids,
        period=ReportingPeriod.unbounded(),
    )


def _period_money(entry) -> dict:
    """
    The canonical INR money for one licence, as list-row keys.

    `purchase_amount` / `sale_amount` keep their long-standing names and meaning
    — Σ purchase bills, Σ sale bills — but are now scoped to the reporting
    period, and `opening_position` / `closing_position` disclose what the period
    carried in and out. `profit_loss` is the canonical
    ``credit_bill - debit_bill`` and is COPIED, never recomputed here. A row with
    no entry (a licence with no qualifying trade) reports zeros rather than being
    dropped.
    """
    if not entry:
        return {
            'purchase_amount': 0.0,
            'sale_amount': 0.0,
            'profit_loss': 0.0,
            'profit_state': 'NONE',
            'opening_position': 0.0,
            'closing_position': 0.0,
        }
    return {
        'purchase_amount': float(entry['credit_bill']),
        'sale_amount': float(entry['debit_bill']),
        'profit_loss': float(entry['profit_loss']),
        'profit_state': entry['profit_state'],
        'opening_position': float(entry['opening_position']),
        'closing_position': float(entry['closing_position']),
    }


def _iso_or_dash(value) -> str:
    """A transaction date as the grids have always printed it: ISO, or ``'-'``."""
    return str(value) if value else '-'


def _iso_or_none(value):
    return str(value) if value else None


def _trade_row_sort_key(row):
    """Chronological, ties broken by trade id; undated rows last, not first."""
    return (row['invoice_date'] == '-', row['invoice_date'], row['trade_id'])


# ---------------------------------------------------------------------------
# Data-preparation helpers (previously private viewset methods)
# ---------------------------------------------------------------------------

def prepare_dfia_data(queryset, activity=None) -> list:
    """
    Annotate a DFIA queryset with trade aggregates and return a list of dicts.
    Uses 2 batched group-by queries instead of 4N individual queries.

    Args:
        queryset: DFIA licences (a QuerySet or a plain list of instances).
        activity: the canonical `build_period_activity` map. When given, the
            money columns are that PERIOD's figures and the row also carries the
            opening/closing position. When ``None`` this falls back to the
            unbounded period — i.e. lifetime — which is what the callers that
            have no period concept (`search_licenses`) want.

    The INR money is never re-derived here: `purchase_amount`, `sale_amount`,
    `profit_loss`, `opening_position` and `closing_position` all come from the
    canonical accounting service, so this list cannot disagree with the summary
    that totals it or with the grids that group it.
    """
    from apps.license.services.balance_calculator import LicenseBalanceCalculator
    from apps.trade.models import LicenseTrade

    # Accept either a QuerySet or a plain list of model instances.
    licenses = _as_model_list(queryset, 'exporter', 'port')
    if not licenses:
        return []

    license_ids = [lic.id for lic in licenses]
    activity = _activity_for(activity, dfia_ids=license_ids)

    # USD (CIF) movement stays a local aggregate: the canonical accounting
    # service is denominated in INR (see its CURRENCY section), while
    # `total_value`/`sold_value` below are the licence's own USD figures. The
    # two currencies are reported side by side and never added.
    purchase_totals = (
        LicenseTrade.objects
        .filter(license_type=DFIA_LICENSE_TYPE, direction='PURCHASE', lines__sr_number__license_id__in=license_ids)
        .values('lines__sr_number__license_id')
        .annotate(total_usd=Sum('lines__cif_fc'))
    )
    sale_totals = (
        LicenseTrade.objects
        .filter(license_type=DFIA_LICENSE_TYPE, direction='SALE', lines__sr_number__license_id__in=license_ids)
        .values('lines__sr_number__license_id')
        .annotate(total_usd=Sum('lines__cif_fc'))
    )

    purchase_map = {r['lines__sr_number__license_id']: r for r in purchase_totals}
    sale_map = {r['lines__sr_number__license_id']: r for r in sale_totals}
    # `balance_value` must be the SAME shared Balance Engine figure every
    # other module shows — NOT `purchase CIF - sale CIF` (a trade-only sum
    # that ignores BOE debits/allotments/opening balance and silently
    # shows $0 for any license with few/no internal purchase trades, the
    # common case). Verified by CanonicalLedgerService golden scenarios.
    balance_map = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(license_ids)

    data = []
    for license in licenses:
        pur_row = purchase_map.get(license.id, {})
        sal_row = sale_map.get(license.id, {})

        purchase_amount_usd = float(pur_row.get('total_usd') or 0)
        sale_amount_usd = float(sal_row.get('total_usd') or 0)

        balance_usd = float(balance_map.get(license.id, DECIMAL_ZERO))
        entry = activity.get((DFIA_LICENSE_TYPE, license.id))

        data.append({
            'id': license.id,
            'license_type': DFIA_LICENSE_TYPE,
            'license_number': license.license_number,
            'license_date': license.license_date,
            'license_expiry_date': license.license_expiry_date,
            'exporter_name': license.exporter.name if license.exporter else '',
            'exporter_id': license.exporter.id if license.exporter else None,
            'port_name': license.port.name if license.port else '',
            'total_value': purchase_amount_usd,
            'balance_value': balance_usd,
            'sold_value': sale_amount_usd,
            'currency': 'USD',
            'is_expired': license.is_expired,
            'is_active': not license.is_expired,
            'sold_status': get_sold_status(purchase_amount_usd, balance_usd),
            **_period_money(entry),
        })
    return data


def prepare_incentive_data(queryset, activity=None) -> list:
    """
    Annotate an Incentive queryset with trade aggregates and return a list of dicts.

    ``activity`` has the same contract as in `prepare_dfia_data`: the canonical
    period money, or ``None`` for the lifetime view.
    """
    from apps.trade.models import LicenseTrade

    licenses = _as_model_list(queryset, 'exporter', 'port_code')
    if not licenses:
        return []

    license_ids = [lic.id for lic in licenses]
    today = timezone.now().date()
    activity = _activity_for(activity, incentive_ids=license_ids)

    # `license_value` movement — the licence's own value, reported alongside the
    # canonical INR money below.
    purchase_totals = (
        LicenseTrade.objects
        .filter(
            license_type=INCENTIVE_LICENSE_TYPE,
            direction='PURCHASE',
            incentive_lines__incentive_license_id__in=license_ids,
        )
        .values('incentive_lines__incentive_license_id')
        .annotate(total_value=Sum('incentive_lines__license_value'))
    )
    sale_totals = (
        LicenseTrade.objects
        .filter(
            license_type=INCENTIVE_LICENSE_TYPE,
            direction='SALE',
            incentive_lines__incentive_license_id__in=license_ids,
        )
        .values('incentive_lines__incentive_license_id')
        .annotate(total_value=Sum('incentive_lines__license_value'))
    )

    purchase_map = {r['incentive_lines__incentive_license_id']: r for r in purchase_totals}
    sale_map = {r['incentive_lines__incentive_license_id']: r for r in sale_totals}

    data = []
    for license in licenses:
        pur_row = purchase_map.get(license.id, {})
        sal_row = sale_map.get(license.id, {})

        purchase_value_inr = float(pur_row.get('total_value') or 0)
        sale_value_inr = float(sal_row.get('total_value') or 0)
        entry = activity.get((INCENTIVE_LICENSE_TYPE, license.id))
        # `balance_value` is the authoritative, signal-maintained
        # `IncentiveLicense.balance_value` field (`license_value -
        # sold_value`, kept in sync by `recompute_totals` on every trade
        # change) — NOT re-derived from trade sums here, so this can never
        # drift from what the license's own model already reports.
        balance_inr = float(license.balance_value or 0)

        data.append({
            'id': license.id,
            'license_type': license.license_type,
            'license_number': license.license_number,
            'license_date': license.license_date,
            'license_expiry_date': license.license_expiry_date,
            'exporter_name': license.exporter.name if license.exporter else '',
            'exporter_id': license.exporter.id if license.exporter else None,
            'port_name': license.port_code.name if license.port_code else '',
            'total_value': purchase_value_inr,
            'balance_value': balance_inr,
            'sold_value': sale_value_inr,
            'currency': 'INR',
            'is_expired': license.license_expiry_date < today if license.license_expiry_date else False,
            'is_active': license.is_active,
            'sold_status': get_sold_status(purchase_value_inr, balance_inr),
            **_period_money(entry),
        })
    return data


def get_incentive_breakdown(incentive_qs) -> dict:
    """
    Return per-type count and balance for RODTEP/ROSTL/MEIS in a single DB query.
    """
    rows = (
        incentive_qs
        .filter(license_type__in=INCENTIVE_SUBTYPES)
        .values('license_type')
        .annotate(count=Count('id'), balance=Sum('balance_value'))
    )
    breakdown = {
        row['license_type']: {
            'count': row['count'],
            'balance': round(float(row['balance'] or 0), 2),
        }
        for row in rows
    }
    for lt in INCENTIVE_SUBTYPES:
        if lt not in breakdown:
            breakdown[lt] = {'count': 0, 'balance': 0.0}
    return breakdown


# ---------------------------------------------------------------------------
# Queryset / list builder
# ---------------------------------------------------------------------------

def build_license_queryset(query_params) -> list:
    """
    Apply all ledger-list filters and return a combined, sorted list of
    DFIA + Incentive license dicts — the same data shape returned by
    ``LicenseLedgerViewSet.get_queryset()``.

    Accepts a dict-like ``query_params`` (e.g. ``request.query_params``).

    A pure PRESENTATION pass over `_ledger_dataset`: the licence set and every
    money column come from the canonical service, so the list, the summary that
    totals it and the two grids that regroup it are all reading one result.
    """
    dataset = _ledger_dataset(query_params, with_index=False)
    activity = dataset['activity']

    rows = (
        list(prepare_dfia_data(dataset['dfia_qs'], activity=activity))
        + list(prepare_incentive_data(dataset['incentive_qs'], activity=activity))
    )
    rows.sort(key=lambda x: x.get('license_date') or date.min, reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Summary service
# ---------------------------------------------------------------------------

def get_ledger_summary(query_params) -> dict:
    """
    Compute summary statistics for the ledger.

    Accepts a dict-like object (e.g. ``request.query_params``).
    Returns a plain dict suitable for ``Response(…)``.

    A TOTAL OF THE LIST, not a second opinion about it: the licence set and the
    activity map are the identical `_ledger_dataset` result the list rows are
    built from, so ``total_licenses`` counts exactly the rows the grid shows and
    the money columns sum exactly their values.
    """
    dataset = _ledger_dataset(query_params, with_index=False)
    dfia_qs = dataset['dfia_qs']
    incentive_qs = dataset['incentive_qs']
    activity = dataset['activity']

    # DFIA aggregates
    _opening_rows = dfia_qs.annotate(
        _opening=Coalesce(Sum('export_license__cif_fc'), Value(DECIMAL_ZERO), output_field=DecimalField())
    ).values_list('_opening', flat=True)
    dfia_total = sum(float(v or 0) for v in _opening_rows)
    dfia_balance = float(sum(_live_dfia_balance_map(dfia_qs).values()))
    dfia_sold = dfia_total - dfia_balance

    # Incentive aggregates
    inc_agg = incentive_qs.aggregate(
        total=Sum('license_value'), balance=Sum('balance_value'), sold=Sum('sold_value')
    )
    incentive_total = float(inc_agg['total'] or 0)
    incentive_balance = float(inc_agg['balance'] or 0)
    incentive_sold = float(inc_agg['sold'] or 0)

    # STEP 2 — trade money, from the canonical service, over EXACTLY the licence
    # set counted above.
    #
    # This replaced a pair of global aggregates that ran
    # ``Sum(LicenseTrade.total_amount)`` across every trade in the date range.
    # Three things were wrong with that, all of them silent:
    #
    #   * it was not restricted to the licences the summary was reporting on, so
    #     a licence filtered out by exporter/norm/balance still contributed its
    #     money to the totals;
    #   * `total_amount` is the WHOLE trade, so a trade covering three licences
    #     was counted three times — once per licence family it touched — and the
    #     "profit" moved when unrelated licences were filtered;
    #   * it selected trades by `invoice_date` alone, which is period ACTIVITY,
    #     while the licence count beside it used licence ELIGIBILITY. The two
    #     halves of the same summary answered two different questions.
    #
    # Per-licence line amounts, summed from the same entries the list prints,
    # make the summary a total OF the list rather than a second opinion about it.
    dfia_totals = LicenseLedgerAccountingService.calculate_period_profit_loss(
        dfia_ids=dfia_qs.values_list('id', flat=True),
        period=period,
        company_id=company_id,
    )
    inc_totals = LicenseLedgerAccountingService.calculate_period_profit_loss(
        incentive_ids=incentive_qs.values_list('id', flat=True),
        period=period,
        company_id=company_id,
    )
    dfia_purchases = dfia_totals['purchase_total']
    dfia_sales = dfia_totals['sale_total']
    inc_purchases = inc_totals['purchase_total']
    inc_sales = inc_totals['sale_total']

    return {
        'dfia': {
            'total_licenses': dfia_qs.count(),
            'total_value_usd': round(dfia_total, 2),
            'sold_value_usd': round(dfia_sold, 2),
            'balance_value_usd': round(dfia_balance, 2),
            'purchase_amount_inr': round(float(dfia_purchases), 2),
            'sale_amount_inr': round(float(dfia_sales), 2),
            'profit_loss_inr': round(float(dfia_totals['profit_loss']), 2),
            # Disclosed so the period figures above are readable as a movement:
            # opening + purchases − sales == closing.
            'opening_position_inr': round(float(dfia_totals['opening_position']), 2),
            'closing_position_inr': round(float(dfia_totals['closing_position']), 2),
        },
        'incentive': {
            'total_licenses': incentive_qs.count(),
            'total_value_inr': round(incentive_total, 2),
            'sold_value_inr': round(incentive_sold, 2),
            'balance_value_inr': round(incentive_balance, 2),
            'purchase_amount_inr': round(float(inc_purchases), 2),
            'sale_amount_inr': round(float(inc_sales), 2),
            'profit_loss_inr': round(float(inc_totals['profit_loss']), 2),
            'opening_position_inr': round(float(inc_totals['opening_position']), 2),
            'closing_position_inr': round(float(inc_totals['closing_position']), 2),
            'breakdown': get_incentive_breakdown(incentive_qs),
        },
    }


# ---------------------------------------------------------------------------
# Company-wise aggregation
# ---------------------------------------------------------------------------

def search_licenses(query_params) -> dict:
    """
    Search across DFIA + Incentive licenses by license number or exporter name.

    Returns ``{'count': int, 'query': str, 'license_type': str, 'results': list}``.
    Returns ``None`` when no query is provided (caller should return 400).
    """
    query = _get_text_param(query_params, 'q')
    license_type = _get_license_type(query_params)
    active_only = _get_bool_param(query_params, 'active_only', default=True)
    min_balance = _parse_decimal(_get_text_param(query_params, 'min_balance'))

    if not query:
        return None

    results = []

    if license_type in {'ALL', DFIA_LICENSE_TYPE}:
        dfia_qs = LicenseDetailsModel.objects.select_related('exporter', 'port').filter(
            Q(license_number__icontains=query) | Q(exporter__name__icontains=query)
        )
        if active_only:
            dfia_qs = dfia_qs.filter(flags__is_expired=False)
        if min_balance is not None:
            dfia_qs = dfia_qs.filter(id__in=_dfia_ids_with_min_live_balance(dfia_qs, min_balance))
        results.extend(prepare_dfia_data(dfia_qs[:50]))

    if license_type in {'ALL', *INCENTIVE_LICENSE_TYPES}:
        incentive_qs = IncentiveLicense.objects.select_related('exporter', 'port_code').filter(
            Q(license_number__icontains=query) | Q(exporter__name__icontains=query)
        )
        if active_only:
            incentive_qs = incentive_qs.filter(
                is_active=True, license_expiry_date__gte=timezone.now().date()
            )
        if license_type not in {'ALL', INCENTIVE_LICENSE_TYPE}:
            incentive_qs = incentive_qs.filter(license_type=license_type)
        if min_balance is not None:
            incentive_qs = incentive_qs.filter(balance_value__gte=min_balance)
        results.extend(prepare_incentive_data(incentive_qs[:50]))

    results.sort(key=lambda x: x.get('license_date') or date.min, reverse=True)
    return {'count': len(results), 'query': query, 'license_type': license_type, 'results': results}


def get_company_wise_trades(query_params) -> dict:
    """
    The period's trades grouped by COMPANY, with a grand summary.

    Same licences, same transactions, same money as `get_license_wise_trades` —
    the two differ ONLY in whether company or licence is the outer grouping key.
    Both read the identical `build_ledger_dataset` result, so they cannot report
    different totals for the same filters (asserted by the cross-endpoint
    reconciliation test).

    WHAT THIS REPLACED: an implementation that accepted nothing but ``search``.
    It applied no period, no company, no licence-type, no active/balance/norm/
    purchase-status filter, and summed ``LicenseTrade.total_amount`` — the WHOLE
    trade — so a January request and a February request returned byte-identical
    lifetime totals, and any trade spanning several licences was counted once
    per licence family it touched.
    """
    dataset = _ledger_dataset(query_params)
    period_label = dataset['period']

    companies_dict: dict = {}
    for (license_type, license_id), entry in dataset['activity'].items():
        meta = dataset['index'].get((license_type, license_id), {})
        for company in entry['companies'].values():
            bucket = companies_dict.get(company['company_id'])
            if bucket is None:
                bucket = {
                    'company_id': company['company_id'],
                    'company_name': company['company_name'],
                    'purchases': [],
                    'sales': [],
                    'purchase_total': DECIMAL_ZERO,
                    'sale_total': DECIMAL_ZERO,
                }
                companies_dict[company['company_id']] = bucket

            for key in ('purchases', 'sales'):
                for row in company[key]:
                    bucket[key].append({
                        'trade_id': row['trade_id'],
                        'license_ids': [license_id],
                        'licenses': [meta.get('license_number', '')],
                        'license_type': meta.get('license_type', license_type),
                        'invoice_date': _iso_or_dash(row['date']),
                        'amount': float(row['amount']),
                    })
            bucket['purchase_total'] += company['purchase_total']
            bucket['sale_total'] += company['sale_total']

    companies = []
    for c in sorted(companies_dict.values(), key=lambda x: x['company_name'] or ''):
        c['purchases'].sort(key=_trade_row_sort_key)
        c['sales'].sort(key=_trade_row_sort_key)
        c['profit_loss'] = float(net_of(c['sale_total'], c['purchase_total']))
        c['purchase_total'] = float(c['purchase_total'])
        c['sale_total'] = float(c['sale_total'])
        companies.append(c)

    totals = dataset['totals']
    return {
        'companies': companies,
        'summary': {
            'total_companies': len(companies),
            'total_purchase': float(totals['purchase_total']),
            'total_sale': float(totals['sale_total']),
            'profit_loss': float(totals['profit_loss']),
            'opening_position': float(totals['opening_position']),
            'closing_position': float(totals['closing_position']),
        },
        'period': {
            'start_date': _iso_or_none(period_label.start),
            'end_date': _iso_or_none(period_label.end),
        },
    }


# ---------------------------------------------------------------------------
# License-wise aggregation
# ---------------------------------------------------------------------------

def get_license_wise_trades(query_params) -> dict:
    """
    Return trades grouped by license, then by company within each license.
    Accepts a dict-like ``query_params``.
    """
    from apps.trade.models import LicenseTrade

    search = _get_text_param(query_params, 'search')
    terms = [t.strip() for t in search.split(',') if t.strip()] if search else []
    license_type = _get_license_type(query_params)
    purchase_date_from = _parse_iso_date(_get_text_param(query_params, 'purchase_date_from'))
    purchase_date_to = _parse_iso_date(_get_text_param(query_params, 'purchase_date_to'))
    company_id = _parse_int(_get_text_param(query_params, 'company'))
    is_active_only = _get_bool_param(query_params, 'active_only', default=True)
    min_balance = _parse_decimal(_get_text_param(query_params, 'min_balance'))
    norm = _get_norm_param(query_params)
    purchase_status = _get_purchase_status_param(query_params)
    ordering = _get_text_param(query_params, 'ordering', '-license_date')

    # Pre-compute allowed license IDs (license number OR exporter name) to avoid JOIN fan-out
    allowed_dfia_ids = None
    allowed_inc_ids = None
    if terms and len(terms) == 1:
        t = terms[0]
        allowed_dfia_ids = set(
            LicenseDetailsModel.objects.filter(
                Q(license_number__icontains=t) | Q(exporter__name__icontains=t)
            ).values_list('id', flat=True)
        )
        allowed_inc_ids = set(
            IncentiveLicense.objects.filter(
                Q(license_number__icontains=t) | Q(exporter__name__icontains=t)
            ).values_list('id', flat=True)
        )
    elif terms:  # multiple comma-separated exact terms — exact license number match only
        allowed_dfia_ids = set(
            LicenseDetailsModel.objects.filter(license_number__in=terms).values_list('id', flat=True)
        )
        allowed_inc_ids = set(
            IncentiveLicense.objects.filter(license_number__in=terms).values_list('id', flat=True)
        )

    qs = LicenseTrade.objects.select_related('from_company', 'to_company').prefetch_related(
        'lines__sr_number__license',
        'incentive_lines__incentive_license',
    ).filter(direction__in=TRADE_DIRECTIONS)

    if license_type and license_type != 'ALL':
        if license_type == INCENTIVE_LICENSE_TYPE:
            qs = qs.filter(license_type=INCENTIVE_LICENSE_TYPE)
        else:
            qs = qs.filter(license_type=license_type)
    if purchase_date_from:
        qs = qs.filter(invoice_date__gte=purchase_date_from)
    if purchase_date_to:
        qs = qs.filter(invoice_date__lte=purchase_date_to)

    if allowed_dfia_ids is not None or allowed_inc_ids is not None:
        qs = qs.filter(
            Q(lines__sr_number__license_id__in=(allowed_dfia_ids or set()))
            | Q(incentive_lines__incentive_license_id__in=(allowed_inc_ids or set()))
        ).distinct()

    if company_id:
        # Restrict to trades where the selected company is in the role that the loop assigns
        # to the `company` variable:
        #   PURCHASE → company = trade.to_company  (the buyer)
        #   SALE     → company = trade.from_company (the seller)
        # Using the broader  Q(from|to_company_id=company_id)  pulled in trades where the
        # company was the *counterparty*, causing NEELKANTH IMPEX / LABDHI GLOBAL LLP etc.
        # to appear even when only LABDHI MERCANTILE LLP was selected.
        qs = qs.filter(
            Q(direction='PURCHASE', to_company_id=company_id)
            | Q(direction='SALE', from_company_id=company_id)
        )

    licenses_dict: dict = {}

    for trade in qs:
        company = trade.to_company if trade.direction == 'PURCHASE' else trade.from_company
        if not company:
            continue

        license_amounts: dict = {}
        if trade.license_type == 'DFIA':
            lic_entries = list({
                (
                    line.sr_number.license.id,
                    line.sr_number.license.license_number,
                    str(line.sr_number.license.license_date) if line.sr_number.license.license_date else '-',
                    trade.license_type,
                )
                for line in trade.lines.all()
                if line.sr_number and line.sr_number.license
                and (allowed_dfia_ids is None or line.sr_number.license.id in allowed_dfia_ids)
            })
            for line in trade.lines.all():
                if line.sr_number and line.sr_number.license:
                    _lid = line.sr_number.license.id
                    license_amounts[_lid] = license_amounts.get(_lid, Decimal('0')) + (line.amount_inr or Decimal('0'))
        else:
            lic_entries = list({
                (
                    tl.incentive_license.id,
                    tl.incentive_license.license_number,
                    str(tl.incentive_license.license_date) if tl.incentive_license.license_date else '-',
                    trade.license_type,
                )
                for tl in trade.incentive_lines.all()
                if tl.incentive_license
                and (allowed_inc_ids is None or tl.incentive_license.id in allowed_inc_ids)
            })
            for tl in trade.incentive_lines.all():
                if tl.incentive_license:
                    _lid = tl.incentive_license.id
                    license_amounts[_lid] = license_amounts.get(_lid, Decimal('0')) + (tl.amount_inr or Decimal('0'))

        for lic_id, lic_num, lic_date, lic_type in lic_entries:
            if lic_id not in licenses_dict:
                licenses_dict[lic_id] = {
                    'license_id': lic_id,
                    'license_number': lic_num,
                    'license_date': lic_date,
                    'license_type': lic_type,
                    'companies': {},
                }

            cid = company.id
            if cid not in licenses_dict[lic_id]['companies']:
                licenses_dict[lic_id]['companies'][cid] = {
                    'company_id': cid,
                    'company_name': company.name,
                    'purchases': [],
                    'sales': [],
                    'purchase_total': Decimal('0'),
                    'sale_total': Decimal('0'),
                }

            amount = license_amounts.get(lic_id, Decimal('0'))
            row = {
                'trade_id': trade.id,
                'invoice_date': str(trade.invoice_date) if trade.invoice_date else '-',
                'amount': float(amount),
            }
            if trade.direction == 'PURCHASE':
                licenses_dict[lic_id]['companies'][cid]['purchases'].append(row)
                licenses_dict[lic_id]['companies'][cid]['purchase_total'] += amount
            else:
                licenses_dict[lic_id]['companies'][cid]['sales'].append(row)
                licenses_dict[lic_id]['companies'][cid]['sale_total'] += amount

    # Post-filter: active_only
    if is_active_only and licenses_dict:
        active_dfia_ids = set(
            LicenseDetailsModel.objects.filter(flags__is_expired=False)
            .values_list('id', flat=True)
        )
        active_inc_ids = set(
            IncentiveLicense.objects.filter(
                is_active=True, license_expiry_date__gte=timezone.now().date()
            ).values_list('id', flat=True)
        )
        licenses_dict = {
            lid: ld for lid, ld in licenses_dict.items()
            if (ld['license_type'] == DFIA_LICENSE_TYPE and lid in active_dfia_ids)
            or (ld['license_type'] != DFIA_LICENSE_TYPE and lid in active_inc_ids)
        }

    # Post-filter: min_balance. BL-LEDGER-02: resolve DFIA balance LIVE,
    # scoped to only the DFIA ids already present in `licenses_dict` (not
    # the whole table) -- fixed number of queries either way, but a
    # smaller, more relevant candidate set.
    if min_balance is not None and licenses_dict:
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        dfia_ids_in_result = [
            lid for lid, ld in licenses_dict.items() if ld['license_type'] == DFIA_LICENSE_TYPE
        ]
        live_balance_map = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(dfia_ids_in_result)
        dfia_ids_above = {
            lid for lid in dfia_ids_in_result
            if live_balance_map.get(lid, DECIMAL_ZERO) >= min_balance
        }
        inc_ids_above = set(
            IncentiveLicense.objects.filter(balance_value__gte=min_balance)
            .values_list('id', flat=True)
        )
        licenses_dict = {
            lid: ld for lid, ld in licenses_dict.items()
            if (ld['license_type'] == DFIA_LICENSE_TYPE and lid in dfia_ids_above)
            or (ld['license_type'] != DFIA_LICENSE_TYPE and lid in inc_ids_above)
        }

    # Post-filter: norm (DFIA/export-item concept only — every Incentive
    # license is dropped once a norm filter is active, see `_get_norm_param`).
    if norm and licenses_dict:
        dfia_ids_with_norm = set(
            LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class=norm)
            .values_list('id', flat=True)
        )
        licenses_dict = {
            lid: ld for lid, ld in licenses_dict.items()
            if ld['license_type'] == DFIA_LICENSE_TYPE and lid in dfia_ids_with_norm
        }

    # Post-filter: purchase_status (DFIA-only concept — every Incentive
    # license is dropped once active, see `_get_purchase_status_param`).
    if purchase_status and licenses_dict:
        dfia_ids_with_status = set(
            LicenseDetailsModel.objects.filter(purchase_status__code=purchase_status)
            .values_list('id', flat=True)
        )
        licenses_dict = {
            lid: ld for lid, ld in licenses_dict.items()
            if ld['license_type'] == DFIA_LICENSE_TYPE and lid in dfia_ids_with_status
        }

    # Ordering
    reverse = ordering.startswith('-')
    order_field = ordering.lstrip('-')

    if order_field == 'balance_value' and licenses_dict:
        # BL-LEDGER-02: sort key must use the LIVE DFIA balance, not the
        # cached column -- scoped to only the DFIA ids in this result set.
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        dfia_ids_in_result = [
            lid for lid, ld in licenses_dict.items() if ld['license_type'] == DFIA_LICENSE_TYPE
        ]
        dfia_bal = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(dfia_ids_in_result)
        inc_bal = dict(
            IncentiveLicense.objects.filter(id__in=licenses_dict)
            .values_list('id', 'balance_value')
        )
        def _bal_key(ld):
            lid = ld['license_id']
            v = dfia_bal.get(lid) or inc_bal.get(lid)
            return float(v) if v is not None else 0.0
        sorted_licenses = sorted(licenses_dict.values(), key=_bal_key, reverse=reverse)
    else:
        sorted_licenses = sorted(
            licenses_dict.values(),
            key=lambda ld: ld.get('license_date') or '',
            reverse=reverse,
        )

    result = []
    for lic in sorted_licenses:
        companies = []
        for c in sorted(lic['companies'].values(), key=lambda x: x['company_name']):
            pt = c['purchase_total']
            st = c['sale_total']
            c['purchase_total'] = float(pt)
            c['sale_total'] = float(st)
            c['profit_loss'] = float(st - pt)
            companies.append(c)
        lic['companies'] = companies
        result.append(lic)

    return {'licenses': result}
