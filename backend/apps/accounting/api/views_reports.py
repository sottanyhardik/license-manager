"""Reports (all from the GL), loans and the historical migration center."""
from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import ValidationError

from apps.accounting.models import (
    NOTE_KINDS, PAYABLE_KINDS, RECEIVABLE_KINDS, Account, BankAccount, EntityBooks, Loan, MigrationRun,
)
from apps.accounting.selectors import ledger, reports
from apps.accounting.services import loans as loan_svc
from apps.accounting.services import migration as mig_svc
from apps.core.models import CompanyModel

from .common import AccountingView, ApproverView, as_date, as_int, as_money, entity_from, ok, param, period_from

REGISTER_KINDS = {
    "purchase": ["PURCHASE"], "sales": ["SALES"], "expense": ["EXPENSE"],
    "commission": ["COMMISSION_PAYABLE", "COMMISSION_RECEIVABLE"], "notes": list(NOTE_KINDS),
    "payables": list(PAYABLE_KINDS), "receivables": list(RECEIVABLE_KINDS),
}


class ReportView(AccountingView):
    """GET /reports/<name>/?entity=&fy= | start=&end= [&account=&party=&kind=&as_of=]"""

    def get(self, request, name: str):
        e = entity_from(request)
        start, end, fy_start = period_from(request, e)
        if name == "trial-balance":
            return ok(ledger.trial_balance(e, start=start, end=end, fy_start=fy_start))
        if name == "profit-loss":
            return ok(reports.profit_and_loss(e, start, end))
        if name == "profit-loss-monthly":
            return ok(reports.monthly_profit_and_loss(e, start, end))
        if name == "balance-sheet":
            return ok(reports.balance_sheet(e, as_date(param(request, "as_of"), "as_of", end)))
        if name == "cash-flow":
            return ok(reports.cash_flow(e, start, end))
        if name == "general-ledger":
            acct = Account.objects.select_related("group").get(pk=as_int(param(request, "account", required=True),
                                                                         "account"), entity=e)
            return ok(ledger.general_ledger(acct, start=start, end=end))
        if name == "party-ledger":
            return ok(ledger.party_ledger(e, as_int(param(request, "party", required=True), "party"),
                                          start=start, end=end))
        if name in ("receivables-ageing", "payables-ageing"):
            return ok(reports.ageing(e, receivable=name.startswith("receivables"),
                                     as_of=as_date(param(request, "as_of"), "as_of", end)))
        if name == "register":
            kind = param(request, "kind", "sales")
            if kind not in REGISTER_KINDS:
                raise ValidationError({"kind": f"One of {', '.join(REGISTER_KINDS)}."})
            return ok(reports.register(e, REGISTER_KINDS[kind], start, end))
        if name == "tds":
            return ok(reports.tds_register(e, start, end))
        if name == "gst":
            return ok(reports.gst_register(e, start, end))
        if name == "trade-profitability":
            return ok(reports.trade_profitability(e, start, end))
        if name == "suspense":
            return ok(reports.suspense_register(e, as_of=end))
        if name == "loans":
            return ok(reports.loan_register(e, as_of=end))
        if name in ("bank-book", "cash-book"):
            kind = "BANK" if name == "bank-book" else "CASH"
            return ok([ledger.general_ledger(a, start=start, end=end)
                       for a in Account.objects.filter(entity=e, kind=kind).select_related("group")])
        if name == "dashboard":
            return ok(reports.dashboard(e, start, end))
        raise ValidationError({"report": f"Unknown report '{name}'."})


class ConsolidatedView(AccountingView):
    """GET /reports/consolidated/?entities=1,2&start=&end= (separate reporting function)."""

    def get(self, request):
        raw = param(request, "entities")
        qs = EntityBooks.objects.filter(is_active=True).select_related("company")
        if raw:
            qs = qs.filter(pk__in=[as_int(x, "entities") for x in str(raw).split(",") if x.strip()])
        entities = list(qs)
        if not entities:
            raise ValidationError({"entities": "No entity books selected."})
        from apps.accounting.services.books import fy_bounds
        from django.utils import timezone
        _l, fy_start, fy_end = fy_bounds(timezone.localdate())
        start = as_date(param(request, "start"), "start", fy_start)
        end = as_date(param(request, "end"), "end", fy_end)
        return ok(reports.consolidated(entities, start, end))


# --- loans ----------------------------------------------------------------------------------------

def _loan_dict(loan: Loan) -> dict:
    return {"id": loan.pk, "entity_id": loan.entity_id, "party_id": loan.party_id, "party": loan.party.name,
            "direction": loan.direction, "loan_type": loan.loan_type, "principal": loan.principal,
            "interest_rate": loan.interest_rate, "compound": loan.compound, "repayment_type": loan.repayment_type,
            "start_date": loan.start_date, "maturity_date": loan.maturity_date, "status": loan.status,
            "closed_on": loan.closed_on, "bank_account_id": loan.bank_account_id,
            "principal_account_id": loan.principal_account_id, "interest_account_id": loan.interest_account_id,
            "principal_outstanding": loan_svc.principal_outstanding(loan),
            "interest_outstanding": loan_svc.interest_outstanding(loan),
            "accruals": [{"period_start": a.period_start, "period_end": a.period_end, "amount": a.amount,
                          "voucher_id": a.voucher_id} for a in loan.accruals.all()]}


