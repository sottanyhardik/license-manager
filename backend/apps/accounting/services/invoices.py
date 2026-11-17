"""Invoices: link trade invoices (never recreate), standalone bills (expense, commission, notes),
confirmation, posting, reversal, re-posting after a trade edit, TDS, bill-wise settlement.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounting.domain.money import ZERO, allocate_pro_rata, q2, to_money
from apps.accounting.domain.tax import TdsRule, compute_tds, split_gst, state_code_from_gstin
from apps.accounting.models import (
    NOTE_KINDS, PAYABLE_KINDS, RECEIVABLE_KINDS, Account, DocStatus, EntityBooks, Invoice, InvoiceKind, InvoiceLine,
    LowerDeductionCertificate, Settlement, TdsSection, Voucher, VoucherType,
)
from apps.accounting.selectors.trade_source import get_trade, view_of
from apps.core.models import CompanyModel

from . import AccountingError, audit
from .books import ensure_financial_year, fy_bounds, party_account
from .chart import system_account
from .posting import LineSpec, cr, dr, post_voucher, reverse_voucher

VOUCHER_TYPE_FOR = {
    InvoiceKind.PURCHASE: VoucherType.PURCHASE, InvoiceKind.SALES: VoucherType.SALES,
    InvoiceKind.EXPENSE: VoucherType.EXPENSE, InvoiceKind.COMMISSION_PAYABLE: VoucherType.COMMISSION,
    InvoiceKind.COMMISSION_RECEIVABLE: VoucherType.COMMISSION, InvoiceKind.DEBIT_NOTE: VoucherType.DEBIT_NOTE,
    InvoiceKind.CREDIT_NOTE: VoucherType.CREDIT_NOTE,
}
TRADE_LINE_ROLE = {
    "PURCHASE": "PURCHASES", "SALES": "SALES",
    "COMMISSION_PAYABLE": "COMMISSION_EXPENSE", "COMMISSION_RECEIVABLE": "COMMISSION_INCOME",
}
INTERCOMPANY_ROLE = {
    "PURCHASES": "INTERCOMPANY_PURCHASES", "SALES": "INTERCOMPANY_SALES",
    "COMMISSION_EXPENSE": "INTERCOMPANY_COMMISSION_EXPENSE", "COMMISSION_INCOME": "INTERCOMPANY_COMMISSION_INCOME",
}


# --- trade-linked invoices -----------------------------------------------------------------------

def entity_for_trade(trade) -> EntityBooks | None:
    view = view_of(trade)
    return EntityBooks.objects.filter(pk=view.entity_company_id, is_active=True).first() if view.entity_company_id else None


@transaction.atomic
def invoice_from_trade(trade_id: int, *, user=None, credit_days: int | None = None,
                       tds_section: TdsSection | None = None) -> Invoice:
    """Return the trade's accounting invoice, creating the link (as a draft) if missing."""
    existing = Invoice.objects.filter(trade_id=trade_id).first()
    if existing:
        return existing
    trade = get_trade(trade_id)
    view = view_of(trade)
    entity = entity_for_trade(trade)
    if entity is None:
        raise AccountingError("The trade's own company has no active books.", "no_books")
    if not view.party_company_id:
        raise AccountingError("The trade has no counterparty company.", "no_party")
    if not view.invoice_date:
        raise AccountingError("The trade has no invoice date.", "no_date")
    if view.total <= 0:
        raise AccountingError("The trade total is zero.", "zero_total")
    if view.lines_total != view.subtotal:
        raise AccountingError(
            f"Trade lines ({view.lines_total}) do not add up to the trade subtotal ({view.subtotal}).", "line_mismatch"
        )
    party = CompanyModel.objects.get(pk=view.party_company_id)
    days = entity.default_credit_days if credit_days is None else credit_days
    if Invoice.objects.filter(entity=entity, kind=view.kind, party=party, number=view.invoice_number).exists():
        raise AccountingError(f"Another bill {view.invoice_number} already exists for {party.name}; correct the trade's "
                              "invoice number first.", "duplicate_number")
    try:
        with transaction.atomic():
            invoice = Invoice.objects.create(
                entity=entity, kind=view.kind, party=party, number=view.invoice_number, date=view.invoice_date,
                credit_days=days, due_date=view.invoice_date + timedelta(days=days), trade_id=trade.pk,
                taxable_amount=view.subtotal, roundoff=view.roundoff, gross_amount=view.total, net_amount=view.total,
                source_version=view.version, narration=f"Trade #{trade.pk} {trade.direction} {view.invoice_number}",
                tds_section=tds_section,
            )
    except IntegrityError:  # concurrent double-click: the first link wins
        existing = Invoice.objects.filter(trade_id=trade_id).first()
        if existing:
            return existing
        raise AccountingError("Could not link the trade (duplicate bill number).", "duplicate_number")
    _write_trade_lines(invoice, view, trade.pk)
    if tds_section:
        apply_tds(invoice)
    audit.record("INVOICE_LINKED_FROM_TRADE", invoice, actor=user, trade=trade.pk, version=view.version)
    return invoice


