from django.urls import path
from .views.auth import (
    LoginView, LogoutView, MeView,
)
from .views.password import (

    PasswordResetRequestView, PasswordResetConfirmView)

from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="api-login"),
    path("auth/logout/", LogoutView.as_view(), name="api-logout"),
    path("auth/me/", MeView.as_view(), name="api-me"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Forgot password
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("auth/password-reset-confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
]
