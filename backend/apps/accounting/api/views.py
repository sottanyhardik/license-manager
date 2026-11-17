"""Accounting API: entities/books, chart, vouchers, invoices, payments, trade tracking, masters, audit.

HTTP only: every write is a call into apps.accounting.services (ARCHITECTURE_RULES 1/3).
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import ValidationError

from apps.accounting.models import (
    Account, AccountGroup, AccountingAuditEvent, AccountingPeriod, BankAccount, CostCentre, EntityBooks, Invoice,
    LowerDeductionCertificate, Payment, TdsSection, Voucher,
)
from apps.accounting.selectors.entities import discover_entities
from apps.accounting.selectors.trade_status import trade_accounting_rows
from apps.accounting.services import books as books_svc
from apps.accounting.services import invoices as inv_svc
from apps.accounting.services import masters as masters_svc
from apps.accounting.services import payments as pay_svc
from apps.accounting.services import posting
from apps.core.models import CompanyModel

from .common import (
    AccountingView, ApproverView, as_date, as_int, as_money, entity_from, ok, page, param, period_from,
)
from .present import account_dict, entity_dict, invoice_dict, payment_dict, voucher_dict


# --- entities & books ------------------------------------------------------------------------------

class EntityListView(ApproverView):
    """GET: entities discovered from Trade (+ books status). POST: activate books for an existing company."""

    def get(self, request):
        return ok({"discovered": discover_entities(),
                   "books": [entity_dict(e) for e in EntityBooks.objects.select_related("company")]})

    def post(self, request):
        company = CompanyModel.objects.get(pk=as_int(param(request, "company_id", required=True), "company_id"))
        books = books_svc.activate_books(
            company, as_date(param(request, "books_start_date"), "books_start_date"), user=request.user,
            state_code=param(request, "state_code", "") or "",
            default_credit_days=as_int(param(request, "default_credit_days", 0), "default_credit_days"),
        )
        return ok(entity_dict(books), status.HTTP_201_CREATED)


class EntityDetailView(ApproverView):
    def get(self, request, entity_id: int):
        e = EntityBooks.objects.select_related("company").get(pk=entity_id)
        data = entity_dict(e)
        data["financial_years"] = [
            {"id": fy.pk, "label": fy.label, "start_date": fy.start_date, "end_date": fy.end_date, "status": fy.status,
             "periods": [{"id": p.pk, "period_no": p.period_no, "start_date": p.start_date, "end_date": p.end_date,
                          "status": p.status} for p in fy.periods.all()]}
            for fy in e.financial_years.prefetch_related("periods")
        ]
        return ok(data)

    def patch(self, request, entity_id: int):
        e = EntityBooks.objects.get(pk=entity_id)
        days = param(request, "default_credit_days")
        mc = param(request, "require_maker_checker")
        e = masters_svc.configure_books(
            e, default_credit_days=as_int(days, "default_credit_days") if days not in (None, "") else None,
            require_maker_checker=(str(mc).lower() in ("1", "true", "yes")) if mc not in (None, "") else None,
            state_code=param(request, "state_code"), tan=param(request, "tan"), user=request.user,
        )
        return ok(entity_dict(e))


class FinancialYearOpenView(ApproverView):
    def post(self, request, entity_id: int):
        e = EntityBooks.objects.get(pk=entity_id)
        fy = books_svc.ensure_financial_year(e, as_date(param(request, "date"), "date"))
        return ok({"id": fy.pk, "label": fy.label}, status.HTTP_201_CREATED)


class PeriodLockView(ApproverView):
    def post(self, request, period_id: int):
        period = AccountingPeriod.objects.select_related("financial_year__entity").get(pk=period_id)
        locked = str(param(request, "locked", "true")).lower() in ("1", "true", "yes")
        period = books_svc.set_period_lock(period, locked, user=request.user)
        return ok({"id": period.pk, "status": period.status})


# --- chart of accounts ----------------------------------------------------------------------------

class AccountListView(ApproverView):
    def get(self, request):
        e = entity_from(request)
        qs = Account.objects.filter(entity=e).select_related("group").order_by("code")
        if param(request, "kind"):
            qs = qs.filter(kind=param(request, "kind"))
        if param(request, "search"):
            qs = qs.filter(name__icontains=param(request, "search"))
        groups = AccountGroup.objects.filter(entity=e).order_by("code")
        return ok({"accounts": [account_dict(a) for a in qs],
                   "groups": [{"id": g.pk, "code": g.code, "name": g.name, "nature": g.nature,
                               "report_head": g.report_head} for g in groups],
                   "cost_centres": [{"id": c.pk, "code": c.code, "name": c.name}
                                    for c in CostCentre.objects.filter(entity=e)]})

    def post(self, request):
        e = entity_from(request)
        group = AccountGroup.objects.get(pk=as_int(param(request, "group_id", required=True), "group_id"), entity=e)
        acct = masters_svc.add_account(e, group=group, code=param(request, "code", required=True),
                                       name=param(request, "name", required=True),
                                       kind=param(request, "kind", "GENERAL"), user=request.user)
        return ok(account_dict(acct), status.HTTP_201_CREATED)


class AccountDetailView(ApproverView):
    def patch(self, request, account_id: int):
        acct = Account.objects.select_related("group").get(pk=account_id)
        active = param(request, "is_active")
        acct = masters_svc.rename_account(
            acct, name=param(request, "name", acct.name),
            is_active=(str(active).lower() in ("1", "true", "yes")) if active not in (None, "") else None,
            user=request.user)
        return ok(account_dict(acct))


class CostCentreView(ApproverView):
    def post(self, request):
        e = entity_from(request)
        cc = masters_svc.add_cost_centre(e, code=param(request, "code", required=True),
                                         name=param(request, "name", required=True), user=request.user)
        return ok({"id": cc.pk, "code": cc.code, "name": cc.name}, status.HTTP_201_CREATED)


# --- vouchers -------------------------------------------------------------------------------------

def _line_specs(entity, raw_lines) -> list:
    if not isinstance(raw_lines, list) or not raw_lines:
        raise ValidationError({"lines": "A list of {account_id, debit, credit} is required."})
    accounts = {a.pk: a for a in Account.objects.filter(entity=entity,
                                                        pk__in=[as_int(r.get("account_id"), "account_id")
                                                                for r in raw_lines])}
    specs = []
    for r in raw_lines:
        acct = accounts.get(int(r["account_id"]))
        if acct is None:
            raise ValidationError({"lines": f"Account {r['account_id']} is not in this entity."})
        specs.append(posting.LineSpec(acct, as_money(r.get("debit"), "debit", "0"), as_money(r.get("credit"), "credit", "0"),
                                      str(r.get("narration", ""))[:255],
                                      as_int(r["trade_id"], "trade_id") if r.get("trade_id") else None,
                                      as_int(r["cost_centre_id"], "cost_centre_id") if r.get("cost_centre_id") else None))
    return specs


class VoucherListView(AccountingView):
    """GET vouchers (filters: entity, type, status, start, end, source_type, account). POST: manual draft."""

    def get(self, request):
        e = entity_from(request)
        qs = Voucher.objects.filter(entity=e).select_related("posted_by", "created_by").order_by("-date", "-id")
        for f, field in (("type", "voucher_type"), ("status", "status"), ("source_type", "source_type")):
            if param(request, f):
                qs = qs.filter(**{field: param(request, f)})
        if param(request, "start"):
            qs = qs.filter(date__gte=as_date(param(request, "start"), "start"))
        if param(request, "end"):
            qs = qs.filter(date__lte=as_date(param(request, "end"), "end"))
        if param(request, "account"):
            qs = qs.filter(lines__account_id=as_int(param(request, "account"), "account")).distinct()
        if param(request, "search"):
            qs = qs.filter(number__icontains=param(request, "search")) | qs.filter(narration__icontains=param(request, "search"))
        return ok(page(request, qs, voucher_dict))

    def post(self, request):
        e = entity_from(request)
        v = posting.create_draft(entity=e, voucher_type=param(request, "voucher_type", "JOURNAL"),
                                 voucher_date=as_date(param(request, "date"), "date"),
                                 lines=_line_specs(e, request.data.get("lines")),
                                 narration=param(request, "narration", "") or "", user=request.user)
        return ok(voucher_dict(v, lines=True), status.HTTP_201_CREATED)


class VoucherDetailView(AccountingView):
    def get(self, request, voucher_id: int):
        v = Voucher.objects.select_related("posted_by", "created_by").get(pk=voucher_id)
        data = voucher_dict(v, lines=True)
        data["audit"] = [{"action": a.action, "actor": a.actor.username if a.actor else None, "at": a.occurred_at,
                          "detail": a.detail}
                         for a in AccountingAuditEvent.objects.filter(object_type="Voucher", object_id=v.pk)
                         .select_related("actor")]
        return ok(data)

    def patch(self, request, voucher_id: int):
        """Edit a manual DRAFT (header + full line set). Posted vouchers are refused (reverse instead)."""
        v = Voucher.objects.select_related("entity").get(pk=voucher_id)
        v = posting.update_draft(v, voucher_type=param(request, "voucher_type", v.voucher_type),
                                 voucher_date=as_date(param(request, "date"), "date", v.date),
                                 lines=_line_specs(v.entity, request.data.get("lines")),
                                 narration=param(request, "narration", v.narration) or "", user=request.user)
        return ok(voucher_dict(v, lines=True))

    def delete(self, request, voucher_id: int):
        posting.delete_draft(Voucher.objects.get(pk=voucher_id), user=request.user)
        return ok({"deleted": True}, status.HTTP_200_OK)


class VoucherPostView(ApproverView):
    def post(self, request, voucher_id: int):
        return ok(voucher_dict(posting.post_draft(Voucher.objects.get(pk=voucher_id), user=request.user), lines=True))


class VoucherReverseView(ApproverView):
    def post(self, request, voucher_id: int):
        v = Voucher.objects.get(pk=voucher_id)
        when = param(request, "date")
        rev = posting.reverse_manual_voucher(v, reason=param(request, "reason", required=True),
                                      reversal_date=as_date(when, "date") if when else None, user=request.user)
        return ok(voucher_dict(rev, lines=True), status.HTTP_201_CREATED)


# --- invoices -------------------------------------------------------------------------------------

def _invoice_lines(entity, raw) -> list[inv_svc.LineInput]:
    if not isinstance(raw, list) or not raw:
        raise ValidationError({"lines": "At least one line is required."})
    out = []
    for r in raw:
        acct = Account.objects.get(pk=as_int(r.get("account_id"), "account_id"), entity=entity)
        out.append(inv_svc.LineInput(
            account=acct, amount=as_money(r.get("amount")), description=str(r.get("description", "")),
            gst_rate=as_money(r.get("gst_rate"), "gst_rate", "0"), quantity=as_money(r.get("quantity"), "quantity", "0"),
            trade_id=as_int(r["trade_id"], "trade_id") if r.get("trade_id") else None,
            cost_centre_id=as_int(r["cost_centre_id"], "cost_centre_id") if r.get("cost_centre_id") else None,
            allocation=r.get("allocation") or None,
        ))
    return out


class InvoiceListView(AccountingView):
    def get(self, request):
        e = entity_from(request)
        qs = Invoice.objects.filter(entity=e).select_related("party", "voucher", "tds_section").order_by("-date", "-id")
        kinds = param(request, "kind")
        if kinds:
            qs = qs.filter(kind__in=str(kinds).split(","))
        if param(request, "status"):
            qs = qs.filter(status=param(request, "status"))
        for f in ("party_id", "trade_id"):
            if param(request, f):
                qs = qs.filter(**{f: as_int(param(request, f), f)})
        if param(request, "start"):
            qs = qs.filter(date__gte=as_date(param(request, "start"), "start"))
        if param(request, "end"):
            qs = qs.filter(date__lte=as_date(param(request, "end"), "end"))
        if param(request, "search"):
            qs = qs.filter(number__icontains=param(request, "search"))
        return ok(page(request, qs, invoice_dict))

    def post(self, request):
        e = entity_from(request)
        tds = param(request, "tds_section_id")
        against = param(request, "against_invoice_id")
        inv = inv_svc.create_invoice(
            entity=e, kind=param(request, "kind", required=True),
            party=CompanyModel.objects.get(pk=as_int(param(request, "party_id", required=True), "party_id")),
            number=param(request, "number", required=True), invoice_date=as_date(param(request, "date"), "date"),
            lines=_invoice_lines(e, request.data.get("lines")),
            credit_days=as_int(param(request, "credit_days", 0), "credit_days"),
            party_reference=param(request, "party_reference", "") or "",
            tds_section=TdsSection.objects.get(pk=as_int(tds, "tds_section_id")) if tds else None,
            against_invoice=Invoice.objects.get(pk=as_int(against, "against_invoice_id"), entity=e) if against else None,
            narration=param(request, "narration", "") or "", user=request.user,
        )
        return ok(invoice_dict(inv, lines=True), status.HTTP_201_CREATED)


class InvoiceDetailView(AccountingView):
    def get(self, request, invoice_id: int):
        return ok(invoice_dict(Invoice.objects.select_related("party", "voucher").get(pk=invoice_id), lines=True))


class InvoiceFromTradeView(AccountingView):
    def post(self, request):
        tds = param(request, "tds_section_id")
        days = param(request, "credit_days")
        inv = inv_svc.invoice_from_trade(
            as_int(param(request, "trade_id", required=True), "trade_id"), user=request.user,
            credit_days=as_int(days, "credit_days") if days not in (None, "") else None,
            tds_section=TdsSection.objects.get(pk=as_int(tds, "tds_section_id")) if tds else None)
        return ok(invoice_dict(inv, lines=True), status.HTTP_201_CREATED)


class InvoiceActionView(AccountingView):
    """POST /invoices/<id>/<action>/: confirm | cancel (manager); post | reverse | resync (approver)."""
    APPROVER_ACTIONS = ("post", "reverse", "resync")

    def initial(self, request, *args, **kwargs):
        self.write_level = "approve" if kwargs.get("action") in self.APPROVER_ACTIONS else "write"
        super().initial(request, *args, **kwargs)

    def post(self, request, invoice_id: int, action: str):
        inv = Invoice.objects.get(pk=invoice_id)
        if action == "confirm":
            inv = inv_svc.confirm_invoice(inv, user=request.user)
        elif action == "post":
            if inv.status == "DRAFT":
                inv = inv_svc.confirm_invoice(inv, user=request.user)
            inv = inv_svc.post_invoice(inv, user=request.user)
        elif action == "cancel":
            inv = inv_svc.cancel_invoice(inv, user=request.user, reason=param(request, "reason", "") or "")
        elif action == "reverse":
            when = param(request, "date")
            inv = inv_svc.reverse_invoice(inv, reason=param(request, "reason", required=True), user=request.user,
                                          reversal_date=as_date(when, "date") if when else None)
        elif action == "resync":
            inv = inv_svc.resync_trade_invoice(inv, user=request.user,
                                               reason=param(request, "reason", "Trade edited after posting"))
        else:
            raise ValidationError({"action": "Unknown action."})
        inv = Invoice.objects.select_related("party", "voucher").get(pk=inv.pk)
        return ok(invoice_dict(inv, lines=True))


# --- payments -------------------------------------------------------------------------------------

def _allocations(entity, raw) -> list:
    out = []
    for r in raw or []:
        out.append((Invoice.objects.get(pk=as_int(r.get("invoice_id"), "invoice_id"), entity=entity),
                    as_money(r.get("amount"))))
    return out


class PaymentListView(ApproverView):
    """Recording a payment posts it, so it needs the approver role."""

    def get(self, request):
        e = entity_from(request)
        qs = Payment.objects.filter(entity=e).select_related("party", "voucher").order_by("-date", "-id")
        for f in ("direction", "status"):
            if param(request, f):
                qs = qs.filter(**{f: param(request, f)})
        for f in ("party_id", "bank_account_id"):
            if param(request, f):
                qs = qs.filter(**{f: as_int(param(request, f), f)})
        if param(request, "start"):
            qs = qs.filter(date__gte=as_date(param(request, "start"), "start"))
        if param(request, "end"):
            qs = qs.filter(date__lte=as_date(param(request, "end"), "end"))
        if param(request, "search"):
            qs = qs.filter(reference__icontains=param(request, "search"))
        return ok(page(request, qs, payment_dict))

    def post(self, request):
        e = entity_from(request)
        if param(request, "statement_line_id"):  # additive: the bank transaction it came through (posted + matched)
            return self._post_for_line(request, e)
        p = pay_svc.record_payment(
            entity=e, direction=param(request, "direction", required=True),
            party=CompanyModel.objects.get(pk=as_int(param(request, "party_id", required=True), "party_id")),
            bank_account=BankAccount.objects.get(pk=as_int(param(request, "bank_account_id", required=True),
                                                           "bank_account_id"), entity=e),
            payment_date=as_date(param(request, "date"), "date"), amount=as_money(param(request, "amount")),
            tds_amount=as_money(param(request, "tds_amount"), "tds_amount", "0"),
            mode=param(request, "mode", "NEFT"), reference=param(request, "reference", "") or "",
            narration=param(request, "narration", "") or "",
            allocations=_allocations(e, request.data.get("allocations")), user=request.user,
        )
        return ok(payment_dict(p), status.HTTP_201_CREATED)

    def _post_for_line(self, request, e):
        from apps.accounting.models import StatementLine
        from apps.accounting.services import bank_proposals
        line = StatementLine.objects.select_related("bank_account").get(
            pk=as_int(param(request, "statement_line_id"), "statement_line_id"), bank_account__entity=e)
        if param(request, "bank_account_id") and as_int(param(request, "bank_account_id"), "bank_account_id") != line.bank_account_id:
            raise ValidationError({"bank_account_id": "Does not match the bank of the chosen bank transaction."})
        p = bank_proposals.record_payment_for_line(
            line, entity=e, direction=param(request, "direction", required=True),
            party=CompanyModel.objects.get(pk=as_int(param(request, "party_id", required=True), "party_id")),
            amount=as_money(param(request, "amount")), tds_amount=as_money(param(request, "tds_amount"), "tds_amount", "0"),
            payment_date=as_date(param(request, "date"), "date") if param(request, "date") else None,
            mode=param(request, "mode", "") or "", reference=param(request, "reference", "") or "",
            narration=param(request, "narration", "") or "",
            allocations=_allocations(e, request.data.get("allocations")), user=request.user,
        )
        return ok(payment_dict(p), status.HTTP_201_CREATED)


class PaymentActionView(ApproverView):
    def post(self, request, payment_id: int, action: str):
        p = Payment.objects.get(pk=payment_id)
        if action == "allocate":
            for invoice, amount in _allocations(p.entity, request.data.get("allocations")):
                pay_svc.allocate_payment(p, invoice, amount, user=request.user)
        elif action == "reverse":
            when = param(request, "date")
            pay_svc.reverse_payment(p, reason=param(request, "reason", required=True), user=request.user,
                                    reversal_date=as_date(when, "date") if when else None)
        else:
            raise ValidationError({"action": "Unknown action."})
        return ok(payment_dict(Payment.objects.select_related("party", "voucher").get(pk=p.pk)))


class TradePaymentAccountView(ApproverView):
    """POST {trade_payment_id, bank_account_id} posts it; {trade_payment_id, existing_payment_id} links an
    already-recorded payment/receipt instead (no posting, no double-counted cash)."""

    def post(self, request):
        existing = param(request, "existing_payment_id")
        bank_id = param(request, "bank_account_id")
        if not existing and not bank_id:
            raise ValidationError({"bank_account_id": "Choose the bank account, or the existing payment to link."})
        p = pay_svc.account_trade_payment(
            as_int(param(request, "trade_payment_id", required=True), "trade_payment_id"),
            bank_account=BankAccount.objects.get(pk=as_int(bank_id, "bank_account_id")) if bank_id else None,
            existing_payment=Payment.objects.get(pk=as_int(existing, "existing_payment_id")) if existing else None,
            user=request.user)
        return ok(payment_dict(p), status.HTTP_201_CREATED)


class VoucherAllocateView(ApproverView):
    """POST {allocations: [{invoice_id, amount}]}: allocate the on-account part of a settling voucher."""

    def post(self, request, voucher_id: int):
        v = Voucher.objects.get(pk=voucher_id)
        for invoice, amount in _allocations(v.entity, request.data.get("allocations")):
            pay_svc.allocate_on_account(v, invoice, amount, user=request.user)
        return ok(voucher_dict(Voucher.objects.get(pk=v.pk), lines=True))


# --- trade tracking -------------------------------------------------------------------------------

class TradeTrackingView(AccountingView):
    def get(self, request):
        e = entity_from(request)
        start, end = param(request, "start"), param(request, "end")
        rows = trade_accounting_rows(e, start=as_date(start, "start") if start else None,
                                     end=as_date(end, "end") if end else None, status=param(request, "status"))
        summary: dict = {}
        for r in rows:
            summary[r["accounting_status"]] = summary.get(r["accounting_status"], 0) + 1
        data = page(request, rows)
        data["summary"] = summary
        return ok(data)


# --- tax masters ----------------------------------------------------------------------------------

class TdsSectionView(ApproverView):
    def get(self, request):
        return ok([{"id": s.pk, "code": s.code, "description": s.description, "rate_individual": s.rate_individual,
                    "rate_other": s.rate_other, "rate_no_pan": s.rate_no_pan, "threshold_single": s.threshold_single,
                    "threshold_aggregate": s.threshold_aggregate, "threshold_mode": s.threshold_mode,
                    "effective_from": s.effective_from, "effective_to": s.effective_to}
                   for s in TdsSection.objects.all()])

    def post(self, request):
        to = param(request, "effective_to")
        s = masters_svc.add_tds_section(
            code=param(request, "code", required=True), description=param(request, "description", "") or "",
            rate_individual=as_money(param(request, "rate_individual"), "rate_individual"),
            rate_other=as_money(param(request, "rate_other"), "rate_other"),
            rate_no_pan=as_money(param(request, "rate_no_pan"), "rate_no_pan"),
            threshold_single=as_money(param(request, "threshold_single"), "threshold_single", "0"),
            threshold_aggregate=as_money(param(request, "threshold_aggregate"), "threshold_aggregate", "0"),
            threshold_mode=param(request, "threshold_mode", "FULL"),
            effective_from=as_date(param(request, "effective_from"), "effective_from"),
            effective_to=as_date(to, "effective_to") if to else None, user=request.user)
        return ok({"id": s.pk, "code": s.code}, status.HTTP_201_CREATED)


class LowerDeductionView(ApproverView):
    def get(self, request):
        return ok([{"id": c.pk, "party_id": c.party_id, "section_code": c.section_code,
                    "certificate_no": c.certificate_no, "rate": c.rate, "valid_from": c.valid_from,
                    "valid_to": c.valid_to} for c in LowerDeductionCertificate.objects.all()])

    def post(self, request):
        c = masters_svc.add_lower_deduction_certificate(
            party=CompanyModel.objects.get(pk=as_int(param(request, "party_id", required=True), "party_id")),
            section_code=param(request, "section_code", required=True),
            certificate_no=param(request, "certificate_no", required=True),
            rate=as_money(param(request, "rate"), "rate"),
            valid_from=as_date(param(request, "valid_from"), "valid_from"),
            valid_to=as_date(param(request, "valid_to"), "valid_to"), user=request.user)
        return ok({"id": c.pk}, status.HTTP_201_CREATED)


class PartySearchView(AccountingView):
    """Parties come from the existing company master (no duplicate party master)."""

    def get(self, request):
        qs = CompanyModel.objects.all().order_by("name")
        if param(request, "search"):
            qs = qs.filter(name__icontains=param(request, "search"))
        return ok([{"id": c.pk, "name": c.name, "gstin": c.gst_number, "pan": c.pan} for c in qs[:50]])


class PartySummaryView(AccountingView):
    """GET parties/summary/?entity=&as_of=  Per-party ledger balance and open bills (party master = companies)."""

    def get(self, request):
        from apps.accounting.selectors import reports
        e = entity_from(request)
        _start, end, _fy = period_from(request, e)
        return ok(reports.party_summary(e, as_of=as_date(param(request, "as_of"), "as_of", end),
                                        search=param(request, "search", "") or ""))


class AuditEventView(AccountingView):
    def get(self, request):
        e = entity_from(request)
        qs = AccountingAuditEvent.objects.filter(entity=e).select_related("actor")
        for f in ("object_type", "object_id", "action"):
            if param(request, f):
                qs = qs.filter(**{f: param(request, f)})
        return ok(page(request, qs, lambda a: {"id": a.pk, "action": a.action, "object_type": a.object_type,
                                                "object_id": a.object_id, "at": a.occurred_at, "detail": a.detail,
                                                "actor": a.actor.username if a.actor else None}))
