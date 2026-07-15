from rest_framework.routers import DefaultRouter

from apps.notifications.views import LicenseBalanceNotificationViewSet

app_name = "notifications"

router = DefaultRouter()
router.register(r"balance", LicenseBalanceNotificationViewSet, basename="balance-notifications")

urlpatterns = router.urls
