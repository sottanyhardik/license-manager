import os

# Must be set BEFORE base.py is imported because base.py does os.environ["SECRET_KEY"]
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use")  # noqa: S105

from .base import *  # noqa: F401, F403

# Remove health_check sub-apps that are not installed in the test virtualenv.
# health_check itself is installed but health_check.db / health_check.cache are
# optional extras that are not present — strip them to prevent ModuleNotFoundError.
INSTALLED_APPS = [
    app for app in INSTALLED_APPS  # noqa: F405
    if app not in ("health_check.db", "health_check.cache")
]

SECRET_KEY = "test-secret-key-not-for-production-use"  # noqa: S105
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ---------------------------------------------------------------------------
# Test-only: make the proxy User model managed so SQLite creates the table.
# In production (PostgreSQL) managed=False because the table already exists.
# ---------------------------------------------------------------------------
def _patch_accounts_user_managed():
    """
    Override accounts.User.Meta.managed → True so pytest-django's
    --create-db creates the table in the in-memory SQLite test DB.
    Called at import time; safe because Django has not yet set up apps.
    """
    try:
        from apps.accounts.models import User
        User._meta.managed = True
    except Exception:
        pass


_patch_accounts_user_managed()


def _patch_core_managed():
    """
    Override all managed=False core models → managed=True so pytest-django's
    SQLite test DB can create the tables. In production (PostgreSQL) the tables
    are owned by the legacy backend and managed=False is correct.
    """
    try:
        from apps.core import models as core_models
        _managed_models = [
            "CompanyModel", "PortModel", "HSCodeModel", "HeadSIONNormsModel",
            "SionNormClassModel", "ItemGroupModel", "ItemNameModel",
            "ExchangeRateModel", "InvoiceEntity", "SchemeCode",
            "NotificationNumber", "PurchaseStatus", "TransferLetterModel",
            "UnitPriceModel", "ProductDescriptionModel", "SIONExportModel",
            "SIONImportModel", "SionNormNote", "SionNormCondition",
            "ItemHeadModel", "MasterChange", "CeleryTaskTracker", "ActivityLog",
        ]
        for model_name in _managed_models:
            model_cls = getattr(core_models, model_name, None)
            if model_cls is not None:
                model_cls._meta.managed = True
    except Exception:
        pass


_patch_core_managed()


def _patch_license_managed():
    """
    Override all managed=False license models → managed=True so pytest-django's
    SQLite test DB can create the tables. In production (PostgreSQL) the tables
    are owned by the legacy backend and managed=False is correct.
    """
    try:
        from apps.license import models as license_models

        _managed_models = [
            "LicenseDetailsModel",
            "LicenseExportItemModel",
            "LicenseImportItemsModel",
            "LicenseBalance",
            "LicenseFlags",
            "LicenseNotes",
            "LicenseOwnership",
            "LicenseDocumentModel",
            "LicenseTransferModel",
            "LicenseItemPlan",
            "LicensePurchase",
            "IncentiveLicense",
            "Invoice",
            "InvoiceItem",
            "StatusModel",
            "OfficeModel",
            "AlongWithModel",
            "DateModel",
            "LicenseInwardOutwardModel",
        ]
        for model_name in _managed_models:
            model_cls = getattr(license_models, model_name, None)
            if model_cls is not None:
                model_cls._meta.managed = True
    except Exception:
        pass


_patch_license_managed()


def _patch_allotment_managed():
    """
    Override all managed=False allotment models → managed=True so pytest-django's
    SQLite test DB can create the tables. In production (PostgreSQL) the tables
    are owned by the legacy backend and managed=False is correct.
    """
    try:
        from apps.allotment import models as allotment_models

        _managed_models = ["AllotmentModel", "AllotmentItems"]
        for model_name in _managed_models:
            model_cls = getattr(allotment_models, model_name, None)
            if model_cls is not None:
                model_cls._meta.managed = True
    except Exception:
        pass


_patch_allotment_managed()


def _patch_bill_of_entry_managed():
    """
    Override all managed=False bill_of_entry models → managed=True so pytest-django's
    SQLite test DB can create the tables. In production (PostgreSQL) the tables
    are owned by the legacy backend and managed=False is correct.
    """
    try:
        from apps.bill_of_entry import models as boe_models

        _managed_models = ["BillOfEntryModel", "RowDetails"]
        for model_name in _managed_models:
            model_cls = getattr(boe_models, model_name, None)
            if model_cls is not None:
                model_cls._meta.managed = True
    except Exception:
        pass


_patch_bill_of_entry_managed()
