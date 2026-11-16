"""Backward-compatible facade for the former monolithic ``core.py``.

The models now live in cohesive sibling modules (header, items, planning,
documents, incentive, ledger_jobs).  Every name that used to be importable from
``apps.license.models.core`` (public and private) is re-exported here.
"""
from __future__ import annotations

import uuid  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from datetime import date  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from decimal import Decimal, ROUND_HALF_UP  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from typing import Dict, Any, Optional  # noqa: F401  re-export: facade module, names consumed via apps.license.models

from django.conf import settings  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from django.core.exceptions import ValidationError  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from django.db import models, transaction  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from django.db.models import Count, Sum, DecimalField, Value, Q  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from django.db.models.functions import Coalesce  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from django.db.models.signals import post_save  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from django.dispatch import receiver  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from django.urls import reverse  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from django.utils import timezone  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from django.utils.functional import cached_property  # noqa: F401  re-export: facade module, names consumed via apps.license.models

from apps.allotment.models import AllotmentItems  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden  # noqa: F401  re-export: facade module, names consumed via apps.license.models
# Removed: from bill_of_entry.tasks import update_balance_values_task
# Now using direct synchronous balance updates for better performance
from apps.core.constants import (
    DEC_0,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
    DEC_000,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
    UNIT_CHOICES,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
    CURRENCY_CHOICES,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
    SCHEME_CODE_CHOICES,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
    NOTIFICATION_NORM_CHOICES,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
    GE,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
    KG,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
    USD,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
    ARO,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
    DEBIT,  # noqa: F401  re-export: facade module, names consumed via apps.license.models
)
# Local imports — keep lightweight at module import time
from apps.core.models import AuditModel, InvoiceEntity, ItemNameModel  # noqa: F401  re-export: facade module, names consumed via apps.license.models
from apps.core.models import PurchaseStatus, SchemeCode, NotificationNumber  # kept for compatibility  # noqa: F401  re-export: facade module, names consumed via apps.license.models
# -----------------------------
# Import centralized utilities
# -----------------------------
from apps.core.utils.decimal_utils import to_decimal as _to_decimal, round_decimal_down as round_down  # noqa: F401  re-export: facade module, names consumed via apps.license.models

_D = Decimal  # shorthand

# The imports above are kept only so historic
# ``from apps.license.models.core import <name>`` keeps working.
from .header import (  # noqa: F401,E402
    LicenseDetailsModel,
    LicenseNotes,
    LicenseBalance,
    LicenseFlags,
    LicenseOwnership,
    _ensure_license_subrows,
)
from .items import (  # noqa: F401,E402
    LicenseExportItemModel,
    LicenseImportItemsModel,
    update_balance,
)
from .planning import (  # noqa: F401,E402
    PLANNING_ACTION_TYPES,
    LicenseItemPlan,
    LicenseReplanRequest,
    SionInputAliasConfig,
    SionPlanningAction,
    SionPlanningOutputMapping,
    SionPlanningPercentageRow,
    SionPlanningProfile,
    SionPlanningRule,
    SionPlanningRun,
    SionPlanningUnitValueRow,
    _validate_planning_json,
)
from .documents import (  # noqa: F401,E402
    AlongWithModel,
    DateModel,
    LicenseDocumentModel,
    LicenseInwardOutwardModel,
    LicenseTransferModel,
    OfficeModel,
    StatusModel,
    license_path,
)
from .incentive import IncentiveLicense, LicensePurchase  # noqa: F401,E402
from .ledger_jobs import (  # noqa: F401,E402
    LicenseLedgerPackageItem,
    LicenseLedgerPackageJob,
    LicenseLedgerRecoveryAudit,
    LicensePackageArtifact,
    LicensePackageAuditEvent,
    LicensePackageRequest,
    LicensePackageRequestItem,
)