def _line_account(invoice: Invoice, role: str) -> Account:
    party_acct = party_account(invoice.entity, invoice.party, payable=invoice.kind in PAYABLE_KINDS)
    if party_acct.intercompany_entity_id and role in INTERCOMPANY_ROLE:
        role = INTERCOMPANY_ROLE[role]
    return system_account(invoice.entity, role)


def _write_trade_lines(invoice: Invoice, view, trade_id: int) -> None:
    account = _line_account(invoice, TRADE_LINE_ROLE[view.kind])
    InvoiceLine.objects.bulk_create([
        InvoiceLine(invoice=invoice, line_no=i, account=account, description=ln.description, quantity=ln.quantity,
                    amount=ln.amount, trade_id=trade_id)
        for i, ln in enumerate(view.lines, start=1)
    ])


def trade_drift(invoice: Invoice) -> bool:
    """True when the trade changed after the invoice was synced/posted."""
    if not invoice.trade_id:
        return False
    return view_of(get_trade(invoice.trade_id)).version != invoice.source_version


@transaction.atomic
def resync_trade_invoice(invoice: Invoice, *, user=None, reason: str = "Trade edited after posting") -> Invoice:
    """Bring a trade invoice back in line with its trade. Posted: reverse + re-post (never rewrite)."""
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if not invoice.trade_id:
        raise AccountingError("Not a trade invoice.", "not_trade_invoice")
    view = view_of(get_trade(invoice.trade_id))
    if view.version == invoice.source_version:
        return invoice
    if invoice.status in (DocStatus.CANCELLED, DocStatus.REVERSED):
        raise AccountingError("This trade invoice is cancelled/reversed; it cannot be re-synced.", "not_active")
    was_posted = invoice.status == DocStatus.POSTED
    settled = settled_amount(invoice)
    identity_changed = (view.entity_company_id, view.party_company_id, view.kind) != (
        invoice.entity_id, invoice.party_id, invoice.kind)
    if identity_changed:
        # Counterparty, own entity or direction changed: the bill moves to another ledger/side.
        if settled > 0:
            raise AccountingError("The trade's party/entity/direction changed but the bill is already settled; "
                                  "reverse its settlements first.", "identity_changed_settled")
        new_entity = EntityBooks.objects.filter(pk=view.entity_company_id, is_active=True).first()
        if new_entity is None or not view.party_company_id:
            raise AccountingError("The trade's new own side has no active books or no counterparty.", "no_books")
    repost_date = None
    if was_posted:
        repost_date = _open_reversal_date(invoice.voucher)
        reverse_voucher(invoice.voucher, reversal_date=repost_date, reason=reason, user=user, _system=True)
    if identity_changed:
        invoice.entity = new_entity
        invoice.party = CompanyModel.objects.get(pk=view.party_company_id)
        invoice.kind = view.kind
    invoice.lines.all().delete()
    invoice.taxable_amount, invoice.roundoff = view.subtotal, view.roundoff
    invoice.gross_amount = view.total
    invoice.number, invoice.date = view.invoice_number, view.invoice_date
    invoice.due_date = view.invoice_date + timedelta(days=invoice.credit_days)
    invoice.source_version = view.version
    invoice.voucher = None
    invoice.status = DocStatus.CONFIRMED if was_posted else DocStatus.DRAFT
    invoice.save()
    _write_trade_lines(invoice, view, invoice.trade_id)
    apply_tds(invoice)
    if invoice.net_amount < settled:  # rolls back the reversal too (atomic)
        raise AccountingError(f"The new net amount {invoice.net_amount} is below the amount already settled {settled}.",
                              "below_settled")
    audit.record("INVOICE_RESYNCED", invoice, actor=user, version=view.version, reason=reason,
                 identity_changed=identity_changed)
    if was_posted:
        # Re-post on the original date when open, else on the same open date as the reversal.
        invoice = post_invoice(invoice, user=user, voucher_date=repost_date, _system=True)
    return invoice


