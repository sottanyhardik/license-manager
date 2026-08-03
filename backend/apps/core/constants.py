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
PCS = "pcs"
NOS = "nos"
MTS = "mts"

UNIT_CHOICES = (
    (KG, "Kgs"),
    (PCS, "Pcs"),
    (NOS, "Nos"),
    (MTS, "Mts"),
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

# ───────────────────────────────
# Decimal Defaults
# ───────────────────────────────
DEC_0 = Decimal("0.00")
DEC_000 = Decimal("0.000")
