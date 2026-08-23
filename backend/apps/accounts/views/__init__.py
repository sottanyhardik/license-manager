# accounts/views/__init__.py
# expose well-known names for consistency
from .auth import LoginView, LogoutView, MeView
from .password import PasswordResetRequestView, PasswordResetConfirmView, ChangePasswordView
from .user_management import UserManagementViewSet

__all__ = [
    "LoginView",
    "LogoutView",
    "MeView",
    "PasswordResetConfirmView",
    "PasswordResetRequestView",
    "ChangePasswordView",
    "UserManagementViewSet",
]