def _open_reversal_date(voucher: Voucher) -> date:
    """Reverse on the original date when its period is open, otherwise today (locked periods stay untouched)."""
    from .books import open_period_for
    try:
        open_period_for(voucher.entity, voucher.date)
        return voucher.date
    except AccountingError:
        return max(timezone.localdate(), voucher.date)


# --- standalone invoices (expense, commission, notes, non-trade purchase/sales) ------------------

@dataclass
class LineInput:
    account: Account
    amount: Decimal
    description: str = ""
    gst_rate: Decimal = ZERO
    quantity: Decimal = ZERO
    trade_id: int | None = None
    cost_centre_id: int | None = None
    #: Optional allocation of this line across trades: {"method": "VALUE"|"QUANTITY", "trade_ids": [...]}
    allocation: dict | None = field(default=None)


@transaction.atomic
def create_invoice(*, entity: EntityBooks, kind: str, party: CompanyModel, number: str, invoice_date: date,
                   lines: list[LineInput], credit_days: int = 0, party_reference: str = "",
                   tds_section: TdsSection | None = None, against_invoice: Invoice | None = None,
                   narration: str = "", currency: str = "INR", fx_rate: Decimal = Decimal("1"),
                   user=None) -> Invoice:
    if kind not in InvoiceKind.values:
        raise AccountingError("Unknown invoice kind.", "bad_kind")
    if kind in NOTE_KINDS and against_invoice is None:
        raise AccountingError("A debit/credit note must reference the bill it adjusts.", "note_without_bill")
    if against_invoice is not None:
        _check_note_target(kind, against_invoice, entity, party)
    if not lines:
        raise AccountingError("At least one line is required.", "no_lines")
    ensure_financial_year(entity, invoice_date)
    invoice = Invoice.objects.create(
        entity=entity, kind=kind, party=party, number=number.strip(), party_reference=party_reference,
        date=invoice_date, credit_days=credit_days, due_date=invoice_date + timedelta(days=credit_days),
        tds_section=tds_section, against_invoice=against_invoice, narration=narration, currency=currency,
        fx_rate=fx_rate,
    )
    supplier_state, recipient_state = _gst_states(entity, party, kind)
    expanded = _expand_allocations(lines)
    rows = []
    for i, ln in enumerate(expanded, start=1):
        if ln.account.entity_id != entity.pk:
            raise AccountingError("Line account belongs to another entity.", "cross_entity_account")
        split = split_gst(to_money(ln.amount), Decimal(ln.gst_rate or 0), supplier_state, recipient_state)
        rows.append(InvoiceLine(
            invoice=invoice, line_no=i, account=ln.account, description=ln.description[:255],
            quantity=ln.quantity or ZERO, amount=to_money(ln.amount), gst_rate=ln.gst_rate or ZERO,
            cgst=split.cgst, sgst=split.sgst, igst=split.igst, trade_id=ln.trade_id, cost_centre_id=ln.cost_centre_id,
        ))
    InvoiceLine.objects.bulk_create(rows)
    _recompute_totals(invoice)
    apply_tds(invoice)
    if against_invoice is not None and invoice.net_amount > against_invoice.net_amount:
        raise AccountingError(f"The note ({invoice.net_amount}) exceeds the bill it adjusts "
                              f"({against_invoice.net_amount}).", "note_exceeds_bill")
    audit.record("INVOICE_CREATED", invoice, actor=user, kind=kind, number=invoice.number)
    return invoice