class LoanListView(ApproverView):
    def get(self, request):
        e = entity_from(request)
        return ok([_loan_dict(x) for x in Loan.objects.filter(entity=e).select_related("party")])

    def post(self, request):
        e = entity_from(request)
        maturity = param(request, "maturity_date")
        tenure = param(request, "tenure_months")
        loan = loan_svc.create_loan(
            entity=e, party=CompanyModel.objects.get(pk=as_int(param(request, "party_id", required=True), "party_id")),
            direction=param(request, "direction", required=True), principal=as_money(param(request, "principal"),
                                                                                    "principal"),
            interest_rate=as_money(param(request, "interest_rate"), "interest_rate"),
            start_date=as_date(param(request, "start_date"), "start_date"),
            bank_account=BankAccount.objects.get(pk=as_int(param(request, "bank_account_id", required=True),
                                                           "bank_account_id"), entity=e),
            maturity_date=as_date(maturity, "maturity_date") if maturity else None,
            compound=str(param(request, "compound", "false")).lower() in ("1", "true", "yes"),
            repayment_type=param(request, "repayment_type", "FLEXIBLE"),
            tenure_months=as_int(tenure, "tenure_months") if tenure else None,
            loan_type=param(request, "loan_type", "") or "", user=request.user)
        return ok(_loan_dict(loan), status.HTTP_201_CREATED)


class LoanActionView(ApproverView):
    def post(self, request, loan_id: int, action: str):
        loan = Loan.objects.select_related("party").get(pk=loan_id)
        on = as_date(param(request, "date"), "date")
        if action == "accrue":
            loan_svc.accrue_interest(loan, period_end=on, user=request.user)
        elif action == "repay":
            loan_svc.record_repayment(loan, on=on, principal=as_money(param(request, "principal"), "principal", "0"),
                                      interest=as_money(param(request, "interest"), "interest", "0"),
                                      tds=as_money(param(request, "tds"), "tds", "0"),
                                      reference=param(request, "reference", "") or "", user=request.user)
        elif action == "disburse":
            loan_svc.disburse_loan(loan, amount=as_money(param(request, "amount")), on=on, user=request.user)
        elif action == "close":
            loan_svc.close_loan(loan, on=on, user=request.user)
        else:
            raise ValidationError({"action": "Unknown action."})
        return ok(_loan_dict(Loan.objects.select_related("party").get(pk=loan.pk)))


# --- migration center -----------------------------------------------------------------------------

def _run_dict(run: MigrationRun, items: bool = False) -> dict:
    data = {"id": run.pk, "entity_id": run.entity_id, "mode": run.mode, "parameters": run.parameters,
            "summary": run.summary, "created_on": run.created_on,
            "created_by": run.created_by.username if run.created_by else None}
    if items:
        data["items"] = [{"source_type": i.source_type, "source_id": i.source_id, "classification": i.classification,
                          "outcome": i.outcome, "reasons": i.reasons, "amount": i.amount,
                          "financial_year": i.financial_year} for i in run.items.all()]
    return data


class MigrationView(ApproverView):
    """GET: runs + live reconciliation. POST {mode: DRY_RUN} or {mode: EXECUTE, confirm: true, bank_account_id?}."""

    def get(self, request):
        e = entity_from(request)
        return ok({"runs": [_run_dict(r) for r in MigrationRun.objects.filter(entity=e).select_related("created_by")[:20]],
                   "reconciliation": mig_svc.reconcile(e)})

    def post(self, request):
        e = entity_from(request)
        mode = param(request, "mode", "DRY_RUN")
        if mode == "DRY_RUN":
            run = mig_svc.dry_run(e, user=request.user)
        elif mode == "EXECUTE":
            bank_id = param(request, "bank_account_id")
            trade_ids = request.data.get("trade_ids")
            run = mig_svc.execute(
                e, bank_account=BankAccount.objects.get(pk=as_int(bank_id, "bank_account_id"), entity=e) if bank_id else None,
                confirm=str(param(request, "confirm", "false")).lower() in ("1", "true", "yes"), user=request.user,
                trade_ids=[as_int(t, "trade_ids") for t in trade_ids] if trade_ids else None)
        else:
            raise ValidationError({"mode": "DRY_RUN or EXECUTE."})
        return ok(_run_dict(run, items=True), status.HTTP_201_CREATED)


class MigrationRunView(ApproverView):
    def get(self, request, run_id: int):
        return ok(_run_dict(MigrationRun.objects.select_related("created_by").get(pk=run_id), items=True))
