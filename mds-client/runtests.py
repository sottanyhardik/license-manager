#!/usr/bin/env python
"""
Standalone test runner for mds_client.

Runs the suite with Django's own test runner against ``tests.settings`` — no
pytest, no live MDS, no real DB server required (in-memory SQLite):

    python runtests.py            # run everything
    python runtests.py tests.test_client   # a subset

pytest works too if installed (``pytest.ini`` points at the same settings).
"""

import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
    django.setup()
    TestRunner = get_runner(settings)
    runner = TestRunner(verbosity=2)
    labels = sys.argv[1:] or ["tests"]
    failures = runner.run_tests(labels)
    sys.exit(bool(failures))


if __name__ == "__main__":
    main()
