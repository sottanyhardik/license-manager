# FILE: accounts/services.py
"""
Service layer for user creation.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


def create_user(username: str, password: str, email: str, first_name: str = "", last_name: str = "") -> User:
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name or "",
            last_name=last_name or ""
        )
        return user
    except Exception as e:
        raise serializers.ValidationError(f"Failed to create user: {e}")
