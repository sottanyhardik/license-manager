"""Accounting masters maintained by the accountant: ledgers, cost centres, TDS sections, LDCs, book settings."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.accounting.models import (
    Account, AccountGroup, AccountKind, CostCentre, EntityBooks, LowerDeductionCertificate, TdsSection,
)
from apps.core.models import CompanyModel

from . import AccountingError, audit

USER_KINDS = (AccountKind.GENERAL, AccountKind.TAX)


@transaction.atomic
def add_account(entity: EntityBooks, *, group: AccountGroup, code: str, name: str, kind: str = AccountKind.GENERAL,
                user=None) -> Account:
    if group.entity_id != entity.pk:
        raise AccountingError("The group belongs to another entity.", "cross_entity")
    if kind not in USER_KINDS:
        raise AccountingError("Party, bank, loan and suspense ledgers are created by their own workflows.",
                              "bad_kind")
    if Account.objects.filter(entity=entity, code=code.strip()).exists():
        raise AccountingError(f"Account code {code} already exists.", "duplicate_code")
    account = Account.objects.create(entity=entity, group=group, code=code.strip(), name=name.strip(), kind=kind)
    audit.record("ACCOUNT_CREATED", account, actor=user, code=account.code)
    return account


@transaction.atomic
def rename_account(account: Account, *, name: str, is_active: bool | None = None, user=None) -> Account:
    account.name = name.strip() or account.name
    if is_active is not None:
        if account.system_role and not is_active:
            raise AccountingError("System ledgers used by posting rules cannot be deactivated.", "system_account")
        account.is_active = is_active
    account.save(update_fields=["name", "is_active", "modified_on"])
    audit.record("ACCOUNT_CHANGED", account, actor=user, name=account.name, is_active=account.is_active)
    return account


@transaction.atomic
def add_cost_centre(entity: EntityBooks, *, code: str, name: str, user=None) -> CostCentre:
    cc, created = CostCentre.objects.get_or_create(entity=entity, code=code.strip(), defaults={"name": name.strip()})
    if not created:
        raise AccountingError("Cost centre code already exists.", "duplicate_code")
    audit.record("COST_CENTRE_CREATED", cc, actor=user, entity=entity, code=cc.code)
    return cc


@transaction.atomic
def configure_books(entity: EntityBooks, *, default_credit_days: int | None = None,
                    require_maker_checker: bool | None = None, state_code: str | None = None,
                    tan: str | None = None, user=None) -> EntityBooks:
    if default_credit_days is not None:
        entity.default_credit_days = default_credit_days
    if require_maker_checker is not None:
        entity.require_maker_checker = require_maker_checker
    if state_code is not None:
        entity.state_code = state_code[:2]
    if tan is not None:
        entity.tan = tan[:10]
    entity.save()
    audit.record("BOOKS_CONFIGURED", entity, actor=user, entity=entity)
    return entity


@transaction.atomic
def add_tds_section(*, code: str, description: str, rate_individual: Decimal, rate_other: Decimal,
                    rate_no_pan: Decimal, threshold_single: Decimal, threshold_aggregate: Decimal,
                    threshold_mode: str, effective_from: date, effective_to: date | None = None,
                    user=None) -> TdsSection:
    if threshold_mode not in (TdsSection.FULL, TdsSection.EXCESS):
        raise AccountingError("threshold_mode must be FULL or EXCESS.", "bad_mode")
    if TdsSection.objects.filter(code=code, effective_from=effective_from).exists():
        raise AccountingError("A version of this section with the same effective date exists.", "duplicate")
    section = TdsSection.objects.create(
        code=code.strip().upper(), description=description, rate_individual=rate_individual, rate_other=rate_other,
        rate_no_pan=rate_no_pan, threshold_single=threshold_single, threshold_aggregate=threshold_aggregate,
        threshold_mode=threshold_mode, effective_from=effective_from, effective_to=effective_to,
    )
    audit.record("TDS_SECTION_CREATED", section, actor=user, entity=None, code=section.code)
    return section


@transaction.atomic
def add_lower_deduction_certificate(*, party: CompanyModel, section_code: str, certificate_no: str, rate: Decimal,
                                    valid_from: date, valid_to: date, amount_limit: Decimal | None = None,
                                    user=None) -> LowerDeductionCertificate:
    if valid_to < valid_from:
        raise AccountingError("valid_to is before valid_from.", "bad_dates")
    ldc = LowerDeductionCertificate.objects.create(
        party=party, section_code=section_code.strip().upper(), certificate_no=certificate_no, rate=rate,
        valid_from=valid_from, valid_to=valid_to, amount_limit=amount_limit,
    )
    audit.record("LDC_CREATED", ldc, actor=user, entity=None, party=party.pk)
    return ldc