def _check_note_target(kind: str, target: Invoice, entity: EntityBooks, party: CompanyModel) -> None:
    if target.entity_id != entity.pk or target.party_id != party.pk:
        raise AccountingError("The adjusted bill belongs to another entity or party.", "note_mismatch")
    if kind == InvoiceKind.DEBIT_NOTE and target.kind not in PAYABLE_KINDS:
        raise AccountingError("A debit note adjusts a purchase/expense bill.", "note_mismatch")
    if kind == InvoiceKind.CREDIT_NOTE and target.kind not in RECEIVABLE_KINDS:
        raise AccountingError("A credit note adjusts a sales bill.", "note_mismatch")


def _gst_states(entity: EntityBooks, party: CompanyModel, kind: str) -> tuple[str, str]:
    ours = entity.state_code or state_code_from_gstin(entity.company.gst_number)
    theirs = state_code_from_gstin(party.gst_number)
    receives_supply = kind in PAYABLE_KINDS or kind == InvoiceKind.DEBIT_NOTE
    return (theirs, ours) if receives_supply else (ours, theirs)


def _expand_allocations(lines: list[LineInput]) -> list[LineInput]:
    """A line with an allocation becomes one line per trade, split by trade value or quantity."""
    from apps.accounting.selectors.trade_source import trade_queryset
    out: list[LineInput] = []
    for ln in lines:
        alloc = ln.allocation or {}
        trade_ids = alloc.get("trade_ids") or []
        if not trade_ids:
            out.append(ln)
            continue
        trades = {t.pk: t for t in trade_queryset().filter(pk__in=trade_ids)}
        if len(trades) != len(set(trade_ids)):
            raise AccountingError("An allocation references an unknown trade.", "bad_allocation")
        method = alloc.get("method", "VALUE")
        if method == "QUANTITY":
            weights = [sum((x.qty_kg or ZERO for x in trades[t].lines.all()), ZERO) for t in trade_ids]
        elif method == "VALUE":
            weights = [trades[t].total_amount for t in trade_ids]
        else:
            raise AccountingError("Allocation method must be VALUE or QUANTITY (weight in kg).", "bad_allocation")
        try:
            parts = allocate_pro_rata(to_money(ln.amount), [Decimal(w) for w in weights])
        except ValueError as exc:
            raise AccountingError(f"Cannot allocate by {method.lower()}: the trades have no {method.lower()}.",
                                  "bad_allocation") from exc
        for trade_id, part in zip(trade_ids, parts):
            if part:
                out.append(LineInput(ln.account, part, f"{ln.description} (alloc {method.lower()})".strip(),
                                     ln.gst_rate, ZERO, trade_id, ln.cost_centre_id))
    return out


