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

logger = logging.getLogger(__name__)

DFIA_LICENSE_TYPE = "DFIA"
INCENTIVE_LICENSE_TYPE = "INCENTIVE"
INCENTIVE_SUBTYPES = ("RODTEP", "ROSTL", "MEIS")
INCENTIVE_LICENSE_TYPES = frozenset({INCENTIVE_LICENSE_TYPE, *INCENTIVE_SUBTYPES})
ALL_LICENSE_TYPES = frozenset({"ALL", DFIA_LICENSE_TYPE, *INCENTIVE_LICENSE_TYPES})
TRADE_DIRECTIONS = ("PURCHASE", "SALE")
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
DECIMAL_ZERO = Decimal("0")


def _get_text_param(query_params, name: str, default: str = "") -> str:
    value = query_params.get(name, default)
    if value is None:
        return default
    return str(value).strip()


def _get_license_type(query_params) -> str:
    license_type = _get_text_param(query_params, "license_type", "ALL").upper()
    return license_type if license_type in ALL_LICENSE_TYPES else "ALL"


def _get_bool_param(query_params, name: str, *, default: bool = False) -> bool:
    value = query_params.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in TRUE_VALUES


def _parse_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _parse_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_iso_date(value) -> date | None:
    if value in (None, ""):
        return None
    try:
        return parse_date(str(value).strip())
    except ValueError:
        return None


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
# Data-preparation helpers (previously private viewset methods)
# ---------------------------------------------------------------------------

def prepare_dfia_data(queryset) -> list:
    """
    Annotate a DFIA queryset with trade aggregates and return a list of dicts.
    Uses 2 batched group-by queries instead of 4N individual queries.
    """
    from apps.trade.models import LicenseTrade

    # Accept either a QuerySet or a plain list of model instances.
    licenses = _as_model_list(queryset, 'exporter', 'port')
    if not licenses:
        return []

    license_ids = [lic.id for lic in licenses]

    purchase_totals = (
        LicenseTrade.objects
        .filter(license_type=DFIA_LICENSE_TYPE, direction='PURCHASE', lines__sr_number__license_id__in=license_ids)
        .values('lines__sr_number__license_id')
        .annotate(total_inr=Sum('lines__amount_inr'), total_usd=Sum('lines__cif_fc'))
    )
    sale_totals = (
        LicenseTrade.objects
        .filter(license_type=DFIA_LICENSE_TYPE, direction='SALE', lines__sr_number__license_id__in=license_ids)
        .values('lines__sr_number__license_id')
        .annotate(total_inr=Sum('lines__amount_inr'), total_usd=Sum('lines__cif_fc'))
    )

    purchase_map = {r['lines__sr_number__license_id']: r for r in purchase_totals}
    sale_map = {r['lines__sr_number__license_id']: r for r in sale_totals}

    data = []
    for license in licenses:
        pur_row = purchase_map.get(license.id, {})
        sal_row = sale_map.get(license.id, {})

        purchase_amount_inr = float(pur_row.get('total_inr') or 0)
        purchase_amount_usd = float(pur_row.get('total_usd') or 0)
        sale_amount_inr = float(sal_row.get('total_inr') or 0)
        sale_amount_usd = float(sal_row.get('total_usd') or 0)

        profit_loss = sale_amount_inr - purchase_amount_inr
        balance_usd = purchase_amount_usd - sale_amount_usd

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
            'purchase_amount': purchase_amount_inr,
            'sale_amount': sale_amount_inr,
            'profit_loss': profit_loss,
            'currency': 'USD',
            'is_expired': license.is_expired,
            'is_active': not license.is_expired,
            'sold_status': get_sold_status(purchase_amount_usd, balance_usd),
        })
    return data


