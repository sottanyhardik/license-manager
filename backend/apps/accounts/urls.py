# accounts/urls.py
from django.urls import path
from .views import LoginView, LogoutView, TokenRefreshView, MeView, UsersView

app_name = "accounts"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("users/", UsersView.as_view(), name="users-list"),
]
