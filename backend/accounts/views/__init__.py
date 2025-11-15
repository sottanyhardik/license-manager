# accounts/views/__init__.py
# expose well-known names for consistency
from .auth import LoginView, LogoutView, MeView  # noqa
from .password import PasswordResetRequestView, PasswordResetConfirmView