def _recompute_totals(invoice: Invoice) -> None:
    agg = invoice.lines.aggregate(t=Sum("amount"), c=Sum("cgst"), s=Sum("sgst"), i=Sum("igst"))
    invoice.taxable_amount = q2(agg["t"] or ZERO)
    invoice.cgst, invoice.sgst, invoice.igst = q2(agg["c"] or ZERO), q2(agg["s"] or ZERO), q2(agg["i"] or ZERO)
    invoice.gross_amount = invoice.taxable_amount + invoice.cgst + invoice.sgst + invoice.igst + invoice.roundoff
    invoice.net_amount = invoice.gross_amount - invoice.tds_amount
    invoice.save(update_fields=["taxable_amount", "cgst", "sgst", "igst", "gross_amount", "net_amount", "modified_on"])


# --- TDS -----------------------------------------------------------------------------------------

def tds_rule_for(code: str, on: date) -> TdsSection | None:
    return (TdsSection.objects.filter(code=code, effective_from__lte=on)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on)).order_by("-effective_from").first())


def apply_tds(invoice: Invoice) -> Invoice:
    """(Re)compute TDS from the configured section effective on the invoice date. No section => no TDS."""
    tds = ZERO
    rate = ZERO
    if invoice.tds_section_id and invoice.kind not in NOTE_KINDS:
        section = tds_rule_for(invoice.tds_section.code, invoice.date)
        if section is None:
            raise AccountingError(f"No TDS rate for {invoice.tds_section.code} effective {invoice.date:%d-%m-%Y}.",
                                  "tds_rate_missing")
        rule = TdsRule(section.rate_individual, section.rate_other, section.rate_no_pan,
                       section.threshold_single, section.threshold_aggregate, section.threshold_mode)
        ldc = (LowerDeductionCertificate.objects
               .filter(party=invoice.party, section_code=section.code, valid_from__lte=invoice.date,
                       valid_to__gte=invoice.date).first())
        prior = _prior_tds_base(invoice, section.code)
        first_crossing = section.threshold_aggregate > 0 and prior <= section.threshold_aggregate
        prior_untaxed = _prior_tds_base(invoice, section.code, untaxed_only=True) if first_crossing else ZERO
        ldc_remaining = None
        if ldc and ldc.amount_limit is not None:
            used = (Invoice.objects.filter(entity=invoice.entity, party=invoice.party, tds_section__code=section.code,
                                           date__gte=ldc.valid_from, date__lte=ldc.valid_to, status=DocStatus.POSTED)
                    .exclude(pk=invoice.pk).aggregate(t=Sum("taxable_amount"))["t"] or ZERO)
            ldc_remaining = ldc.amount_limit - used
        tds = compute_tds(rule, invoice.taxable_amount, prior, invoice.party.pan, ldc.rate if ldc else None,
                          prior_untaxed=prior_untaxed, lower_rate_limit=ldc_remaining)
        rate = (Decimal(tds * 100 / invoice.taxable_amount).quantize(Decimal("0.001"))
                if invoice.taxable_amount and tds else ZERO)  # effective rate (may include FULL-mode catch-up)
    invoice.tds_amount, invoice.tds_rate = tds, rate
    invoice.net_amount = invoice.gross_amount - tds
    invoice.save(update_fields=["tds_amount", "tds_rate", "net_amount", "modified_on"])
    return invoice


def _prior_tds_base(invoice: Invoice, code: str, *, untaxed_only: bool = False) -> Decimal:
    _label, start, end = fy_bounds(invoice.date)
    qs = (Invoice.objects.filter(entity=invoice.entity, party=invoice.party, tds_section__code=code,
                                 date__gte=start, date__lte=end, status=DocStatus.POSTED)
          .exclude(pk=invoice.pk))
    if untaxed_only:
        qs = qs.filter(tds_amount=0)
    return qs.aggregate(t=Sum("taxable_amount"))["t"] or ZERO


# --- lifecycle -----------------------------------------------------------------------------------

