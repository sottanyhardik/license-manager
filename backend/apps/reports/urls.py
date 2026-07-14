from django.urls import path

from .views import (
    GenerateBalanceReportView,
    GenerateItemReportView,
    GenerateLedgerReportView,
    GeneratePivotReportView,
    ReportTaskStatusView,
)

app_name = "reports"

urlpatterns = [
    path("balance/generate/", GenerateBalanceReportView.as_view(), name="balance-generate"),
    path("items/generate/", GenerateItemReportView.as_view(), name="items-generate"),
    path("pivot/generate/", GeneratePivotReportView.as_view(), name="pivot-generate"),
    path("ledger/generate/", GenerateLedgerReportView.as_view(), name="ledger-generate"),
    path("task/<str:task_id>/status/", ReportTaskStatusView.as_view(), name="task-status"),
]