def prepare_incentive_data(queryset) -> list:
    """
    Annotate an Incentive queryset with trade aggregates and return a list of dicts.
    """
    from apps.trade.models import LicenseTrade

    licenses = _as_model_list(queryset, 'exporter', 'port_code')
    if not licenses:
        return []

    license_ids = [lic.id for lic in licenses]
    today = timezone.now().date()

    purchase_totals = (
        LicenseTrade.objects
        .filter(
            license_type=INCENTIVE_LICENSE_TYPE,
            direction='PURCHASE',
            incentive_lines__incentive_license_id__in=license_ids,
        )
        .values('incentive_lines__incentive_license_id')
        .annotate(total_inr=Sum('incentive_lines__amount_inr'), total_value=Sum('incentive_lines__license_value'))
    )
    sale_totals = (
        LicenseTrade.objects
        .filter(
            license_type=INCENTIVE_LICENSE_TYPE,
            direction='SALE',
            incentive_lines__incentive_license_id__in=license_ids,
        )
        .values('incentive_lines__incentive_license_id')
        .annotate(total_inr=Sum('incentive_lines__amount_inr'), total_value=Sum('incentive_lines__license_value'))
    )

    purchase_map = {r['incentive_lines__incentive_license_id']: r for r in purchase_totals}
    sale_map = {r['incentive_lines__incentive_license_id']: r for r in sale_totals}

    data = []
    for license in licenses:
        pur_row = purchase_map.get(license.id, {})
        sal_row = sale_map.get(license.id, {})

        purchase_amount_inr = float(pur_row.get('total_inr') or 0)
        purchase_value_inr = float(pur_row.get('total_value') or 0)
        sale_amount_inr = float(sal_row.get('total_inr') or 0)
        sale_value_inr = float(sal_row.get('total_value') or 0)

        profit_loss = sale_amount_inr - purchase_amount_inr
        balance_inr = purchase_value_inr - sale_value_inr

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
            'purchase_amount': purchase_amount_inr,
            'sale_amount': sale_amount_inr,
            'profit_loss': profit_loss,
            'currency': 'INR',
            'is_expired': license.license_expiry_date < today if license.license_expiry_date else False,
            'is_active': license.is_active,
            'sold_status': get_sold_status(purchase_value_inr, balance_inr),
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
    """
    from apps.trade.models import LicenseTrade

    license_type = _get_license_type(query_params)
    min_balance = _parse_decimal(_get_text_param(query_params, 'min_balance'))
    exporter_id = _parse_int(_get_text_param(query_params, 'exporter'))
    company_id = _parse_int(_get_text_param(query_params, 'company'))
    no_purchases = _get_bool_param(query_params, 'no_purchases')
    is_active_only = _get_bool_param(query_params, 'active_only', default=True)
    purchase_date_from = _parse_iso_date(_get_text_param(query_params, 'purchase_date_from'))
    purchase_date_to = _parse_iso_date(_get_text_param(query_params, 'purchase_date_to'))

    dfia_qs = LicenseDetailsModel.objects.select_related('exporter', 'port').all()
    incentive_qs = IncentiveLicense.objects.select_related('exporter', 'port_code').all()

    if is_active_only and not company_id:
        dfia_qs = dfia_qs.filter(flags__is_expired=False)
        incentive_qs = incentive_qs.filter(
            is_active=True, license_expiry_date__gte=timezone.now().date()
        )

    if exporter_id:
        dfia_qs = dfia_qs.filter(exporter_id=exporter_id)
        incentive_qs = incentive_qs.filter(exporter_id=exporter_id)

    if min_balance is not None:
        dfia_qs = dfia_qs.filter(balance__balance_cif__gte=min_balance)
        incentive_qs = incentive_qs.filter(balance_value__gte=min_balance)

    if (purchase_date_from or purchase_date_to) and not company_id:
        dfia_pf: dict = {}
        inc_pf: dict = {}
        for param, key in [(purchase_date_from, 'invoice_date__gte'), (purchase_date_to, 'invoice_date__lte')]:
            if param:
                dfia_pf[key] = param
                inc_pf[key] = param
        if dfia_pf:
            ids = LicenseTrade.objects.filter(
                license_type=DFIA_LICENSE_TYPE, direction='PURCHASE', **dfia_pf
            ).values_list('lines__sr_number__license_id', flat=True).distinct()
            dfia_qs = dfia_qs.filter(id__in=ids)
        if inc_pf:
            ids = LicenseTrade.objects.filter(
                license_type=INCENTIVE_LICENSE_TYPE, direction='PURCHASE', **inc_pf
            ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()
            incentive_qs = incentive_qs.filter(id__in=ids)

    if company_id:
        dfia_ids = LicenseTrade.objects.filter(
            Q(from_company_id=company_id) | Q(to_company_id=company_id), license_type=DFIA_LICENSE_TYPE
        ).values_list('lines__sr_number__license_id', flat=True).distinct()
        inc_ids = LicenseTrade.objects.filter(
            Q(from_company_id=company_id) | Q(to_company_id=company_id), license_type=INCENTIVE_LICENSE_TYPE
        ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()
        dfia_qs = dfia_qs.filter(id__in=dfia_ids)
        incentive_qs = incentive_qs.filter(id__in=inc_ids)
    elif query_params.get('company'):
        logger.warning("Invalid company_id: %s", query_params.get('company'))

    if no_purchases:
        dfia_with = LicenseTrade.objects.filter(
            license_type=DFIA_LICENSE_TYPE, direction='PURCHASE'
        ).values_list('lines__sr_number__license_id', flat=True).distinct()
        inc_with = LicenseTrade.objects.filter(
            license_type=INCENTIVE_LICENSE_TYPE, direction='PURCHASE'
        ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()
        dfia_qs = dfia_qs.exclude(id__in=dfia_with)
        incentive_qs = incentive_qs.exclude(id__in=inc_with)

    if license_type == DFIA_LICENSE_TYPE:
        return prepare_dfia_data(dfia_qs)
    if license_type in INCENTIVE_LICENSE_TYPES:
        if license_type != INCENTIVE_LICENSE_TYPE:
            incentive_qs = incentive_qs.filter(license_type=license_type)
        return prepare_incentive_data(incentive_qs)
    combined = list(prepare_dfia_data(dfia_qs)) + list(prepare_incentive_data(incentive_qs))
    combined.sort(key=lambda x: x.get('license_date') or date.min, reverse=True)
    return combined


# ---------------------------------------------------------------------------
# Summary service
# ---------------------------------------------------------------------------

def get_ledger_summary(query_params) -> dict:
    """
    Compute summary statistics for the ledger.

    Accepts a dict-like object (e.g. ``request.query_params``).
    Returns a plain dict suitable for ``Response(…)``.
    """
    from apps.trade.models import LicenseTrade

    company_id = _parse_int(_get_text_param(query_params, 'company'))
    license_type = _get_license_type(query_params)
    is_active_only = _get_bool_param(query_params, 'active_only', default=True)
    min_balance = _parse_decimal(_get_text_param(query_params, 'min_balance'))
    purchase_date_from = _parse_iso_date(_get_text_param(query_params, 'purchase_date_from'))
    purchase_date_to = _parse_iso_date(_get_text_param(query_params, 'purchase_date_to'))

    # Base querysets
    if is_active_only:
        dfia_qs = LicenseDetailsModel.objects.filter(flags__is_expired=False)
        incentive_qs = IncentiveLicense.objects.filter(
            is_active=True, license_expiry_date__gte=timezone.now().date()
        )
    else:
        dfia_qs = LicenseDetailsModel.objects.all()
        incentive_qs = IncentiveLicense.objects.all()

    if min_balance is not None:
        dfia_qs = dfia_qs.filter(balance__balance_cif__gte=min_balance)
        incentive_qs = incentive_qs.filter(balance_value__gte=min_balance)

    # Date-range filter on license IDs via trade dates
    if purchase_date_from or purchase_date_to:
        dfia_f: dict = {}
        inc_f: dict = {}
        if purchase_date_from:
            dfia_f['invoice_date__gte'] = purchase_date_from
            inc_f['invoice_date__gte'] = purchase_date_from
        if purchase_date_to:
            dfia_f['invoice_date__lte'] = purchase_date_to
            inc_f['invoice_date__lte'] = purchase_date_to
        if dfia_f:
            ids = LicenseTrade.objects.filter(
                license_type=DFIA_LICENSE_TYPE, direction='PURCHASE', **dfia_f
            ).values_list('lines__sr_number__license_id', flat=True).distinct()
            dfia_qs = dfia_qs.filter(id__in=ids)
        if inc_f:
            ids = LicenseTrade.objects.filter(
                license_type=INCENTIVE_LICENSE_TYPE, direction='PURCHASE', **inc_f
            ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()
            incentive_qs = incentive_qs.filter(id__in=ids)

    # Company filter
    if company_id:
        dfia_ids = LicenseTrade.objects.filter(
            Q(from_company_id=company_id) | Q(to_company_id=company_id), license_type=DFIA_LICENSE_TYPE
        ).values_list('lines__sr_number__license_id', flat=True).distinct()
        inc_ids = LicenseTrade.objects.filter(
            Q(from_company_id=company_id) | Q(to_company_id=company_id), license_type=INCENTIVE_LICENSE_TYPE
        ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()
        dfia_qs = dfia_qs.filter(id__in=dfia_ids)
        incentive_qs = incentive_qs.filter(id__in=inc_ids)
    elif query_params.get('company'):
        logger.warning("Invalid company_id in summary: %s", query_params.get('company'))

    # License-type filter
    if license_type != 'ALL':
        if license_type == DFIA_LICENSE_TYPE:
            incentive_qs = IncentiveLicense.objects.none()
        elif license_type in INCENTIVE_LICENSE_TYPES:
            dfia_qs = LicenseDetailsModel.objects.none()
            if license_type != INCENTIVE_LICENSE_TYPE:
                incentive_qs = incentive_qs.filter(license_type=license_type)

    # DFIA aggregates
    _opening_rows = dfia_qs.annotate(
        _opening=Coalesce(Sum('export_license__cif_fc'), Value(DECIMAL_ZERO), output_field=DecimalField())
    ).values_list('_opening', flat=True)
    dfia_total = sum(float(v or 0) for v in _opening_rows)
    dfia_balance = float(dfia_qs.aggregate(balance=Sum('balance__balance_cif'))['balance'] or 0)
    dfia_sold = dfia_total - dfia_balance

    # Incentive aggregates
    inc_agg = incentive_qs.aggregate(
        total=Sum('license_value'), balance=Sum('balance_value'), sold=Sum('sold_value')
    )
    incentive_total = float(inc_agg['total'] or 0)
    incentive_balance = float(inc_agg['balance'] or 0)
    incentive_sold = float(inc_agg['sold'] or 0)

    # Trade-amount aggregates
    dfia_tf: dict = {'license_type': DFIA_LICENSE_TYPE}
    inc_tf: dict = {'license_type': INCENTIVE_LICENSE_TYPE}
    for field, param in [('invoice_date__gte', purchase_date_from), ('invoice_date__lte', purchase_date_to)]:
        if param:
            dfia_tf[field] = param
            inc_tf[field] = param

    def _sum(qs_filter, direction):
        return LicenseTrade.objects.filter(direction=direction, **qs_filter).aggregate(
            total=Sum('total_amount')
        )['total'] or 0

    if company_id:
        cq = Q(from_company_id=company_id) | Q(to_company_id=company_id)
        dfia_purchases = LicenseTrade.objects.filter(
            cq, direction='PURCHASE', **dfia_tf
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        dfia_sales = LicenseTrade.objects.filter(
            cq, direction='SALE', **dfia_tf
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        inc_purchases = LicenseTrade.objects.filter(
            cq, direction='PURCHASE', **inc_tf
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        inc_sales = LicenseTrade.objects.filter(
            cq, direction='SALE', **inc_tf
        ).aggregate(total=Sum('total_amount'))['total'] or 0
    else:
        dfia_purchases = _sum(dfia_tf, 'PURCHASE')
        dfia_sales = _sum(dfia_tf, 'SALE')
        inc_purchases = _sum(inc_tf, 'PURCHASE')
        inc_sales = _sum(inc_tf, 'SALE')

    return {
        'dfia': {
            'total_licenses': dfia_qs.count(),
            'total_value_usd': round(dfia_total, 2),
            'sold_value_usd': round(dfia_sold, 2),
            'balance_value_usd': round(dfia_balance, 2),
            'purchase_amount_inr': round(float(dfia_purchases), 2),
            'sale_amount_inr': round(float(dfia_sales), 2),
            'profit_loss_inr': round(float(dfia_sales) - float(dfia_purchases), 2),
        },
        'incentive': {
            'total_licenses': incentive_qs.count(),
            'total_value_inr': round(incentive_total, 2),
            'sold_value_inr': round(incentive_sold, 2),
            'balance_value_inr': round(incentive_balance, 2),
            'purchase_amount_inr': round(float(inc_purchases), 2),
            'sale_amount_inr': round(float(inc_sales), 2),
            'profit_loss_inr': round(float(inc_sales) - float(inc_purchases), 2),
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
            dfia_qs = dfia_qs.filter(balance__balance_cif__gte=min_balance)
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
    Return all trades grouped by company with purchases, sales, and a grand summary.
    Accepts a dict-like ``query_params``.
    """
    from apps.trade.models import LicenseTrade

    search = _get_text_param(query_params, 'search')
    terms = [t.strip() for t in search.split(',') if t.strip()] if search else []

    qs = LicenseTrade.objects.select_related('from_company', 'to_company').prefetch_related(
        'lines__sr_number__license',
        'incentive_lines__incentive_license',
    ).filter(direction__in=TRADE_DIRECTIONS)

    if terms:
        if len(terms) == 1:
            t = terms[0]
            qs = qs.filter(
                Q(lines__sr_number__license__license_number__icontains=t)
                | Q(incentive_lines__incentive_license__license_number__icontains=t)
            ).distinct()
        else:
            qs = qs.filter(
                Q(lines__sr_number__license__license_number__in=terms)
                | Q(incentive_lines__incentive_license__license_number__in=terms)
            ).distinct()

    companies_dict: dict = {}

    for trade in qs:
        company = trade.to_company if trade.direction == 'PURCHASE' else trade.from_company
        if not company:
            continue

        cid = company.id
        if cid not in companies_dict:
            companies_dict[cid] = {
                'company_id': cid,
                'company_name': company.name,
                'purchases': [],
                'sales': [],
                'purchase_total': Decimal('0'),
                'sale_total': Decimal('0'),
            }

        if trade.license_type == 'DFIA':
            lic_pairs = list({
                (line.sr_number.license.id, line.sr_number.license.license_number)
                for line in trade.lines.all()
                if line.sr_number and line.sr_number.license
            })
        else:
            lic_pairs = list({
                (tl.incentive_license.id, tl.incentive_license.license_number)
                for tl in trade.incentive_lines.all()
                if tl.incentive_license
            })

        row = {
            'trade_id': trade.id,
            'license_ids': [p[0] for p in lic_pairs],
            'licenses': [p[1] for p in lic_pairs],
            'license_type': trade.license_type,
            'invoice_date': str(trade.invoice_date) if trade.invoice_date else '-',
            'amount': float(trade.total_amount or 0),
        }

        amount = trade.total_amount or Decimal('0')
        if trade.direction == 'PURCHASE':
            companies_dict[cid]['purchases'].append(row)
            companies_dict[cid]['purchase_total'] += amount
        else:
            companies_dict[cid]['sales'].append(row)
            companies_dict[cid]['sale_total'] += amount

    companies = []
    total_purchase = Decimal('0')
    total_sale = Decimal('0')

    for c in sorted(companies_dict.values(), key=lambda x: x['company_name']):
        pt = c['purchase_total']
        st = c['sale_total']
        c['purchase_total'] = float(pt)
        c['sale_total'] = float(st)
        c['profit_loss'] = float(st - pt)
        total_purchase += pt
        total_sale += st
        companies.append(c)

    return {
        'companies': companies,
        'summary': {
            'total_companies': len(companies),
            'total_purchase': float(total_purchase),
            'total_sale': float(total_sale),
            'profit_loss': float(total_sale - total_purchase),
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

    if terms:
        if len(terms) == 1:
            t = terms[0]
            qs = qs.filter(
                Q(lines__sr_number__license__license_number__icontains=t)
                | Q(incentive_lines__incentive_license__license_number__icontains=t)
            ).distinct()
        else:
            qs = qs.filter(
                Q(lines__sr_number__license__license_number__in=terms)
                | Q(incentive_lines__incentive_license__license_number__in=terms)
            ).distinct()

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
                and (not terms or any(t.lower() in line.sr_number.license.license_number.lower() for t in terms))
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
                and (not terms or any(t.lower() in tl.incentive_license.license_number.lower() for t in terms))
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

    result = []
    for lic in sorted(licenses_dict.values(), key=lambda x: x['license_number']):
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