@transaction.atomic
def confirm_invoice(invoice: Invoice, *, user=None) -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status != DocStatus.DRAFT:
        raise AccountingError(f"Only drafts can be confirmed (status {invoice.status}).", "not_draft")
    if invoice.trade_id and trade_drift(invoice):
        raise AccountingError("The trade changed since this invoice was linked; re-sync first.", "trade_drift")
    invoice.status = DocStatus.CONFIRMED
    invoice.confirmed_by = user if getattr(user, "is_authenticated", False) else None
    invoice.confirmed_at = timezone.now()
    invoice.save(update_fields=["status", "confirmed_by", "confirmed_at", "modified_on"])
    audit.record("INVOICE_CONFIRMED", invoice, actor=user)
    return invoice


def voucher_lines_for(invoice: Invoice) -> list[LineSpec]:
    e = invoice.entity
    payable = invoice.kind in PAYABLE_KINDS
    party = party_account(e, invoice.party, payable=payable or invoice.kind == InvoiceKind.DEBIT_NOTE)
    lines: list[LineSpec] = []
    # Purchase-side documents debit the cost lines; sale-side and debit notes credit them.
    debit_lines = payable or invoice.kind == InvoiceKind.CREDIT_NOTE
    tax_prefix = "INPUT" if payable or invoice.kind == InvoiceKind.DEBIT_NOTE else "OUTPUT"
    for ln in invoice.lines.select_related("account"):
        spec = dict(narration=ln.description, trade_id=ln.trade_id, cost_centre_id=ln.cost_centre_id)
        lines.append(dr(ln.account, ln.amount, **spec) if debit_lines else cr(ln.account, ln.amount, **spec))
        for tax, value in (("CGST", ln.cgst), ("SGST", ln.sgst), ("IGST", ln.igst)):
            if value:
                acct = system_account(e, f"{tax_prefix}_{tax}")
                lines.append(dr(acct, value, trade_id=ln.trade_id) if debit_lines else cr(acct, value, trade_id=ln.trade_id))
    if invoice.roundoff:
        acct = system_account(e, "ROUND_OFF")
        lines.append(LineSpec(acct, invoice.roundoff, ZERO) if debit_lines else LineSpec(acct, ZERO, invoice.roundoff))
        if invoice.trade_id:
            lines[-1] = LineSpec(lines[-1].account, lines[-1].debit, lines[-1].credit, "Round off", invoice.trade_id)
    gross = invoice.gross_amount
    party_narr = f"{invoice.kind} {invoice.number}"
    lines.append(cr(party, gross, party_narr, trade_id=invoice.trade_id) if debit_lines
                 else dr(party, gross, party_narr, trade_id=invoice.trade_id))
    if invoice.tds_amount:
        if payable:  # we deduct TDS from the supplier's dues
            lines += [dr(party, invoice.tds_amount, "TDS deducted"), cr(system_account(e, "TDS_PAYABLE"), invoice.tds_amount)]
        else:        # the customer deducts TDS from our dues
            lines += [dr(system_account(e, "TDS_RECEIVABLE"), invoice.tds_amount), cr(party, invoice.tds_amount, "TDS deducted")]
    return lines


