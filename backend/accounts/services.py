# FILE: accounts/services.py
"""
Small service layer to encapsulate user creation/updating and avatar handling.
Keeps business logic out of views for easier testing.
"""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from typing import Optional
import os

User = get_user_model()


def create_user(username: str, password: str, email: str, first_name: str = "", last_name: str = "") -> User:
    user = User(username=username, email=email, first_name=first_name or "", last_name=last_name or "")
    user.set_password(password)
    user.save()
    return user


def set_avatar(user: User, avatar_file: UploadedFile) -> User:
    # delete old file if exists
    try:
        if user.avatar and hasattr(user.avatar, "path"):
            old_path = user.avatar.path
            if os.path.exists(old_path):
                os.remove(old_path)
    except Exception:
        pass
    user.avatar = avatar_file
    user.save(update_fields=["avatar"])
    return user


def remove_avatar(user: User) -> None:
    try:
        if user.avatar and hasattr(user.avatar, "path"):
            path = user.avatar.path
            user.avatar.delete(save=False)
            if os.path.exists(path):
                os.remove(path)
    except Exception:
        pass
    # Clear field and save
    user.avatar = None
    user.save(update_fields=["avatar"])
