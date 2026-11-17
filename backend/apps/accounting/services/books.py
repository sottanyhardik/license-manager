"""Books lifecycle: activation of an existing Trade entity, financial years, period locks, party ledgers."""
from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.accounting.domain.interest import month_end
from apps.accounting.domain.tax import state_code_from_gstin
from apps.accounting.models import Account, AccountingPeriod, AccountKind, EntityBooks, FinancialYear
from apps.core.models import CompanyModel

from . import AccountingError, audit
from .chart import ensure_default_chart, group, next_code


def fy_bounds(d: date) -> tuple[str, date, date]:
    start_year = d.year if d.month >= 4 else d.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}", date(start_year, 4, 1), date(start_year + 1, 3, 31)


@transaction.atomic
def activate_books(company: CompanyModel, books_start_date: date, *, user=None, state_code: str = "",
                   default_credit_days: int = 0) -> EntityBooks:
    """Start (or return) the books of an existing company. Never creates a company."""
    books, created = EntityBooks.objects.get_or_create(
        company=company,
        defaults={
            "books_start_date": books_start_date,
            "state_code": state_code or state_code_from_gstin(company.gst_number),
            "default_credit_days": default_credit_days,
        },
    )
    if created:
        ensure_default_chart(books)
        ensure_financial_year(books, books_start_date)
        _flag_intercompany(books)
        audit.record("BOOKS_ACTIVATED", books, actor=user, entity=books, books_start_date=books_start_date)
    return books


def _flag_intercompany(books: EntityBooks) -> None:
    """Party ledgers that point at another books-owning entity are intercompany (both directions)."""
    Account.objects.filter(kind=AccountKind.PARTY, party=books.company).exclude(entity=books).update(
        intercompany_entity=books
    )
    for account in Account.objects.filter(entity=books, kind=AccountKind.PARTY, intercompany_entity__isnull=True):
        other = EntityBooks.objects.filter(company_id=account.party_id).first()
        if other:
            Account.objects.filter(pk=account.pk).update(intercompany_entity=other)


def ensure_financial_year(entity: EntityBooks, d: date) -> FinancialYear:
    if d < entity.books_start_date:
        raise AccountingError(
            f"{d:%d-%m-%Y} is before the books start date {entity.books_start_date:%d-%m-%Y}.", "before_books_start"
        )
    label, start, end = fy_bounds(d)
    fy = FinancialYear.objects.filter(entity=entity, label=label).first()
    if fy:
        return fy
    with transaction.atomic():
        fy, created = FinancialYear.objects.get_or_create(
            entity=entity, label=label, defaults={"start_date": start, "end_date": end}
        )
        if created:
            audit.record("FINANCIAL_YEAR_OPENED", fy, entity=entity, label=label)
            month_start = start
            for n in range(1, 13):
                AccountingPeriod.objects.create(
                    financial_year=fy, period_no=n, start_date=month_start, end_date=month_end(month_start)
                )
                month_start = _next_month(month_start)
    return fy


def _next_month(d: date) -> date:
    return date(d.year + (d.month // 12), d.month % 12 + 1, 1)


def open_period_for(entity: EntityBooks, d: date) -> tuple[FinancialYear, AccountingPeriod]:
    fy = ensure_financial_year(entity, d)
    if fy.status == FinancialYear.CLOSED:
        raise AccountingError(f"Financial year {fy.label} is closed.", "fy_closed")
    # Row lock (inside the caller's transaction) so a concurrent period lock cannot race a posting.
    period = fy.periods.select_for_update().get(start_date__lte=d, end_date__gte=d)
    if period.status == AccountingPeriod.LOCKED:
        raise AccountingError(f"The accounting period {period.start_date:%b %Y} is locked.", "period_locked")
    return fy, period


@transaction.atomic
def set_period_lock(period: AccountingPeriod, locked: bool, *, user=None) -> AccountingPeriod:
    period = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    period.status = AccountingPeriod.LOCKED if locked else AccountingPeriod.OPEN
    period.locked_by = user if locked and getattr(user, "is_authenticated", False) else None
    period.locked_at = timezone.now() if locked else None
    period.save(update_fields=["status", "locked_by", "locked_at", "modified_on"])
    audit.record("PERIOD_LOCKED" if locked else "PERIOD_UNLOCKED", period, actor=user,
                 entity=period.financial_year.entity, period=str(period.start_date))
    return period


def party_account(entity: EntityBooks, party: CompanyModel, *, payable: bool) -> Account:
    """The single ledger for ``party`` in ``entity``'s books (Sundry Creditors/Debtors by first use)."""
    existing = Account.objects.filter(entity=entity, kind=AccountKind.PARTY, party=party).first()
    if existing:
        return existing
    if party.pk == entity.pk:
        raise AccountingError("An entity cannot be its own party.", "self_party")
    with transaction.atomic():
        other = EntityBooks.objects.filter(pk=party.pk).first()
        account, _ = Account.objects.get_or_create(
            entity=entity, kind=AccountKind.PARTY, party=party,
            defaults={
                "code": next_code(entity, "P"), "name": party.name,
                "group": group(entity, "CRD" if payable else "DBT"), "intercompany_entity": other,
            },
        )
    return account
