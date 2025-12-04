# FILE: lmanagement/__init__.py
# Ensure the Celery app is loaded when Django starts
from .celery import app as celery_app  # noqa: F401

__all__ = ("celery_app",)
