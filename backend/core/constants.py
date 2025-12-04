"""
Global project-wide constants & choice tuples.
Import these wherever needed instead of redefining choices in each model.
"""

from decimal import Decimal

# ───────────────────────────────
# Transaction Type
# ───────────────────────────────
CREDIT = "C"
DEBIT = "D"

TYPE_CHOICES = (
    (CREDIT, "Credit"),
    (DEBIT, "Debit"),
)

# ───────────────────────────────
# Row Types (ARO / Allotment)
# ───────────────────────────────
ARO = "AR"
ALLOTMENT = "AT"

ROW_TYPE_CHOICES = (
    (ARO, "ARO"),
    (ALLOTMENT, "Allotment"),
)

# ───────────────────────────────
# Units
# ───────────────────────────────
KG = "kg"

UNIT_CHOICES = (
    (KG, "kg"),
)

# ───────────────────────────────
# Currency Choices
# ───────────────────────────────
USD = "usd"
EURO = "euro"

CURRENCY_CHOICES = (
    (USD, "usd"),
    (EURO, "euro"),
)

# ───────────────────────────────
# Scheme Codes
# ───────────────────────────────
DFIA = "26"

SCHEME_CODE_CHOICES = (
    (DFIA, "26 - Duty Free Import Authorization"),
)

# ───────────────────────────────
# Notifications (Norms)
# ───────────────────────────────
N2009 = "098/2009"
N2015 = "019/2015"
N2023 = "025/2023"

NOTIFICATION_NORM_CHOICES = (
    (N2015, "019/2015"),
    (N2009, "098/2009"),
    (N2023, "025/2023"),
)

# ───────────────────────────────
# License Purchase Types
# ───────────────────────────────
GE = "GE"
MI = "NP"
IP = "IP"
SM = "SM"
OT = "OT"
CO = "CO"
RA = "RA"
LM = "LM"

# Full choices with is_active status (value, label, is_active)
LICENCE_PURCHASE_CHOICES_FULL = (
    (GE, "GE Purchase", True),
    (MI, "GE Operating", True),
    (IP, "GE Item Purchase", True),
    (SM, "SM Purchase", True),
    (OT, "OT Purchase", True),
    (CO, "Conversion", True),
    (RA, "Ravi Foods", True),
    (LM, "LM Purchase", False),  # Hidden/inactive
)

# Standard choices for model field (all options)
LICENCE_PURCHASE_CHOICES = tuple((code, label) for code, label, _ in LICENCE_PURCHASE_CHOICES_FULL)

# Active choices only (for display in UI)
LICENCE_PURCHASE_CHOICES_ACTIVE = tuple((code, label) for code, label, active in LICENCE_PURCHASE_CHOICES_FULL if active)

# ───────────────────────────────
# Decimal Defaults
# ───────────────────────────────
DEC_0 = Decimal("0.00")
DEC_000 = Decimal("0.000")
