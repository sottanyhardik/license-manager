"""Historical data migration center: inventory -> dry run -> execute (authorised) -> reconcile.

Uses the same posting engine as live transactions. Never invents values, never skips silently
(every record gets a classification with reasons), never posts an already-accounted record.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from apps.accounting.domain.money import ZERO
from apps.accounting.models import (
    BankAccount, DocStatus, EntityBooks, Invoice, MigrationItem, MigrationRun, Payment,
)
from apps.accounting.selectors.trade_source import trades_for_company, view_of

from . import AccountingError, audit
from .books import fy_bounds
from .invoices import confirm_invoice, invoice_from_trade, post_invoice
from .payments import account_trade_payment

ALREADY, READY, REVIEW, EXCEPTION = "ALREADY_ACCOUNTED", "READY", "NEEDS_REVIEW", "EXCEPTION"
MIGRATED, FAILED, SKIPPED = "MIGRATED", "FAILED", "SKIPPED"


@dataclass
class Classified:
    source_type: str
    source_id: int
    classification: str
    amount: Decimal
    financial_year: str
    reasons: list[str] = field(default_factory=list)
    label: str = ""


def classify_trades(entity: EntityBooks) -> list[Classified]:
    out: list[Classified] = []
    invoices = {i.trade_id: i for i in Invoice.objects.filter(entity=entity, trade__isnull=False)}
    accounted_payments = set(Payment.objects.filter(entity=entity, trade_payment__isnull=False)
                             .values_list("trade_payment_id", flat=True))
    for trade in trades_for_company(entity.pk).order_by("invoice_date", "id"):
        view = view_of(trade)
        fy = fy_bounds(view.invoice_date)[0] if view.invoice_date else ""
        reasons = []
        inv = invoices.get(trade.pk)
        if inv and inv.status in (DocStatus.POSTED, DocStatus.REVERSED):
            cls = ALREADY if inv.source_version == view.version else EXCEPTION
            if cls == EXCEPTION:
                reasons.append("Trade edited after posting: re-sync required")
        else:
            if not view.invoice_date:
                reasons.append("No invoice date")
            elif view.invoice_date < entity.books_start_date:
                reasons.append(f"Dated before books start {entity.books_start_date:%d-%m-%Y} (covered by opening balances)")
            if not view.party_company_id:
                reasons.append("No counterparty company")
            if view.total <= 0:
                reasons.append("Zero total")
            if view.lines_total != view.subtotal:
                reasons.append(f"Lines {view.lines_total} ≠ subtotal {view.subtotal}")
            cls = REVIEW if reasons else READY
        out.append(Classified("TRADE", trade.pk, cls, view.total, fy, reasons,
                              f"{trade.direction} {view.invoice_number}"))
        for tp in trade.payments.all():
            if tp.pk in accounted_payments:
                pcls, preasons = ALREADY, []
            elif cls in (READY, ALREADY):
                pcls, preasons = READY, []
            else:
                pcls, preasons = REVIEW, ["Trade invoice not postable yet"]
            out.append(Classified("TRADE_PAYMENT", tp.pk, pcls, tp.amount, fy_bounds(tp.date)[0], preasons,
                                  f"Payment on {view.invoice_number}"))
    return out


def summarise(items: list[Classified]) -> dict:
    by_class = defaultdict(lambda: {"count": 0, "amount": ZERO})
    by_fy = defaultdict(lambda: defaultdict(lambda: {"count": 0, "amount": ZERO}))
    for it in items:
        key = f"{it.source_type}:{it.classification}"
        by_class[key]["count"] += 1
        by_class[key]["amount"] += it.amount
        by_fy[it.financial_year][key]["count"] += 1
        by_fy[it.financial_year][key]["amount"] += it.amount
    return {"by_classification": {k: dict(v) for k, v in by_class.items()},
            "by_financial_year": {fy: {k: dict(v) for k, v in d.items()} for fy, d in by_fy.items()}}


@transaction.atomic
def dry_run(entity: EntityBooks, *, user=None) -> MigrationRun:
    items = classify_trades(entity)
    run = MigrationRun.objects.create(entity=entity, mode=MigrationRun.DRY_RUN, summary=_json(summarise(items)))
    MigrationItem.objects.bulk_create([
        MigrationItem(run=run, source_type=i.source_type, source_id=i.source_id, classification=i.classification,
                      reasons=i.reasons, amount=i.amount, financial_year=i.financial_year)
        for i in items
    ])
    audit.record("MIGRATION_DRY_RUN", run, actor=user, entity=entity, items=len(items))
    return run


def execute(entity: EntityBooks, *, bank_account: BankAccount | None, confirm: bool, user=None,
            trade_ids: list[int] | None = None) -> MigrationRun:
    """Post READY trades (and their payments, if a bank account is mapped). Each record in its own
    transaction so one failure is recorded and does not roll back the others."""
    if not confirm:
        raise AccountingError("Execution requires explicit confirmation (confirm=true).", "confirm_required")
    if bank_account is not None and bank_account.entity_id != entity.pk:
        raise AccountingError("The bank account belongs to another entity.", "cross_entity")
    items = [i for i in classify_trades(entity) if trade_ids is None or i.source_type != "TRADE" or i.source_id in trade_ids]
    run = MigrationRun.objects.create(entity=entity, mode=MigrationRun.EXECUTE, parameters={
        "bank_account_id": bank_account.pk if bank_account else None, "trade_ids": trade_ids})
    records = []
    for it in items:
        outcome, reasons = SKIPPED, list(it.reasons)
        if it.classification == READY and it.source_type == "TRADE":
            outcome, reasons = _try(lambda: _post_trade(it.source_id, user), reasons)
        elif it.classification == READY and it.source_type == "TRADE_PAYMENT":
            if bank_account is None:
                reasons.append("No bank account mapped for historical payments")
            else:
                outcome, reasons = _try(lambda: account_trade_payment(it.source_id, bank_account=bank_account,
                                                                      user=user), reasons)
        records.append(MigrationItem(run=run, source_type=it.source_type, source_id=it.source_id,
                                     classification=it.classification, outcome=outcome, reasons=reasons,
                                     amount=it.amount, financial_year=it.financial_year))
    MigrationItem.objects.bulk_create(records)
    counts = defaultdict(int)
    for r in records:
        counts[f"{r.source_type}:{r.outcome}"] += 1
    run.summary = {"outcomes": dict(counts), "reconciliation": _json(reconcile(entity))}
    run.save(update_fields=["summary", "modified_on"])
    audit.record("MIGRATION_EXECUTED", run, actor=user, entity=entity, outcomes=dict(counts))
    return run


def _post_trade(trade_id: int, user):
    with transaction.atomic():
        inv = invoice_from_trade(trade_id, user=user)
        if inv.status == DocStatus.DRAFT:
            confirm_invoice(inv, user=user)
        return post_invoice(inv, user=user)


def _try(fn, reasons):
    try:
        with transaction.atomic():
            fn()
        return MIGRATED, reasons
    except AccountingError as exc:
        return FAILED, reasons + [str(exc)]


def reconcile(entity: EntityBooks) -> dict:
    """Entity x FY: source trade totals vs accounted (posted invoice) totals. Differences stay visible."""
    source = defaultdict(lambda: ZERO)
    accounted = defaultdict(lambda: ZERO)
    posted = {i.trade_id: i for i in Invoice.objects.filter(entity=entity, trade__isnull=False, status=DocStatus.POSTED)}
    for trade in trades_for_company(entity.pk):
        view = view_of(trade)
        if not view.invoice_date:
            continue
        fy = fy_bounds(view.invoice_date)[0]
        source[fy] += view.total
        if trade.pk in posted:
            accounted[fy] += posted[trade.pk].gross_amount
    return {fy: {"source_total": source[fy], "accounted_total": accounted[fy], "difference": source[fy] - accounted[fy]}
            for fy in sorted(source)}


def _json(data):
    if isinstance(data, dict):
        return {str(k): _json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_json(v) for v in data]
    if isinstance(data, Decimal):
        return str(data)
    return data
