"""
pytest plugin: patches all managed=False models to managed=True
so the test runner creates tables in the SQLite test DB.

Loaded via conftest.py: pytest_plugins = ["conftest_managed"]
"""


def pytest_configure(config):
    """Called by pytest before Django is configured -- skip here."""
    pass


def pytest_sessionstart(session):
    """Called after Django setup. Patch all managed=False models."""
    _patch_all_managed()


def _patch_all_managed():
    """Set managed=True on every model that has managed=False."""
    try:
        from django.apps import apps as django_apps
        for model in django_apps.get_models():
            if not model._meta.managed:
                model._meta.managed = True
    except Exception:
        pass  # Django not yet ready -- will be called again after setup
