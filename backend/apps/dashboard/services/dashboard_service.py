"""
Dashboard aggregation service.

All queries are aggregate-only (Count/Sum/TruncMonth) — no full querysets
are ever materialised.  Results are cached globally for 5 minutes.

BillOfEntry model does not exist in the new backend yet; every code path
that would touch it is wrapped in try/except ImportError and gracefully
falls back to zero.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth

from apps.allotment.models import AllotmentModel
from apps.license.models.license import LicenseDetailsModel

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
CACHE_TTL = 60 * 5  # 5 minutes

# Module-level import to avoid re-running try/except on every call
try:
    from apps.bill_of_entry.models import BillOfEntryModel as _BillOfEntryModel  # type: ignore[import]
except ImportError:
    _BillOfEntryModel = None


def _boe_model():
    return _BillOfEntryModel


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def get_dashboard_stats(user: Any) -> dict:
    """
    Return a dict of KPI counts for the dashboard header cards.

    All keys are always present; unavailable aggregates default to 0.
    Result is cached per user for CACHE_TTL seconds.
    """
    # Global key — dashboard data is not per-user
    cache_key = "dashboard:stats:global"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    thirty_days_ahead = today + timedelta(days=30)

    # Single aggregate call replaces 6 separate COUNT queries against the
    # same LicenseDetailsModel table, eliminating the N+1 pattern.
    stats = LicenseDetailsModel.objects.aggregate(
        total=Count("pk"),
        active_licenses=Count(
            "pk",
            filter=Q(flags__is_expired=False, flags__is_null=False),
        ),
        expired_licenses=Count(
            "pk",
            filter=Q(flags__is_expired=True, flags__is_null=False),
        ),
        null_licenses=Count("pk", filter=Q(flags__is_null=True)),
        expiring_soon=Count(
            "pk",
            filter=Q(
                flags__is_active=True,
                license_expiry_date__gte=today,
                license_expiry_date__lte=thirty_days_ahead,
                balance__balance_cif__gte=Decimal("100.00"),
            ),
        ),
        total_balance_cif_sum=Sum("balance__balance_cif"),
        low_balance_licenses=Count(
            "pk",
            filter=Q(
                flags__is_active=True,
                balance__balance_cif__lt=Decimal("100.00"),
            ),
        ),
    )

    total_licenses = stats["total"]
    active_licenses = stats["active_licenses"]
    expired_licenses = stats["expired_licenses"]
    null_licenses = stats["null_licenses"]
    expiring_soon = stats["expiring_soon"]
    total_balance_cif = str(stats["total_balance_cif_sum"] or Decimal("0.00"))
    low_balance_licenses = stats["low_balance_licenses"]

    recent_allotments = AllotmentModel.objects.filter(
        modified_on__gte=thirty_days_ago,
    ).count()

    # BOE model may not exist yet
    recent_boes = 0
    _boe = _boe_model()
    if _boe is not None:
        try:
            recent_boes = _boe.objects.filter(
                created_on__gte=thirty_days_ago,
            ).count()
        except Exception:
            recent_boes = 0

    result = {
        "total_licenses": total_licenses,
        "active_licenses": active_licenses,
        "expired_licenses": expired_licenses,
        "null_licenses": null_licenses,
        "expiring_soon": expiring_soon,
        "total_balance_cif": total_balance_cif,
        "recent_boes": recent_boes,
        "recent_allotments": recent_allotments,
        "low_balance_licenses": low_balance_licenses,
    }
    cache.set(cache_key, result, CACHE_TTL)
    return result


def get_license_utilisation_chart(user: Any) -> list[dict]:
    """
    Top 10 licenses ranked by balance_cif descending.

    Returns: [{'license_number': str, 'balance_cif': str}, ...]
    """
    cache_key = "dashboard:utilisation:global"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    qs = (
        LicenseDetailsModel.objects
        .select_related("balance")
        .filter(balance__balance_cif__isnull=False)
        .order_by("-balance__balance_cif")[:10]
    )

    result = [
        {
            "license_number": lic.license_number,
            "balance_cif": str(lic.balance.balance_cif),
        }
        for lic in qs
    ]
    cache.set(cache_key, result, CACHE_TTL)
    return result


def get_monthly_activity(user: Any) -> list[dict]:
    """
    BOE + allotment counts per calendar month for the last 12 months.

    Builds a complete 12-month grid so months with zero activity still appear.
    Returns list sorted oldest-first:
      [{'month': 'Jan 2025', 'boe_count': N, 'allotment_count': N}, ...]
    """
    cache_key = "dashboard:activity:global"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    today = date.today()
    twelve_months_ago = today - timedelta(days=365)

    # ---- Allotment counts by month ----------------------------------------
    allotment_qs = (
        AllotmentModel.objects
        .filter(modified_on__gte=twelve_months_ago)
        .annotate(month=TruncMonth("modified_on"))
        .values("month")
        .annotate(count=Count("pk"))
        .order_by("month")
    )
    allotment_by_month: dict[tuple[int, int], int] = {
        (row["month"].year, row["month"].month): row["count"]
        for row in allotment_qs
    }

    # ---- BOE counts by month (graceful degradation) -----------------------
    boe_by_month: dict[tuple[int, int], int] = {}
    _boe = _boe_model()
    if _boe is not None:
        try:
            boe_qs = (
                _boe.objects
                .filter(created_on__gte=twelve_months_ago)
                .annotate(month=TruncMonth("created_on"))
                .values("month")
                .annotate(count=Count("pk"))
                .order_by("month")
            )
            boe_by_month = {
                (row["month"].year, row["month"].month): row["count"]
                for row in boe_qs
            }
        except Exception:
            boe_by_month = {}

    # ---- Build complete 12-month grid — oldest first ----------------------
    # Generate months oldest-first
    months = []
    current = today.replace(day=1)
    for _ in range(12):
        months.append(current)
        # Step back one month
        if current.month == 1:
            current = current.replace(year=current.year - 1, month=12)
        else:
            current = current.replace(month=current.month - 1)
    months.reverse()  # oldest first

    result = [
        {
            "month": m.strftime("%b %Y"),
            "boe_count": boe_by_month.get((m.year, m.month), 0),
            "allotment_count": allotment_by_month.get((m.year, m.month), 0),
        }
        for m in months
    ]

    cache.set(cache_key, result, CACHE_TTL)
    return result


def get_expiring_licenses(user: Any) -> list[dict]:
    """
    Licenses expiring within the next 30 days with a non-trivial balance.

    Returns up to 20 records ordered by soonest expiry first:
      [{'license_number': str, 'license_expiry_date': ISO str,
        'balance_cif': str, 'days_to_expiry': int}, ...]
    """
    cache_key = "dashboard:expiring:global"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    today = date.today()
    thirty_days_ahead = today + timedelta(days=30)

    qs = (
        LicenseDetailsModel.objects
        .select_related("balance", "flags")
        .filter(
            license_expiry_date__gte=today,
            license_expiry_date__lte=thirty_days_ahead,
            flags__is_active=True,
            balance__balance_cif__gte=Decimal("100.00"),
        )
        .order_by("license_expiry_date")[:20]
    )

    result = [
        {
            "license_number": lic.license_number,
            "license_expiry_date": lic.license_expiry_date.isoformat(),
            "balance_cif": str(lic.balance.balance_cif),
            "days_to_expiry": (lic.license_expiry_date - today).days,
        }
        for lic in qs
    ]

    cache.set(cache_key, result, CACHE_TTL)
    return result