@transaction.atomic
def post_invoice(invoice: Invoice, *, user=None, voucher_date: date | None = None,
                 _system: bool = False) -> Invoice:
    """Post a confirmed invoice once. ``voucher_date`` defaults to the invoice date (a re-post after a
    trade edit uses an open-period date when the invoice's own period is locked)."""
    invoice = Invoice.objects.select_for_update().select_related("entity", "party").get(pk=invoice.pk)
    if invoice.status == DocStatus.POSTED:
        return invoice  # exactly-once: repeated delivery is a no-op
    if invoice.status != DocStatus.CONFIRMED:
        raise AccountingError("Confirm the invoice before posting.", "not_confirmed")
    if (not _system and invoice.entity.require_maker_checker and invoice.created_by_id
            and getattr(user, "pk", None) == invoice.created_by_id):
        raise AccountingError("Maker-checker: the bill must be posted by a different user.", "maker_checker")
    if invoice.trade_id and trade_drift(invoice):
        raise AccountingError("The trade changed since this invoice was linked; re-sync first.", "trade_drift")
    if invoice.tds_section_id:  # thresholds depend on what is posted *now*, not when the draft was made
        apply_tds(invoice)
    if invoice.net_amount <= 0 and invoice.kind not in NOTE_KINDS:
        raise AccountingError("Nothing to post: the invoice amount is zero.", "zero_amount")
    # Each posting of the same invoice (first post, re-post after a trade edit) has its own sequence number.
    prior = Voucher.objects.filter(source_type="INVOICE", source_id=invoice.pk, reversal_of__isnull=True).count()
    voucher, _ = post_voucher(
        entity=invoice.entity, voucher_type=VOUCHER_TYPE_FOR[invoice.kind], voucher_date=voucher_date or invoice.date,
        lines=voucher_lines_for(invoice), narration=invoice.narration or f"{invoice.get_kind_display()} {invoice.number}",
        source_type="INVOICE", source_id=invoice.pk, source_event="POST" if prior == 0 else f"POST#{prior + 1}",
        source_version=invoice.source_version or "1", user=user,
    )
    invoice.voucher = voucher
    invoice.status = DocStatus.POSTED
    invoice.save(update_fields=["voucher", "status", "modified_on"])
    audit.record("INVOICE_POSTED", invoice, actor=user, voucher=voucher.number)
    if invoice.kind in NOTE_KINDS:
        _settle_note(invoice, user=user)
    return invoice


def _settle_note(note: Invoice, *, user=None) -> None:
    target = note.against_invoice
    amount = min(note.net_amount, outstanding(target))
    if amount > 0:
        allocate(target, note.voucher, amount, note=note, user=user)


@transaction.atomic
def cancel_invoice(invoice: Invoice, *, user=None, reason: str = "") -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status not in (DocStatus.DRAFT, DocStatus.CONFIRMED):
        raise AccountingError("Posted invoices are reversed, not cancelled.", "posted_immutable")
    invoice.status = DocStatus.CANCELLED
    invoice.save(update_fields=["status", "modified_on"])
    audit.record("INVOICE_CANCELLED", invoice, actor=user, reason=reason)
    return invoice


@transaction.atomic
def reverse_invoice(invoice: Invoice, *, reason: str, user=None, reversal_date: date | None = None) -> Invoice:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status != DocStatus.POSTED:
        raise AccountingError("Only posted invoices can be reversed.", "not_posted")
    if settled_amount(invoice) > 0:
        raise AccountingError("Reverse or re-allocate the settlements on this bill first.", "has_settlements")
    reverse_voucher(invoice.voucher, reversal_date=reversal_date, reason=reason, user=user)
    if invoice.kind in NOTE_KINDS:  # a reversed note no longer reduces the bill it adjusted
        Settlement.objects.filter(note=invoice, is_active=True).update(is_active=False)
    invoice.status = DocStatus.REVERSED
    invoice.save(update_fields=["status", "modified_on"])
    audit.record("INVOICE_REVERSED", invoice, actor=user, reason=reason)
    return invoice


# --- bill-wise settlement ------------------------------------------------------------------------

def settled_amount(invoice: Invoice, as_of: date | None = None) -> Decimal:
    qs = invoice.settlements.filter(is_active=True)
    if as_of is not None:
        qs = qs.filter(voucher__date__lte=as_of)
    return qs.aggregate(t=Sum("amount"))["t"] or ZERO


def applied_amount(note: Invoice, as_of: date | None = None) -> Decimal:
    qs = note.note_settlements.filter(is_active=True)
    if as_of is not None:
        qs = qs.filter(voucher__date__lte=as_of)
    return qs.aggregate(t=Sum("amount"))["t"] or ZERO


