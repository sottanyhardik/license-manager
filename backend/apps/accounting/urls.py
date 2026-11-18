from django.urls import path

from .api import views as v
from .api import views_banking as b
from .api import views_reports as r

app_name = "accounting"

urlpatterns = [
    path("accounting/entities/", v.EntityListView.as_view(), name="entities"),
    path("accounting/entities/<int:entity_id>/", v.EntityDetailView.as_view(), name="entity-detail"),
    path("accounting/entities/<int:entity_id>/financial-years/", v.FinancialYearOpenView.as_view(), name="fy-open"),
    path("accounting/periods/<int:period_id>/lock/", v.PeriodLockView.as_view(), name="period-lock"),
    path("accounting/accounts/", v.AccountListView.as_view(), name="accounts"),
    path("accounting/accounts/<int:account_id>/", v.AccountDetailView.as_view(), name="account-detail"),
    path("accounting/cost-centres/", v.CostCentreView.as_view(), name="cost-centres"),
    path("accounting/parties/", v.PartySearchView.as_view(), name="parties"),
    path("accounting/parties/summary/", v.PartySummaryView.as_view(), name="party-summary"),
    path("accounting/vouchers/", v.VoucherListView.as_view(), name="vouchers"),
    path("accounting/vouchers/<int:voucher_id>/", v.VoucherDetailView.as_view(), name="voucher-detail"),
    path("accounting/vouchers/<int:voucher_id>/post/", v.VoucherPostView.as_view(), name="voucher-post"),
    path("accounting/vouchers/<int:voucher_id>/reverse/", v.VoucherReverseView.as_view(), name="voucher-reverse"),
    path("accounting/vouchers/<int:voucher_id>/allocate/", v.VoucherAllocateView.as_view(), name="voucher-allocate"),
    path("accounting/invoices/", v.InvoiceListView.as_view(), name="invoices"),
    path("accounting/invoices/from-trade/", v.InvoiceFromTradeView.as_view(), name="invoice-from-trade"),
    path("accounting/invoices/<int:invoice_id>/", v.InvoiceDetailView.as_view(), name="invoice-detail"),
    path("accounting/invoices/<int:invoice_id>/<str:action>/", v.InvoiceActionView.as_view(), name="invoice-action"),
    path("accounting/payments/", v.PaymentListView.as_view(), name="payments"),
    path("accounting/payments/from-trade-payment/", v.TradePaymentAccountView.as_view(), name="payment-from-trade"),
    path("accounting/payments/<int:payment_id>/<str:action>/", v.PaymentActionView.as_view(), name="payment-action"),
    path("accounting/trades/", v.TradeTrackingView.as_view(), name="trade-tracking"),
    path("accounting/tds-sections/", v.TdsSectionView.as_view(), name="tds-sections"),
    path("accounting/lower-deduction-certificates/", v.LowerDeductionView.as_view(), name="ldc"),
    path("accounting/audit/", v.AuditEventView.as_view(), name="audit"),
    # banking
    path("accounting/bank-accounts/", b.BankAccountListView.as_view(), name="bank-accounts"),
    path("accounting/bank-accounts/<int:bank_id>/statements/", b.StatementUploadView.as_view(), name="statements"),
    path("accounting/bank-accounts/<int:bank_id>/lines/", b.StatementLineListView.as_view(), name="statement-lines"),
    path("accounting/bank-accounts/<int:bank_id>/auto-match/", b.AutoMatchView.as_view(), name="auto-match"),
    path("accounting/bank-accounts/<int:bank_id>/reconciliation/", b.ReconciliationView.as_view(), name="brs"),
    path("accounting/statement-lines/<int:line_id>/candidates/", b.LineCandidatesView.as_view(), name="candidates"),
    path("accounting/statement-lines/<int:line_id>/match/", b.ManualMatchView.as_view(), name="manual-match"),
    path("accounting/bank-matches/<int:match_id>/unmatch/", b.UnmatchView.as_view(), name="unmatch"),
    path("accounting/bank-accounts/<int:bank_id>/proposals/", b.BankProposalListView.as_view(), name="bank-proposals"),
    path("accounting/bank-accounts/<int:bank_id>/proposals/confirm/", b.BankProposalConfirmView.as_view(),
         name="bank-proposals-confirm"),
    path("accounting/statement-lines/<int:line_id>/proposal/", b.LineProposalView.as_view(), name="line-proposal"),
    path("accounting/statement-lines/<int:line_id>/split/", b.LineSplitView.as_view(), name="line-split"),
    path("accounting/parties/<int:party_id>/bank-lines/", b.PartyBankLinesView.as_view(), name="party-bank-lines"),
    path("accounting/bank-proposals/<int:payment_id>/undo/", b.UndoProposalView.as_view(), name="undo-proposal"),
    path("accounting/narration-aliases/", b.NarrationAliasView.as_view(), name="narration-aliases"),
    path("accounting/narration-aliases/<int:alias_id>/", b.NarrationAliasView.as_view(), name="narration-alias"),
    path("accounting/suspense/", b.SuspenseView.as_view(), name="suspense"),
    path("accounting/suspense/<int:item_id>/resolve/", b.SuspenseResolveView.as_view(), name="suspense-resolve"),
    path("accounting/licence-bank-ledger/<int:license_id>/", b.LicenceBankLedgerView.as_view(), name="licence-bank-ledger"),
    # reports, loans, migration
    path("accounting/reports/consolidated/", r.ConsolidatedView.as_view(), name="consolidated"),
    path("accounting/reports/<str:name>/", r.ReportView.as_view(), name="report"),
    path("accounting/loans/", r.LoanListView.as_view(), name="loans"),
    path("accounting/loans/<int:loan_id>/<str:action>/", r.LoanActionView.as_view(), name="loan-action"),
    path("accounting/migration/", r.MigrationView.as_view(), name="migration"),
    path("accounting/migration/runs/<int:run_id>/", r.MigrationRunView.as_view(), name="migration-run"),
]
