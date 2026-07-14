from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.accounts.urls", namespace="accounts")),
    path("masters/", include("apps.core.urls", namespace="core")),
    path("", include("apps.license.urls", namespace="license")),
    path("allotments/", include("apps.allotment.urls", namespace="allotment")),
    path("bill-of-entries/", include("apps.bill_of_entry.urls", namespace="bill_of_entry")),
    path("tasks/", include("apps.tasks.urls", namespace="tasks")),
    path("reports/", include("apps.reports.urls", namespace="reports")),
    path("dashboard/", include("apps.dashboard.urls", namespace="dashboard")),
    path("trades/", include("apps.trade.urls", namespace="trade")),
]
