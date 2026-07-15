# accounts/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LoginView, LogoutView, MeView, TokenRefreshView, UserViewSet, UsersView

app_name = "accounts"

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user-management")

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
    # Full CRUD viewset (includes available-roles, reset-password actions)
    path("", include(router.urls)),
]