def outstanding(invoice: Invoice, as_of: date | None = None) -> Decimal:
    """Open amount of a posted bill (optionally as it stood on ``as_of``).

    For a debit/credit note this is its *unapplied credit* (normally 0 once applied to its bill);
    notes are never bills that fall due."""
    if invoice.status != DocStatus.POSTED:
        return ZERO
    if invoice.kind in NOTE_KINDS:
        return invoice.net_amount - applied_amount(invoice, as_of)
    return invoice.net_amount - settled_amount(invoice, as_of)


def allocate(invoice: Invoice, voucher: Voucher, amount: Decimal, *, payment=None, note: Invoice | None = None,
             user=None) -> Settlement:
    """Allocate part of a settling voucher to a bill. Caller holds the transaction."""
    amount = to_money(amount)
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if amount <= 0:
        raise AccountingError("Allocation must be positive.", "bad_amount")
    if invoice.status != DocStatus.POSTED:
        raise AccountingError(f"Bill {invoice.number} is not posted.", "bill_not_posted")
    if invoice.entity_id != voucher.entity_id:
        raise AccountingError("Bill and settlement belong to different entities.", "cross_entity")
    if amount > outstanding(invoice):
        raise AccountingError(f"Allocation {amount} exceeds the outstanding {outstanding(invoice)} on {invoice.number}.",
                              "over_allocation")
    settlement = Settlement.objects.create(entity=invoice.entity, invoice=invoice, voucher=voucher,
                                           payment=payment, note=note, amount=amount)
    audit.record("BILL_ALLOCATED", settlement, actor=user, entity=invoice.entity, invoice=invoice.number, amount=amount)
    return settlement


def payment_status(invoice: Invoice, today: date | None = None) -> str:
    """UNPAID / PARTIALLY_PAID / PAID / OVERDUE for posted bills; else the document status."""
    if invoice.status != DocStatus.POSTED:
        return invoice.status
    due = outstanding(invoice)
    if invoice.kind in NOTE_KINDS:
        return "APPLIED" if due <= 0 else "UNAPPLIED_CREDIT"
    if due <= 0:
        return "PAID"
    today = today or timezone.localdate()
    if invoice.due_date and invoice.due_date < today:
        return "OVERDUE"
    return "PARTIALLY_PAID" if due < invoice.net_amount else "UNPAID"


# --- batch helpers (avoid one query per bill in lists/reports) ---------------------------------

def outstanding_map(invoices, as_of: date | None = None) -> dict[int, Decimal]:
    """{invoice_id: outstanding} for many invoices in two grouped queries."""
    invoices = list(invoices)
    ids = [i.pk for i in invoices]
    bills = Settlement.objects.filter(invoice_id__in=ids, is_active=True)
    notes = Settlement.objects.filter(note_id__in=ids, is_active=True)
    if as_of is not None:
        bills, notes = bills.filter(voucher__date__lte=as_of), notes.filter(voucher__date__lte=as_of)
    settled = {r["invoice_id"]: r["t"] for r in bills.values("invoice_id").annotate(t=Sum("amount"))}
    applied = {r["note_id"]: r["t"] for r in notes.values("note_id").annotate(t=Sum("amount"))}
    out = {}
    for inv in invoices:
        if inv.status != DocStatus.POSTED:
            out[inv.pk] = ZERO
        elif inv.kind in NOTE_KINDS:
            out[inv.pk] = inv.net_amount - applied.get(inv.pk, ZERO)
        else:
            out[inv.pk] = inv.net_amount - settled.get(inv.pk, ZERO)
    return out


def status_for(invoice: Invoice, due: Decimal, today: date | None = None) -> str:
    """payment_status() given a precomputed outstanding amount."""
    if invoice.status != DocStatus.POSTED:
        return invoice.status
    if invoice.kind in NOTE_KINDS:
        return "APPLIED" if due <= 0 else "UNAPPLIED_CREDIT"
    if due <= 0:
        return "PAID"
    today = today or timezone.localdate()
    if invoice.due_date and invoice.due_date < today:
        return "OVERDUE"
    return "PARTIALLY_PAID" if due < invoice.net_amount else "UNPAID"
