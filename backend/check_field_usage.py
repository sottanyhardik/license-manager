#!/usr/bin/env python

import os
import re
from pathlib import Path

import django

# -----------------------------
# Configure Django
# -----------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
django.setup()

from django.apps import apps

# -----------------------------
# Configuration
# -----------------------------

PROJECT_ROOT = Path(".").resolve()

IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "migrations",
    "static",
    "media",
}

FILE_EXTENSIONS = {
    ".py",
    ".html",
    ".txt",
    ".jinja",
    ".sql",
}

# -----------------------------
# Read project files once
# -----------------------------

files = []

for root, dirs, filenames in os.walk(PROJECT_ROOT):
    dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

    for filename in filenames:
        path = Path(root) / filename

        if path.suffix not in FILE_EXTENSIONS:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            files.append((str(path), content))
        except Exception:
            pass

# -----------------------------
# Scan fields
# -----------------------------

results = []

for model in apps.get_models():
    app_name = model._meta.app_label
    model_name = model.__name__

    for field in model._meta.fields:

        field_name = field.name

        patterns = [
            rf"\.{re.escape(field_name)}\b",
            rf"\b{re.escape(field_name)}=",
            rf"\b{re.escape(field_name)}__",
            rf'"{re.escape(field_name)}"',
            rf"'{re.escape(field_name)}'",
        ]

        count = 0
        matched_files = []

        for filename, content in files:

            found = False

            for pattern in patterns:
                matches = re.findall(pattern, content)

                if matches:
                    count += len(matches)
                    found = True

            if found:
                matched_files.append(filename)

        results.append(
            {
                "app": app_name,
                "model": model_name,
                "field": field_name,
                "count": count,
                "files": matched_files,
            }
        )

# -----------------------------
# Print report
# -----------------------------

results.sort(key=lambda x: (x["count"], x["model"], x["field"]))

print("=" * 100)
print(f"{'MODEL':30} {'FIELD':25} {'USAGES':8}")
print("=" * 100)

for r in results:
    print(
        f"{r['app']}.{r['model']:<25} "
        f"{r['field']:<25} "
        f"{r['count']:<8}"
    )

print("\n")
print("=" * 100)
print("POTENTIALLY UNUSED FIELDS")
print("=" * 100)

for r in results:
    if r["count"] == 0:
        print(
            f"{r['app']}.{r['model']}.{r['field']}"
        )
