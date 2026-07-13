"""pytest bootstrap: point Django at the test settings before anything imports it."""

import os

import django


def pytest_configure(config):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
    django.setup()
