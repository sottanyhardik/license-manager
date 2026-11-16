"""Backward-compatible facade for the former monolithic ``core.py``.

The models now live in cohesive sibling modules (header, items, planning,
documents, incentive, ledger_jobs).  Every name that used to be importable from
``apps.license.models.core`` (public and private) is re-exported here.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional

from django.conf import settings
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Count, Sum, DecimalField, Value, Q
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
# Removed: from bill_of_entry.tasks import update_balance_values_task
# Now using direct synchronous balance updates for better performance
from apps.core.constants import (
    DEC_0,
    DEC_000,
    UNIT_CHOICES,
    CURRENCY_CHOICES,
    SCHEME_CODE_CHOICES,
    NOTIFICATION_NORM_CHOICES,
    GE,
    KG,
    USD,
    ARO,
    DEBIT,
)
# Local imports — keep lightweight at module import time
from apps.core.models import AuditModel, InvoiceEntity, ItemNameModel
from apps.core.models import PurchaseStatus, SchemeCode, NotificationNumber  # kept for compatibility
# -----------------------------
# Import centralized utilities
# -----------------------------
from apps.core.utils.decimal_utils import to_decimal as _to_decimal, round_decimal_down as round_down

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
