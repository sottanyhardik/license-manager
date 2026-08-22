"""Fresh License Ledger collection filtering over canonical licence datasets."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from apps.license.models import IncentiveLicense, LicenseDetailsModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.license_profit import (
    first_purchase_date_by_license,
    incentive_first_purchase_date_by_license,
)
from apps.trade.models import IncentiveTradeLine, LicenseTrade, LicenseTradeLine


# Public License Ledger filter contract.  Concrete incentive types come from
# the model's authoritative choices; the two aggregate values are report-only
# selectors and are never passed to a model field lookup.
LICENSE_TYPE_ALL = "ALL"
LICENSE_TYPE_DFIA = "DFIA"
LICENSE_TYPE_ALL_INCENTIVE = "ALL_INCENTIVE"
INCENTIVE_LICENSE_TYPES = frozenset(
    value for value, _label in IncentiveLicense.LICENSE_TYPE_CHOICES
)
LICENSE_LEDGER_TYPE_VALUES = frozenset({
    LICENSE_TYPE_ALL,
    LICENSE_TYPE_DFIA,
    LICENSE_TYPE_ALL_INCENTIVE,
    *INCENTIVE_LICENSE_TYPES,
})


def normalize_license_type_filter(value) -> str:
    """Validate and normalize the public License Ledger type selector.

    ``INCENTIVE`` was the former aggregate query token.  It remains a narrow
    compatibility alias, but all new clients receive/use ``ALL_INCENTIVE``.
    Unknown values must never broaden a request to all licences.
    """
    normalized = str(value or LICENSE_TYPE_ALL).strip().upper()
    if normalized == "INCENTIVE":
        normalized = LICENSE_TYPE_ALL_INCENTIVE
    if normalized not in LICENSE_LEDGER_TYPE_VALUES:
        raise ValidationError({
            "license_type": (
                f"Invalid license type '{value}'. Expected one of: "
                f"{', '.join(sorted(LICENSE_LEDGER_TYPE_VALUES))}."
            )
        })
    return normalized


@dataclass(frozen=True)
class LicenseLedgerFilters:
    company_id: int | None = None
    license_type: str = "ALL"
    min_balance: Decimal | None = None
    search: str = ""
    ordering: str = "-license_date"
    active_only: bool = False
    norm: str = ""
    purchase_status: str = ""
    purchase_bill: str = "ALL"
    purchase_date_from: object = None
    purchase_date_to: object = None
    license_numbers: tuple[str, ...] = ()
    exclude_license_numbers: tuple[str, ...] = ()

    @classmethod
    def from_query_params(cls, params):
        def text(name, default=""):
            value = params.get(name, default)
            return str(value).strip() if value is not None else default

        try:
            company_id = int(text("buying_company_id")) if text("buying_company_id") else None
        except ValueError:
            company_id = None
        try:
            min_balance = Decimal(text("min_balance")) if text("min_balance") else None
            if min_balance is not None and (not min_balance.is_finite() or min_balance < 0):
                min_balance = None
        except InvalidOperation:
            min_balance = None
        license_type = normalize_license_type_filter(text("license_type", LICENSE_TYPE_ALL))
        ordering = text("ordering", "-license_date")
        if ordering not in {"-license_date", "license_date", "-balance_value", "balance_value"}:
            ordering = "-license_date"
        purchase_bill = text("purchase_bill", "ALL").upper()
        if purchase_bill not in {"ALL", "WITH_PURCHASE_BILL", "NO_PURCHASE_BILL"}:
            purchase_bill = "ALL"
        license_numbers = tuple(dict.fromkeys(
            number.strip() for number in text("license_numbers").split(",") if number.strip()
        ))
        exclude_license_numbers = tuple(dict.fromkeys(
            number.strip() for number in text("exclude_license_numbers").split(",") if number.strip()
        ))
        return cls(
            company_id=company_id, license_type=license_type, min_balance=min_balance,
            search=text("search"), ordering=ordering,
            active_only=text("active_only", "false").lower() in {"1", "true", "yes", "on"},
            norm=text("norm"), purchase_status=text("purchase_status"),
            purchase_bill=purchase_bill,
            purchase_date_from=parse_date(text("purchase_date_from")),
            purchase_date_to=parse_date(text("purchase_date_to")),
            license_numbers=license_numbers,
            exclude_license_numbers=exclude_license_numbers,
        )


def _trade_scoped_ids(company_id):
    trades = LicenseTrade.objects.all()
    if company_id is not None:
        trades = trades.filter(Q(from_company_id=company_id) | Q(to_company_id=company_id))
    dfia = trades.filter(license_type="DFIA").values_list("lines__sr_number__license_id", flat=True)
    incentive = trades.filter(license_type="INCENTIVE").values_list("incentive_lines__incentive_license_id", flat=True)
    return dfia, incentive


def _apply_database_filters(filters, authorization_company_id):
    dfia_ids, incentive_ids = _trade_scoped_ids(authorization_company_id)
    dfia = LicenseDetailsModel.objects.filter(id__in=dfia_ids).distinct()
    incentive = IncentiveLicense.objects.filter(id__in=incentive_ids).distinct()

    if filters.company_id is not None:
        # A License Ledger company is the BUYER on a qualifying external
        # purchase.  Sale ownership, exporter and counterparty relationships
        # are deliberately excluded: they describe different company roles.
        company_trades = LicenseTrade.objects.filter(
            direction=LicenseTrade.DIR_PURCHASE,
            linked_trade__isnull=True,
            to_company_id=filters.company_id,
        )
        dfia = dfia.filter(id__in=company_trades.filter(license_type="DFIA").values("lines__sr_number__license_id"))
        incentive = incentive.filter(id__in=company_trades.filter(license_type="INCENTIVE").values("incentive_lines__incentive_license_id"))

    if filters.license_type == LICENSE_TYPE_DFIA:
        incentive = IncentiveLicense.objects.none()
    elif filters.license_type == LICENSE_TYPE_ALL_INCENTIVE or filters.license_type in INCENTIVE_LICENSE_TYPES:
        dfia = LicenseDetailsModel.objects.none()
        if filters.license_type != LICENSE_TYPE_ALL_INCENTIVE:
            incentive = incentive.filter(license_type=filters.license_type)

    if filters.active_only:
        today = timezone.localdate()
        dfia = dfia.filter(flags__is_active=True, flags__is_expired=False)
        incentive = incentive.filter(is_active=True, license_expiry_date__gte=today)
    if filters.search:
        match = Q(license_number__icontains=filters.search) | Q(exporter__name__icontains=filters.search)
        dfia, incentive = dfia.filter(match), incentive.filter(match)
    if filters.norm:
        dfia = dfia.filter(export_license__norm_class__norm_class=filters.norm).distinct()
        incentive = IncentiveLicense.objects.none()
    if filters.purchase_status:
        dfia = dfia.filter(purchase_status__code=filters.purchase_status)
        incentive = IncentiveLicense.objects.none()
    if filters.license_numbers:
        dfia = dfia.filter(license_number__in=filters.license_numbers)
        incentive = incentive.filter(license_number__in=filters.license_numbers)
    if filters.exclude_license_numbers:
        dfia = dfia.exclude(license_number__in=filters.exclude_license_numbers)
        incentive = incentive.exclude(license_number__in=filters.exclude_license_numbers)

    if filters.purchase_bill != "ALL":
        dfia_bill = LicenseTradeLine.objects.filter(
            sr_number__license_id=OuterRef("pk"), trade__direction="PURCHASE", amount_inr__gt=0,
        )
        incentive_bill = IncentiveTradeLine.objects.filter(
            incentive_license_id=OuterRef("pk"), trade__direction="PURCHASE", amount_inr__gt=0,
        )
        expected = filters.purchase_bill == "WITH_PURCHASE_BILL"
        dfia = dfia.annotate(has_purchase_bill_filter=Exists(dfia_bill)).filter(has_purchase_bill_filter=expected)
        incentive = incentive.annotate(has_purchase_bill_filter=Exists(incentive_bill)).filter(has_purchase_bill_filter=expected)
    return dfia, incentive


def build_filtered_license_ledger_data(params, *, authorization_company_id=None, license_ref=None):
    """Build one filtered canonical collection shared by UI, PDF and Excel."""
    if license_ref is not None:
        refs = [license_ref]
        first_dates = {}
        filters = LicenseLedgerFilters()
    else:
        filters = LicenseLedgerFilters.from_query_params(params)
        dfia, incentive = _apply_database_filters(filters, authorization_company_id)
        dfia_ids, incentive_ids = list(dfia.values_list("id", flat=True)), list(incentive.values_list("id", flat=True))
        dfia_dates = first_purchase_date_by_license(dfia_ids)
        incentive_dates = incentive_first_purchase_date_by_license(incentive_ids)
        def in_range(value):
            if filters.purchase_date_from or filters.purchase_date_to:
                if value is None: return False
                if filters.purchase_date_from and value < filters.purchase_date_from: return False
                if filters.purchase_date_to and value > filters.purchase_date_to: return False
            return True
        dfia_ids = [value for value in dfia_ids if in_range(dfia_dates.get(value))]
        incentive_ids = [value for value in incentive_ids if in_range(incentive_dates.get(value))]
        incentive_types = dict(IncentiveLicense.objects.filter(id__in=incentive_ids).values_list("id", "license_type"))
        refs = [(value, "DFIA") for value in dfia_ids] + [(value, incentive_types[value]) for value in incentive_ids]
        first_dates = {**{("DFIA", key): value for key, value in dfia_dates.items()}, **{
            (incentive_types[key], key): value for key, value in incentive_dates.items() if key in incentive_types
        }}

    licenses = [CanonicalLedgerService.build_canonical_ledger_dataset(
        license_id, license_type, first_purchase_date=first_dates.get((license_type, license_id)),
    ) for license_id, license_type in refs]
    if filters.min_balance is not None:
        # The collection's eligibility filter is Financial Available Balance,
        # not the presentation ledger's running total.  The latter intentionally
        # represents only opening/purchase/sale activity and can therefore be
        # stale with respect to BOE and allotment consumption.  Resolve the
        # authoritative balance in one batched query path before filtering.
        dfia_ids = [license_id for license_id, license_type in refs if license_type == "DFIA"]
        live_dfia_balances = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(dfia_ids)
        licenses = [
            row for row in licenses
            if (
                live_dfia_balances.get(row["license_id"], Decimal("0"))
                if row["license_type"] == "DFIA"
                else row["summary"]["current_balance"]
            ) >= filters.min_balance
        ]
    balance_sort = filters.ordering.lstrip("-") == "balance_value"
    key = (lambda row: row["summary"]["current_balance"]) if balance_sort else (lambda row: (row.get("license_date") is not None, row.get("license_date")))
    licenses.sort(key=key, reverse=filters.ordering.startswith("-"))
    company_groups = CanonicalLedgerService.build_collection_company_groups(licenses)
    return {
        "licenses": licenses,
        "summary": CanonicalLedgerService.build_collection_summary(licenses),
        "company_groups": company_groups,
        "grand_total": CanonicalLedgerService.build_collection_grand_total(company_groups),
    }
