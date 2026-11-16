"""Production secret/configuration validation (OD-06).

Pure, stdlib-only evaluator shared by:

* ``settings._validate_production_security()``, the import-time fail-closed
  guard for ``DJANGO_ENVIRONMENT=production``, which covers gunicorn, Celery
  worker/beat and every management command, and
* the Django system checks in ``lmanagement/checks.py``
  (``manage.py check --deploy``).

The repository deliberately ships **no** hashes, fingerprints or values of any
secret that is known to have been exposed. Operators can reject such secrets
with an out-of-repo denylist file of sha256 hex digests, pointed to by
``SECURITY_SECRET_DENYLIST_FILE``. See docs/security/OD-06-rotation-runbook.md.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

# Backend fallback used when DJANGO_SECRET_KEY is unset (dev only).
DEFAULT_DEV_SECRET_KEY = "local-dev-only-secret-key-change-for-production-7f8e6d5c4b3a2910"
# Backend fallback used when DB_PASS is unset (local dev / CI throwaway DBs only).
DEFAULT_DEV_DB_PASSWORD = "lmanagement"

# Dev/test/placeholder SECRET_KEY values that already appear in this codebase
# (settings fallbacks, CI and quality-gate key, MDS fallback). These are
# public placeholders, not exposed production secrets.
KNOWN_DEV_SECRET_KEYS = frozenset({
    DEFAULT_DEV_SECRET_KEY,
    "ci-not-a-secret-key-for-tests-only",
    "dev-only-insecure-key-change-me",
})

# Substrings that mark a value as a template placeholder rather than a secret.
_PLACEHOLDER_MARKERS = (
    "django-insecure", "insecure", "change-me", "change_me", "changeme",
    "change-for-production", "not-a-secret", "dev-only", "local-dev", "placeholder",
    "replace", "example", "your-secret", "your_secret", "secret-key-here",
)

# Common weak database passwords (generic; not tied to any exposure).
_WEAK_DB_PASSWORDS = frozenset({
    "postgres", "password", "passw0rd", "admin", "root", "secret", "changeme",
    "123456", "12345678", "qwerty", "letmein", "django", "master_data",
})

# Django's security.W009 criteria.
SECRET_KEY_MIN_LENGTH = 50
SECRET_KEY_MIN_UNIQUE_CHARACTERS = 5
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Finding:
    """One validation failure. ``message`` never contains a secret value."""

    id: str
    message: str
    hint: str = ""


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    if (value.startswith("<") and value.endswith(">")) or value.startswith("${"):
        return True
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_denylist(path_value: str, repo_root: Path) -> tuple[frozenset[str], list[Finding]]:
    """Load sha256 hex digests from an ops-supplied file outside the repo.

    Fails closed: if a denylist path is configured but unusable, the result
    is an error finding rather than silently skipping the check.
    """
    path = Path(path_value).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return frozenset(), [Finding(
            "lmanagement.E030",
            "SECURITY_SECRET_DENYLIST_FILE is set but the file does not exist or is unreadable.",
            "Point it at an existing file outside the repository, or unset it.",
        )]
    root = repo_root.resolve()
    if resolved == root or root in resolved.parents:
        return frozenset(), [Finding(
            "lmanagement.E031",
            "SECURITY_SECRET_DENYLIST_FILE must be outside the repository.",
            "Digests of exposed secrets must never be committed; keep the file in server-side secret storage.",
        )]
    try:
        lines = resolved.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return frozenset(), [Finding(
            "lmanagement.E030",
            "SECURITY_SECRET_DENYLIST_FILE could not be read as UTF-8 text.",
        )]
    digests: set[str] = set()
    bad_lines = 0
    for raw in lines:
        entry = raw.split("#", 1)[0].strip().lower()
        if not entry:
            continue
        if _SHA256_HEX.match(entry):
            digests.add(entry)
        else:
            bad_lines += 1
    findings: list[Finding] = []
    if bad_lines:
        findings.append(Finding(
            "lmanagement.E032",
            f"SECURITY_SECRET_DENYLIST_FILE has {bad_lines} line(s) that are not sha256 hex digests.",
            "One 64-character lowercase hex digest per line; '#' starts a comment.",
        ))
    return frozenset(digests), findings


# Every SECRET_KEY finding starts with the pre-OD-06 operator message
# "DJANGO_SECRET_KEY must be a non-default secret" (pinned by
# apps/core/tests/test_production_settings.py) so existing runbooks/log searches keep working.
def evaluate_secret_key(secret_key: str | None, denylist: frozenset[str] = frozenset()) -> list[Finding]:
    if not secret_key:
        return [Finding("lmanagement.E001", "DJANGO_SECRET_KEY must be a non-default secret: it is missing or empty.",
                        "Generate one: python -c 'import secrets; print(secrets.token_urlsafe(64))'")]
    findings: list[Finding] = []
    if secret_key in KNOWN_DEV_SECRET_KEYS or _is_placeholder(secret_key):
        findings.append(Finding(
            "lmanagement.E002",
            "DJANGO_SECRET_KEY must be a non-default secret: it is a development/test/placeholder value from the repository.",
            "Set DJANGO_SECRET_KEY to a freshly generated secret.",
        ))
    if (
        len(secret_key) < SECRET_KEY_MIN_LENGTH
        or len(set(secret_key)) < SECRET_KEY_MIN_UNIQUE_CHARACTERS
        or secret_key.startswith("django-insecure-")
    ):
        findings.append(Finding(
            "lmanagement.E003",
            f"DJANGO_SECRET_KEY must be a non-default secret: it is weak and needs at least {SECRET_KEY_MIN_LENGTH} characters and "
            f"{SECRET_KEY_MIN_UNIQUE_CHARACTERS} unique characters, without the 'django-insecure-' prefix "
            "(Django security.W009 criteria).",
        ))
    if denylist and sha256_hex(secret_key) in denylist:
        findings.append(Finding(
            "lmanagement.E004",
            "DJANGO_SECRET_KEY must be a non-default secret: it is on the ops denylist (known-exposed secret).",
            "Rotate it: see docs/security/OD-06-rotation-runbook.md.",
        ))
    return findings


def evaluate_db_password(
    password: str | None,
    *,
    db_user: str = "",
    db_name: str = "",
    denylist: frozenset[str] = frozenset(),
) -> list[Finding]:
    if not password:
        return [Finding("lmanagement.E010", "The database password (DB_PASS) is missing or empty.")]
    findings: list[Finding] = []
    lowered = password.lower()
    if (
        password == DEFAULT_DEV_DB_PASSWORD
        or lowered in _WEAK_DB_PASSWORDS
        or (db_user and lowered == db_user.lower())
        or (db_name and lowered == db_name.lower())
        or _is_placeholder(password)
    ):
        findings.append(Finding(
            "lmanagement.E011",
            "The database password is a well-known development default, a placeholder, "
            "or equal to the DB user/name.",
            "Rotate the DB role password and set DB_PASS from the server secret store.",
        ))
    if denylist and sha256_hex(password) in denylist:
        findings.append(Finding(
            "lmanagement.E012",
            "The database password is on the ops denylist (known-exposed secret).",
            "Rotate it: see docs/security/OD-06-rotation-runbook.md.",
        ))
    return findings


def evaluate_production_secrets(
    *,
    secret_key: str | None,
    db_password: str | None,
    db_user: str,
    db_name: str,
    debug: bool,
    denylist_path: str | None,
    repo_root: Path,
) -> list[Finding]:
    """Return every finding for a process that claims to be production."""
    findings: list[Finding] = []
    if debug:
        findings.append(Finding("lmanagement.E020", "DEBUG must be False in production."))
    denylist: frozenset[str] = frozenset()
    if denylist_path and denylist_path.strip():
        denylist, deny_findings = load_denylist(denylist_path.strip(), repo_root)
        findings.extend(deny_findings)
    findings.extend(evaluate_secret_key(secret_key, denylist))
    findings.extend(evaluate_db_password(db_password, db_user=db_user, db_name=db_name, denylist=denylist))
    return findings
