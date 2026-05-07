# FILE: accounts/services.py
"""
Service layer for user creation.
"""

from django.contrib.auth import get_user_model

User = get_user_model()


def create_user(username: str, password: str, email: str, first_name: str = "", last_name: str = "") -> User:
    user = User(username=username, email=email, first_name=first_name or "", last_name=last_name or "")
    user.set_password(password)
    user.save()
    return user
