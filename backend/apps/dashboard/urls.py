from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("stats/", views.DashboardStatsView.as_view(), name="stats"),
    path("charts/utilisation/", views.UtilisationChartView.as_view(), name="utilisation-chart"),
    path("charts/activity/", views.ActivityChartView.as_view(), name="activity-chart"),
    path("expiring-licenses/", views.ExpiringLicensesView.as_view(), name="expiring-licenses"),
]
