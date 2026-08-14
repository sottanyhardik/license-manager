"""
THE canonical License Ledger accounting + filter semantics.

Every License Ledger consumer — the ledger list, `summary`, `license_wise`,
`company_wise`, `ledger_detail`, and the PDF/Excel exporters that ride on them —
reads its filter and date rules from THIS module. There is deliberately no second
implementation: an endpoint may differ from another only in how it GROUPS and
LABELS the canonical rows, never in which licences or which transactions it
selects.

========================================================================
1. FIRST PURCHASE DATE — GLOBAL, LICENCE-SPECIFIC, ACROSS ALL COMPANIES
========================================================================

    first_purchase_date(licence)
        = MIN(qualifying purchase invoice_date) over the LICENCE
          across EVERY company

It is a property of the LICENCE, not of a (licence, company) pair. The Company
filter NEVER changes it. The definition itself is owned by
`apps.license.services.license_profit` and is not restated here — this module
only consumes it.

Worked example (mandated):

    Licence L001
        Company A  PURCHASE 16-Dec-2025
        Company B  PURCHASE 17-Jan-2026,  SALE 20-Jan-2026

    first_purchase_date = 16-Dec-2025      <- Company A's, globally
    ...and it stays 16-Dec-2025 even when the report is filtered to Company B.

========================================================================
2. PURCHASE DATE RANGE — LICENCE ELIGIBILITY
========================================================================

    eligible  <=>  purchase_start_date <= first_purchase_date <= purchase_end_date

BOTH bounds are INCLUSIVE, and the range is a BETWEEN — not a "<= end" cutoff:

    first_purchase_date <  start   -> EXCLUDE
    first_purchase_date == start   -> INCLUDE
    first_purchase_date inside     -> INCLUDE
    first_purchase_date == end     -> INCLUDE
    first_purchase_date >  end     -> EXCLUDE

A licence therefore belongs to the period in which it was ACQUIRED. Later top-up
purchases never pull it into a later window, which is what keeps monthly figures
additive (one licence, one acquisition period).

Continuing the L001 example with report 01-Jan-2026 .. 31-Jan-2026 and the
Company filter set to Company B:

    16-Dec-2025 < 01-Jan-2026   ->  L001 is EXCLUDED

even though Company B both bought and sold inside January. Company B's own
January purchase does NOT become the licence's first purchase.

========================================================================
3. TRANSACTION PERIOD — PERIOD ACTIVITY
========================================================================

Once a licence is eligible, and only then:

    in period  <=>  report_start_date <= transaction_date <= report_end_date

        LICENCE ELIGIBILITY   !=   TRANSACTION PERIOD

Transactions before ``report_start_date`` are historical — they form the opening
/ carried-forward position, never period activity. Transactions after
``report_end_date`` are excluded outright.

========================================================================
4. ORDER OF OPERATIONS — FIXED
========================================================================

    ALL LICENCES
        |  global first_purchase_date               (never company-scoped)
    Purchase Date Range eligibility                 (BETWEEN, inclusive)
        |
    ELIGIBLE LICENCE SET
        |  Company filter                           (role-scoped, see _own_and_party)
    company transactions in period
        |
    Debit / Credit  ->  Profit / Loss

The Company filter is applied AFTER eligibility. Reversing these two steps is the
defect this module exists to prevent.

========================================================================
5. PURCHASE BILL MODE — A SPECIAL OVERRIDE
========================================================================

    ALL                 no constraint (default)
    WITH_PURCHASE_BILL  licence has a qualifying purchase bill
    NO_PURCHASE_BILL    licence has NO qualifying purchase bill

`NO_PURCHASE_BILL` is an OVERRIDE MODE: it BYPASSES Purchase Date Range
eligibility entirely. It has to, definitionally — a licence with no qualifying
purchase bill has no ``first_purchase_date``, so any date range would eliminate
the whole population the user just asked to see.

    NO_PURCHASE_BILL means:   no qualifying purchase bill EXISTS
    It does NOT mean:         no purchase in the selected month
                              no transaction in the selected period
                              first purchase outside the date range

COMPANY-SCOPED. With a Company filter active the question becomes "does THIS
COMPANY have a qualifying purchase bill for this licence?" So for

    Licence L004:  Company A -> purchase exists
                   Company B -> no purchase bill

    filter: Company B + NO_PURCHASE_BILL   ->  L004 is INCLUDED

Company A's purchase must not remove L004 from Company B's no-purchase result.
This is the ONE place a company scope enters a purchase question, and it still
does not change the licence's global ``first_purchase_date``.

========================================================================
6. DEBIT / CREDIT / PROFIT & LOSS
========================================================================

Column mapping is read from `apps.license.domain.transaction_semantics`
(`ledger_column_for`) and is NOT restated here:

    PURCHASE -> CREDIT column   (acquires licence value)
    SALE     -> DEBIT  column   (consumes licence value)
    OPENING  -> CREDIT column

    PROFIT / LOSS (INR)  =  TOTAL CREDIT BILL (INR)  -  TOTAL DEBIT BILL (INR)

i.e. the sum of purchase-side bill amounts minus the sum of sale-side bill
amounts, both in INR (``amount_inr`` on the trade lines). ``> 0`` => PROFIT,
``< 0`` => LOSS, ``== 0`` => break-even. This is the LOCKED business rule;
`profit_loss` is derived from the two published sums by
`LicenseLedgerAccountingService.calculate_profit_loss`, so the two can never
disagree and the rule exists in exactly one expression.

(!) SIGN — RECORDED, NOT SILENTLY REINTERPRETED (!)
Because PURCHASE is the CREDIT column, ``credit_bill - debit_bill`` is
acquisition cost minus disposal proceeds. On the local production-shaped dataset
the sale bill exceeds the purchase bill for 154 of 186 traded licences, so the
majority report a NEGATIVE figure (LOSS) under this rule. The rule is implemented
exactly as specified; the observation is recorded in
MODULE_05_LICENSE_LEDGER_ACCOUNTING_CONSISTENCY_AUDIT.md so that reversing the
operand order later is a one-line change HERE and nowhere else.

========================================================================
7. POSITION IDENTITY
========================================================================

    opening_position + credit_bill - debit_bill == closing_position

holds in bounded AND unbounded mode (unbounded => ``opening_position == 0``, so it
collapses to ``credit - debit == balance``, the pre-existing identity).

No FIFO, weighted-average or other cost-attribution rule is invented. Historical
cost is CARRIED FORWARD as an opening position and disclosed; it is never
re-attributed to a period sale. A licence is one fungible pool of value and is
reported the way a ledger account is reported: opening, movement, closing.

========================================================================
8. TRADE POPULATIONS — NAMED ONCE, CHOSEN EXPLICITLY
========================================================================

  * `LEDGER_POPULATION` — every PURCHASE/SALE trade touching the licence,
    INCLUDING internal linked/mirror legs. What the ledger screens have always
    shown and what `CanonicalLedgerService` builds its running balance from.
  * `REALISED_MARGIN_POPULATION` — external trades only
    (``linked_trade__isnull=True``), the population `license_profit` defines a
    qualifying PURCHASE over, and therefore the population that decides
    ``first_purchase_date`` and "has a qualifying purchase bill".

They differ by 26 of 494 trades on the local dataset, so substituting one for the
other silently restates published figures. Which population the MONEY columns use
is a business decision, not a refactor — see the audit document.

========================================================================
9. CURRENCY
========================================================================

Every money figure this module returns is **INR** (sum of ``amount_inr``) — the
currency the `license_wise` / `company_wise` / `summary` grids and the Bill
columns are denominated in, on both licence families.

The ledger DETAIL screen additionally reports the licence's own value in CIF
**USD** for DFIA (``cif_fc``); that figure is built by `CanonicalLedgerService`,
which imports `ReportingPeriod` from here so the DATE rules are shared even
though the money column is not. USD and INR figures are never added and are not
expected to match — see `license_profit`'s module docstring.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date as date_type
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_date

from apps.core.constants import DEC_0
from apps.trade.models import LicenseTrade

logger = logging.getLogger(__name__)

__all__ = [
    "ReportingPeriod",
    "PurchaseBillMode",
    "LedgerFilterSpec",
    "LicenseLedgerAccountingService",
    "LEDGER_POPULATION",
    "REALISED_MARGIN_POPULATION",
    "DFIA_LICENSE_TYPE",
    "INCENTIVE_LICENSE_TYPE",
    "INCENTIVE_SUBTYPES",
    "INCENTIVE_LICENSE_TYPES",
    "ALL_LICENSE_TYPES",
    "family_of",
    "net_of",
    "profit_state_for",
    "license_index",
]

DFIA_LICENSE_TYPE = "DFIA"
INCENTIVE_LICENSE_TYPE = "INCENTIVE"
#: Rows of the SAME `IncentiveLicense` table — `license_type` is a column on it,
#: not a separate model.
INCENTIVE_SUBTYPES: Tuple[str, ...] = ("RODTEP", "ROSTL", "MEIS")
INCENTIVE_LICENSE_TYPES = frozenset({INCENTIVE_LICENSE_TYPE, *INCENTIVE_SUBTYPES})
ALL_LICENSE_TYPES = frozenset({"ALL", DFIA_LICENSE_TYPE, *INCENTIVE_LICENSE_TYPES})

#: Directions that carry licence value. The COMMISSION family is deliberately
#: absent — non-balance-affecting by approved semantics (see
#: `apps.license.domain.transaction_semantics`).
LEDGER_DIRECTIONS: Tuple[str, str] = (LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_SALE)

#: See section 8. Empty dict = no exclusion.
LEDGER_POPULATION: Dict[str, Any] = {}
#: External trades only — the population `license_profit` defines a qualifying
#: purchase over. Read from there rather than restated, so "qualifying purchase"
#: has one definition system-wide.
REALISED_MARGIN_POPULATION: Dict[str, Any] = {"trade__linked_trade__isnull": True}

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


# ---------------------------------------------------------------------------
# THE REPORTING PERIOD
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReportingPeriod:
    """
    An INCLUSIVE ``[start, end]`` window; either bound may be ``None`` for an
    open end.

    Frozen and hashable so it can be threaded down a call chain (or used as a
    cache key) with no risk of a consumer mutating the period mid-report.

    ONE window drives BOTH accounting decisions (sections 2 and 3): licence
    eligibility compares ``first_purchase_date`` against it, period activity
    compares ``transaction_date`` against it. Two decisions, two different
    inputs, one window — which is exactly why the window is parsed once, here,
    rather than re-read from the query string by each endpoint.
    """

    start: Optional[date_type] = None
    end: Optional[date_type] = None

    # -- construction -------------------------------------------------------

    @classmethod
    def unbounded(cls) -> "ReportingPeriod":
        """The no-period-selected window: every licence, every transaction."""
        return cls(start=None, end=None)

    @classmethod
    def from_query_params(cls, query_params) -> "ReportingPeriod":
        """
        Read the window from a dict-like request query string.

        The wire parameter names are the pre-existing
        ``purchase_date_from`` / ``purchase_date_to`` — kept verbatim so no
        client, saved filter, bookmark or export URL breaks.

        Malformed or blank values degrade to ``None`` (an open bound) rather than
        raising: a bad date in a URL must not 500 a financial screen.
        """
        return cls(
            start=parse_iso_date(text_param(query_params, "purchase_date_from")),
            end=parse_iso_date(text_param(query_params, "purchase_date_to")),
        )

    # -- shape --------------------------------------------------------------

    @property
    def is_bounded(self) -> bool:
        """True when at least one bound is set, i.e. a period IS selected."""
        return self.start is not None or self.end is not None

    # -- eligibility (section 2) -------------------------------------------

    def includes_first_purchase(self, first_purchase_date: Optional[date_type]) -> bool:
        """
        Is a licence with this ``first_purchase_date`` ELIGIBLE for the window?

        ``start <= first_purchase_date <= end``, both bounds inclusive, with an
        unset bound treated as open.

        ``None`` — a licence with no qualifying purchase, hence no acquisition
        date — is eligible ONLY for an unbounded window. With any bound set there
        is no date to compare, so it is excluded rather than admitted on a guess.
        The ``NO_PURCHASE_BILL`` override on `LedgerFilterSpec` is the supported
        way to ask for exactly that population (section 5).
        """
        if not self.is_bounded:
            return True
        if first_purchase_date is None:
            return False
        if self.start is not None and first_purchase_date < self.start:
            return False
        if self.end is not None and first_purchase_date > self.end:
            return False
        return True

    # -- period activity (section 3) ---------------------------------------

    def includes_transaction(self, txn_date: Optional[date_type]) -> bool:
        """
        Is ``txn_date`` inside the window? Both bounds inclusive.

        A ``None`` date (``LicenseTrade.invoice_date`` is nullable) is inside an
        UNBOUNDED window and outside every bounded one — matching what SQL
        already does, since ``invoice_date__gte``/``__lte`` never match NULL. An
        undated trade cannot be assigned to a month, and guessing one would
        fabricate period activity.
        """
        if txn_date is None:
            return not self.is_bounded
        if self.start is not None and txn_date < self.start:
            return False
        if self.end is not None and txn_date > self.end:
            return False
        return True

    def is_before_period(self, txn_date: Optional[date_type]) -> bool:
        """
        Is ``txn_date`` strictly historical — part of the OPENING position rather
        than period activity?

        Always False when there is no ``start``: with no lower bound there is no
        line for a transaction to be before, so every dated row is activity and
        the opening position is zero.
        """
        if txn_date is None or self.start is None:
            return False
        return txn_date < self.start

    def is_after_period(self, txn_date: Optional[date_type]) -> bool:
        """Is ``txn_date`` past ``end`` — excluded from the report entirely?"""
        if txn_date is None or self.end is None:
            return False
        return txn_date > self.end

    # -- ORM helpers --------------------------------------------------------

    def trade_date_filters(self, prefix: str = "") -> Dict[str, Any]:
        """
        ``{'<prefix>invoice_date__gte': start, '<prefix>invoice_date__lte': end}``
        for the bounds that are set — empty dict when unbounded.

        ``prefix`` lets the same rule be applied from a trade queryset (``''``) or
        a trade-LINE queryset (``'trade__'``) without either caller re-typing the
        lookup names.

        /!\\ Valid ONLY for TRANSACTION-period filtering (section 3). It must never
        be used to find a licence's purchases: pushing the window into the query
        that DERIVES ``first_purchase_date`` is the classic form of this bug,
        because it returns the earliest purchase *in the window* instead of the
        licence's real acquisition date.
        """
        filters: Dict[str, Any] = {}
        if self.start is not None:
            filters[f"{prefix}invoice_date__gte"] = self.start
        if self.end is not None:
            filters[f"{prefix}invoice_date__lte"] = self.end
        return filters

    def trade_date_q(self, prefix: str = "") -> Q:
        """`trade_date_filters` as a ``Q`` (empty ``Q()`` when unbounded)."""
        return Q(**self.trade_date_filters(prefix))

    def __str__(self) -> str:  # pragma: no cover — diagnostics only
        return f"[{self.start or '-inf'} .. {self.end or '+inf'}]"


# ---------------------------------------------------------------------------
# PURCHASE BILL MODE (section 5)
# ---------------------------------------------------------------------------

class PurchaseBillMode:
    """
    The three states of the Purchase Bill filter, as sent on the wire.

    A plain constants class rather than an ``Enum`` to match how every other
    ledger filter vocabulary in this codebase is expressed (``license_type``,
    ``purchase_status``, ``norm``), so the parsing path stays uniform.
    """

    ALL = "ALL"
    WITH = "WITH_PURCHASE_BILL"
    NONE = "NO_PURCHASE_BILL"

    CHOICES: Tuple[str, str, str] = (ALL, WITH, NONE)

    #: Accepted wire spellings -> canonical value. The bare ``WITH``/``NO`` forms
    #: are honoured alongside the full names so a hand-written URL or an older
    #: client keeps working.
    ALIASES: Dict[str, str] = {
        "": ALL,
        "ALL": ALL,
        "ANY": ALL,
        "WITH": WITH,
        "WITH_PURCHASE_BILL": WITH,
        "HAS_PURCHASE_BILL": WITH,
        "NO": NONE,
        "NONE": NONE,
        "NO_PURCHASE_BILL": NONE,
        "WITHOUT_PURCHASE_BILL": NONE,
    }

    @classmethod
    def normalize(cls, value: Any) -> str:
        """Any accepted spelling -> canonical value; anything unknown -> ``ALL``."""
        key = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        return cls.ALIASES.get(key, cls.ALL)


# ---------------------------------------------------------------------------
# THE FILTER SPEC — every ledger filter parsed exactly once
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LedgerFilterSpec:
    """
    The parsed, validated License Ledger filter set — the ONE place a ledger query
    string is interpreted.

    Before this existed, `build_license_queryset`, `get_ledger_summary`,
    `get_license_wise_trades` and `get_company_wise_trades` each re-read the raw
    params and each disagreed about at least one of them (the company filter's
    role semantics, whether ``search`` applied at all, whether the dates applied
    at all). Parsing once removes the class of bug rather than its instances.

    Every field is already the right Python type; ``None``/``''`` means "not
    filtering on this". Malformed input degrades to "not filtering" and never
    raises — a hand-edited URL must not 500 a financial screen.
    """

    license_type: str = "ALL"
    period: ReportingPeriod = field(default_factory=ReportingPeriod.unbounded)
    purchase_bill_mode: str = PurchaseBillMode.ALL
    company_id: Optional[int] = None
    exporter_id: Optional[int] = None
    min_balance: Optional[Decimal] = None
    norm: str = ""
    purchase_status: str = ""
    search: str = ""
    active_only: bool = True
    ordering: str = "-license_date"

    @classmethod
    def from_query_params(cls, query_params) -> "LedgerFilterSpec":
        """Parse a dict-like request query string into a spec."""
        license_type = text_param(query_params, "license_type", "ALL").upper()
        return cls(
            license_type=license_type if license_type in ALL_LICENSE_TYPES else "ALL",
            period=ReportingPeriod.from_query_params(query_params),
            purchase_bill_mode=cls._purchase_bill_mode(query_params),
            company_id=parse_int(text_param(query_params, "company")),
            exporter_id=parse_int(text_param(query_params, "exporter")),
            min_balance=parse_decimal(text_param(query_params, "min_balance")),
            norm=text_param(query_params, "norm"),
            purchase_status=text_param(query_params, "purchase_status"),
            search=text_param(query_params, "search"),
            active_only=bool_param(query_params, "active_only", default=True),
            ordering=text_param(query_params, "ordering", "-license_date") or "-license_date",
        )

    @staticmethod
    def _purchase_bill_mode(query_params) -> str:
        """
        Resolve the Purchase Bill mode from the ``purchase_bill`` param, falling
        back to the legacy boolean ``no_purchases``.

        The legacy param asked exactly the new question ("licences with no
        purchase"), so it is an ALIAS rather than a second filter — one behaviour,
        one implementation. An explicit ``purchase_bill`` wins when both appear.
        """
        explicit = text_param(query_params, "purchase_bill")
        if explicit:
            return PurchaseBillMode.normalize(explicit)
        if bool_param(query_params, "no_purchases"):
            return PurchaseBillMode.NONE
        return PurchaseBillMode.ALL

    # -- derived shape ------------------------------------------------------

    @property
    def is_no_purchase_bill_mode(self) -> bool:
        """
        True when the NO_PURCHASE_BILL override is active, i.e. when Purchase Date
        Range eligibility must be BYPASSED (section 5).
        """
        return self.purchase_bill_mode == PurchaseBillMode.NONE

    @property
    def applies_date_eligibility(self) -> bool:
        """
        Should the Purchase Date Range narrow the licence population?

        Only when a window is actually selected AND the NO_PURCHASE_BILL override
        is not active. This single property is what guarantees the override cannot
        be silently re-narrowed by a date range further down the chain.
        """
        return self.period.is_bounded and not self.is_no_purchase_bill_mode

    @property
    def search_terms(self) -> List[str]:
        """
        ``search`` split on commas.

        One term  -> substring match on licence number OR exporter name.
        Several   -> EXACT licence-number match on each (a pasted list of
                     licences), never a substring, so "0311045100,0311045787"
                     cannot pull in a third licence that merely contains one of
                     them.
        """
        return [t.strip() for t in self.search.split(",") if t.strip()]

    @property
    def drops_incentive_licenses(self) -> bool:
        """
        True when a DFIA-only filter is active, so the whole Incentive family must
        be dropped rather than left unfiltered.

        ``norm`` (a SION export-item concept) and ``purchase_status`` are columns
        that exist ONLY on `LicenseDetailsModel`. Leaving Incentive rows in while
        a DFIA-only filter is active would present them as having passed a filter
        that was never applied to them.
        """
        return bool(self.norm or self.purchase_status)


# ---------------------------------------------------------------------------
# Shared parsers — the only implementations of these conversions
# ---------------------------------------------------------------------------

def text_param(query_params, name: str, default: str = "") -> str:
    value = query_params.get(name, default) if query_params is not None else default
    if value is None:
        return default
    return str(value).strip()


def parse_iso_date(value) -> Optional[date_type]:
    if value in (None, ""):
        return None
    try:
        return parse_date(str(value).strip())
    except (ValueError, TypeError):
        return None


def parse_int(value) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_decimal(value) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def bool_param(query_params, name: str, *, default: bool = False) -> bool:
    value = query_params.get(name) if query_params is not None else None
    if value is None:
        return default
    return str(value).strip().lower() in TRUE_VALUES


def clean_ids(ids: Iterable[int]) -> List[int]:
    """De-duplicated, falsy-free id list, input order preserved."""
    return [i for i in dict.fromkeys(ids or []) if i]


def family_of(license_type: Optional[str]) -> str:
    """
    Collapse a wire licence type to the family the two id spaces are keyed by.

    ``'DFIA'`` stays DFIA; ``'RODTEP'``/``'ROSTL'``/``'MEIS'``/``'INCENTIVE'`` all
    map to INCENTIVE, because they are all rows of the SAME `IncentiveLicense`
    table. Keys built from the raw wire value would miss.
    """
    return DFIA_LICENSE_TYPE if license_type == DFIA_LICENSE_TYPE else INCENTIVE_LICENSE_TYPE


def net_of(credit: Decimal, debit: Decimal) -> Decimal:
    """
    THE net operation: ``credit - debit``.

    A one-line function on purpose. The opening position, the period movement, the
    closing position and the Profit / Loss figure are all this same subtraction
    (sections 6 and 7), so it is written once and read everywhere instead of being
    re-typed at each site where a sign could be flipped.
    """
    return (credit or DEC_0) - (debit or DEC_0)


def profit_state_for(profit_loss: Optional[Decimal]) -> str:
    """
    ``'PROFIT'`` | ``'LOSS'`` | ``'NONE'`` for a Profit / Loss figure.

    Decided in the BACKEND so no client ever branches on the sign of a number, and
    so Web, PDF and Excel cannot disagree about a colour.

    ``'NONE'`` is the exact-zero case — BREAK-EVEN, a real financial statement,
    rendered as "NO PROFIT / NO LOSS". The existing wire vocabulary is kept
    (``NONE``, not ``BREAK_EVEN``) because the frontend's `ProfitState` union and
    its `PROFIT_STATE_PRESENTATION` map already carry it; renaming would be a
    breaking contract change for a synonym.
    """
    if profit_loss is None:  # pragma: no cover — defensive
        return "NONE"
    if profit_loss > DEC_0:
        return "PROFIT"
    if profit_loss < DEC_0:
        return "LOSS"
    return "NONE"


def license_index(
    dfia_ids: Iterable[int] = (),
    incentive_ids: Iterable[int] = (),
) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """
    ``{(license_family, license_id): {'license_number', 'license_date',
    'license_type'}}`` — the LABELS a grid prints beside the canonical money, in
    ONE query per licence family.

    Keyed by ``(family, id)`` and never by id alone: `LicenseDetailsModel.id` and
    `IncentiveLicense.id` are independent sequences, so a flat map would let a
    DFIA row inherit an Incentive licence's number.

    ``license_type`` is the licence's OWN value for the incentive family (RODTEP /
    ROSTL / MEIS), not the generic ``"INCENTIVE"`` bucket the key uses, because
    that is the label the grids have always shown.
    """
    from apps.license.models import IncentiveLicense, LicenseDetailsModel

    index: Dict[Tuple[str, int], Dict[str, Any]] = {}

    dfia = clean_ids(dfia_ids)
    if dfia:
        for lid, number, lic_date in LicenseDetailsModel.objects.filter(
            id__in=dfia
        ).values_list("id", "license_number", "license_date"):
            index[(DFIA_LICENSE_TYPE, lid)] = {
                "license_number": number or "",
                "license_date": lic_date,
                "license_type": DFIA_LICENSE_TYPE,
            }

    incentive = clean_ids(incentive_ids)
    if incentive:
        for lid, number, lic_date, lic_type in IncentiveLicense.objects.filter(
            id__in=incentive
        ).values_list("id", "license_number", "license_date", "license_type"):
            index[(INCENTIVE_LICENSE_TYPE, lid)] = {
                "license_number": number or "",
                "license_date": lic_date,
                "license_type": lic_type or INCENTIVE_LICENSE_TYPE,
            }

    return index


# ---------------------------------------------------------------------------
# THE SERVICE
# ---------------------------------------------------------------------------

class LicenseLedgerAccountingService:
    """
    The single implementation of License Ledger first-purchase, eligibility,
    purchase-bill, period-selection, opening-treatment and profit/loss logic.

    Stateless — every method is a `staticmethod`, so there is no instance that
    could be configured differently in two places.
    """

    # ==================================================================
    # 1. GLOBAL FIRST PURCHASE DATE (delegated — never re-derived)
    # ==================================================================

    @staticmethod
    def first_purchase_dates(
        dfia_ids: Iterable[int] = (),
        incentive_ids: Iterable[int] = (),
    ) -> Tuple[Dict[int, date_type], Dict[int, date_type]]:
        """
        ``({dfia_id: first_purchase_date}, {incentive_id: first_purchase_date})``
        in at most ONE grouped query per licence family.

        GLOBAL by construction: both maps come straight from `license_profit`,
        whose queries carry no company predicate at all, so a Company filter
        CANNOT influence the result (section 1). There is deliberately no
        ``company_id`` parameter on this method — adding one is the shape of the
        bug it prevents.

        Never date-windowed either: pushing the report period into the query that
        FINDS the purchases would return "earliest purchase in the window" instead
        of the licence's acquisition date.

        Licences with no qualifying purchase — and licences whose every qualifying
        purchase has a NULL invoice_date — are ABSENT from the maps, never mapped
        to ``None``. Test membership for "has no acquisition date".
        """
        from apps.license.services.license_profit import (
            first_purchase_date_by_license,
            incentive_first_purchase_date_by_license,
        )

        dfia = clean_ids(dfia_ids)
        incentive = clean_ids(incentive_ids)
        return (
            first_purchase_date_by_license(dfia) if dfia else {},
            incentive_first_purchase_date_by_license(incentive) if incentive else {},
        )

    @staticmethod
    def get_global_first_purchase_date(
        license_id: int, license_type: str
    ) -> Optional[date_type]:
        """
        One licence's GLOBAL acquisition date, or ``None`` when it has none.

        Named "global" so the contract cannot be misread at a call site: this is
        the licence's date across ALL companies, and no company scope changes it.

        /!\\ `LicenseDetailsModel.id` and `IncentiveLicense.id` are INDEPENDENT
        sequences, so ``license_type`` is REQUIRED — the wrong family would
        silently return an unrelated licence's date.
        """
        if not license_id:
            return None
        is_dfia = family_of(license_type) == DFIA_LICENSE_TYPE
        dfia, incentive = LicenseLedgerAccountingService.first_purchase_dates(
            dfia_ids=[license_id] if is_dfia else (),
            incentive_ids=() if is_dfia else [license_id],
        )
        return dfia.get(license_id) if is_dfia else incentive.get(license_id)

    # ==================================================================
    # 2. PURCHASE DATE RANGE ELIGIBILITY  (start <= fpd <= end)
    # ==================================================================

    @staticmethod
    def is_license_in_purchase_date_range(
        first_purchase_date: Optional[date_type],
        period: ReportingPeriod,
    ) -> bool:
        """
        Does this licence's GLOBAL first purchase fall INSIDE the window
        (section 2)?

        Thin, deliberately: the boundary arithmetic lives on `ReportingPeriod` so
        it is expressed once and unit-testable without a database. This wrapper
        exists because "is the licence in range" is the vocabulary the endpoints
        and the audit document use.
        """
        return period.includes_first_purchase(first_purchase_date)

    @staticmethod
    def eligible_ids(
        first_purchase_dates: Dict[int, date_type],
        period: ReportingPeriod,
    ) -> List[int]:
        """Ids from a ``{license_id: first_purchase_date}`` map that are eligible."""
        return [
            lid
            for lid, first_date in first_purchase_dates.items()
            if period.includes_first_purchase(first_date)
        ]

    @staticmethod
    def apply_license_eligibility(dfia_qs, incentive_qs, spec: LedgerFilterSpec):
        """
        Narrow both licence querysets to the ELIGIBLE licence set — step 2 of the
        fixed order of operations (section 4), and the ONLY place that step
        happens.

        Sequence, in this order and no other:

          1. Purchase Bill mode (section 5). ``NO_PURCHASE_BILL`` selects the
             true-no-purchase population and RETURNS — the date range is
             deliberately never reached, which is what makes the override an
             override. ``WITH_PURCHASE_BILL`` narrows to licences that have one
             and falls through.
          2. Purchase Date Range (section 2), applied only when
             `spec.applies_date_eligibility`.

        The Company filter is NOT applied here. It belongs to the step AFTER
        eligibility, inside `build_period_activity`, because it must not be able
        to influence a first-purchase decision (sections 1 and 4). The single
        exception is the company-scoped no-purchase-bill question in step 1, which
        is company-scoped by definition and still reads no dates.

        Returns ``(dfia_qs, incentive_qs)``. Cost: at most one grouped aggregate
        or one existence query per licence family, over the licences that survived
        the cheap column filters — never one query per licence.
        """
        svc = LicenseLedgerAccountingService

        if spec.is_no_purchase_bill_mode:
            dfia_no, incentive_no = svc.get_no_purchase_bill_licenses(
                dfia_ids=dfia_qs.values_list("id", flat=True),
                incentive_ids=incentive_qs.values_list("id", flat=True),
                company_id=spec.company_id,
            )
            return dfia_qs.filter(id__in=dfia_no), incentive_qs.filter(id__in=incentive_no)

        if spec.purchase_bill_mode == PurchaseBillMode.WITH:
            dfia_with, incentive_with = svc.get_licenses_with_purchase_bill(
                dfia_ids=dfia_qs.values_list("id", flat=True),
                incentive_ids=incentive_qs.values_list("id", flat=True),
                company_id=spec.company_id,
            )
            dfia_qs = dfia_qs.filter(id__in=dfia_with)
            incentive_qs = incentive_qs.filter(id__in=incentive_with)

        if not spec.applies_date_eligibility:
            return dfia_qs, incentive_qs

        dfia_map, incentive_map = svc.first_purchase_dates(
            dfia_ids=dfia_qs.values_list("id", flat=True),
            incentive_ids=incentive_qs.values_list("id", flat=True),
        )
        return (
            dfia_qs.filter(id__in=svc.eligible_ids(dfia_map, spec.period)),
            incentive_qs.filter(id__in=svc.eligible_ids(incentive_map, spec.period)),
        )

    # ==================================================================
    # 3. PURCHASE BILL EXISTENCE (section 5)
    # ==================================================================

    @staticmethod
    def get_licenses_with_purchase_bill(
        dfia_ids: Iterable[int] = (),
        incentive_ids: Iterable[int] = (),
        company_id: Optional[int] = None,
    ) -> Tuple[Set[int], Set[int]]:
        """
        ``(dfia_ids, incentive_ids)`` that HAVE at least one qualifying purchase
        bill — ONE existence query per licence family.

        "Qualifying" is `REALISED_MARGIN_POPULATION`, i.e. exactly the population
        `license_profit` derives ``first_purchase_date`` from. Reading the same
        definition guarantees the two answers cannot contradict: a licence has a
        qualifying purchase bill IF AND ONLY IF it has a ``first_purchase_date``.

        ``company_id`` scopes the question to that company as the BUYER
        (``to_company``) of the purchase — the same role the grids group a
        purchase under (see `_own_and_party`). Never "either side of the trade": a
        company that merely SOLD the licence has not purchased it.

        NO DATE FILTER, by design. "Has a purchase bill" is a question about
        existence over the licence's whole life, not about a month (section 5).
        """
        from apps.license.services.license_profit import PURCHASE_LINE_FILTERS
        from apps.trade.models import IncentiveTradeLine, LicenseTradeLine

        buyer_scope = {"trade__to_company_id": company_id} if company_id else {}

        dfia = clean_ids(dfia_ids)
        incentive = clean_ids(incentive_ids)
        dfia_with: Set[int] = set()
        incentive_with: Set[int] = set()

        if dfia:
            dfia_with = set(
                LicenseTradeLine.objects.filter(
                    sr_number__license_id__in=dfia, **PURCHASE_LINE_FILTERS, **buyer_scope
                )
                .values_list("sr_number__license_id", flat=True)
                .distinct()
            )
        if incentive:
            incentive_with = set(
                IncentiveTradeLine.objects.filter(
                    incentive_license_id__in=incentive, **PURCHASE_LINE_FILTERS, **buyer_scope
                )
                .values_list("incentive_license_id", flat=True)
                .distinct()
            )
        return dfia_with, incentive_with

    @staticmethod
    def get_no_purchase_bill_licenses(
        dfia_ids: Iterable[int] = (),
        incentive_ids: Iterable[int] = (),
        company_id: Optional[int] = None,
    ) -> Tuple[List[int], List[int]]:
        """
        The complement of `get_licenses_with_purchase_bill`: the licences with NO
        qualifying purchase bill (section 5).

        Derived by SET DIFFERENCE against the candidate ids rather than by a
        second, negated query, so "has a purchase bill" and "has no purchase bill"
        are provably exact opposites over the same candidate set — a separate
        ``exclude()`` could drift from the positive query's join semantics.

        With ``company_id`` set this is the company-scoped question: licences this
        company has not purchased, INCLUDING licences another company did purchase
        (the mandated L004 case).
        """
        dfia = clean_ids(dfia_ids)
        incentive = clean_ids(incentive_ids)
        dfia_with, incentive_with = (
            LicenseLedgerAccountingService.get_licenses_with_purchase_bill(
                dfia_ids=dfia, incentive_ids=incentive, company_id=company_id
            )
        )
        return (
            [lid for lid in dfia if lid not in dfia_with],
            [lid for lid in incentive if lid not in incentive_with],
        )

    # ==================================================================
    # 4. PERIOD ACTIVITY / OPENING / DEBIT / CREDIT / PROFIT & LOSS
    # ==================================================================

    @staticmethod
    def build_period_activity(
        dfia_ids: Iterable[int] = (),
        incentive_ids: Iterable[int] = (),
        period: Optional[ReportingPeriod] = None,
        *,
        company_id: Optional[int] = None,
        population: Optional[Dict[str, Any]] = None,
    ) -> Dict[Tuple[str, int], Dict[str, Any]]:
        """
        THE canonical per-licence accounting result for a reporting period — steps
        3 to 5 of the order of operations (section 4).

        Every licence id passed in gets an entry, WHETHER OR NOT it has activity in
        the window. Eligibility was already decided by `apply_license_eligibility`;
        an eligible licence must not then vanish for having a quiet month. Callers
        that want only the licences worth printing filter on
        ``has_period_activity`` — the service does not make that presentation
        decision for them.

        Args:
            dfia_ids / incentive_ids: the ELIGIBLE licence ids, per family.
            period: the window; ``None`` => unbounded (whole history is activity,
                opening position zero).
            company_id: optional single-company scope, applied with the SAME role
                semantics the grids group by — buyer of a purchase, seller of a
                sale (see `_own_and_party`). Applied HERE, after eligibility.
            population: `LEDGER_POPULATION` (default) or
                `REALISED_MARGIN_POPULATION`. Never a hand-written filter dict.

        Returns:
            ``{(license_family, license_id): entry}`` where each entry is::

                {
                  'license_id', 'license_type',
                  'companies': {company_id: {
                        'company_id', 'company_name',
                        'purchases': [row, ...],   # period rows only
                        'sales':     [row, ...],   # period rows only
                        'purchase_total',          # this company's CREDIT BILL
                        'sale_total',              # this company's DEBIT  BILL
                        'profit_loss',             # credit_bill - debit_bill
                  }},
                  'opening_position': Decimal,   # pre-period credit - debit
                  'credit_bill':      Decimal,   # period PURCHASE bill (INR)
                  'debit_bill':       Decimal,   # period SALE     bill (INR)
                  'profit_loss':      Decimal,   # credit_bill - debit_bill (s.6)
                  'profit_state':     str,       # PROFIT | LOSS | NONE
                  'closing_position': Decimal,   # opening + credit - debit (s.7)
                  'has_period_activity': bool,
                  'excluded_after_period': int,  # rows dropped for being > end
                }

            Every money value is a raw, unquantized ``Decimal`` in **INR**, so a
            caller building grand totals sums raw Decimals and quantizes ONCE.

        Cost: ONE grouped query per licence family — grouped in SQL by
        ``(licence, trade, direction, both companies, invoice_date)``, so no trade
        or line is ever fetched per-licence in Python. Empty id lists cost zero
        queries.
        """
        period = period or ReportingPeriod.unbounded()
        population = LEDGER_POPULATION if population is None else population

        families = (
            (DFIA_LICENSE_TYPE, clean_ids(dfia_ids)),
            (INCENTIVE_LICENSE_TYPE, clean_ids(incentive_ids)),
        )

        entries: Dict[Tuple[str, int], Dict[str, Any]] = {
            (family, lid): _empty_activity_entry(family, lid)
            for family, ids in families
            for lid in ids
        }

        for family, ids in families:
            if not ids:
                continue
            for row in _period_activity_rows(family, ids, population):
                entry = entries.get((family, row["license_id"]))
                if entry is None:  # pragma: no cover — ids came from the filter
                    continue
                _accumulate_activity_row(entry, row, period, company_id)

        for entry in entries.values():
            _finalise_activity_entry(entry)
        return entries

    @staticmethod
    def get_period_transactions(
        license_id: int,
        license_type: str,
        period: Optional[ReportingPeriod] = None,
        *,
        company_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        One licence's PERIOD transactions, chronologically — flattened out of
        `build_period_activity` so a single-licence caller need not walk the
        company grouping itself.
        """
        entry = LicenseLedgerAccountingService._single_license_entry(
            license_id, license_type, period, company_id=company_id
        )
        if not entry:
            return []
        rows: List[Dict[str, Any]] = []
        for company in entry["companies"].values():
            rows.extend(company["purchases"])
            rows.extend(company["sales"])
        rows.sort(key=lambda r: (r["date"] or date_type.min, r["trade_id"]))
        return rows

    @staticmethod
    def get_opening_position(
        license_id: int,
        license_type: str,
        period: Optional[ReportingPeriod] = None,
        *,
        company_id: Optional[int] = None,
    ) -> Decimal:
        """
        The licence's carried-forward position (INR) at ``period.start``:
        pre-period purchase bills minus pre-period sale bills.

        ``DEC_0`` when the window has no ``start`` — there is no line for a
        transaction to be historical to.
        """
        entry = LicenseLedgerAccountingService._single_license_entry(
            license_id, license_type, period, company_id=company_id
        )
        return entry["opening_position"] if entry else DEC_0

    @staticmethod
    def calculate_profit_loss(credit_bill: Decimal, debit_bill: Decimal) -> Decimal:
        """
        THE Profit / Loss rule (section 6): ``credit_bill - debit_bill``, in INR.

        Every Profit / Loss number in the module — per company, per licence, per
        grand total, and the ledger detail's summary card — comes through this one
        function. Changing the rule means changing this line, and only this line.
        """
        return net_of(credit_bill, debit_bill)

    @staticmethod
    def calculate_period_profit_loss(
        dfia_ids: Iterable[int] = (),
        incentive_ids: Iterable[int] = (),
        period: Optional[ReportingPeriod] = None,
        *,
        company_id: Optional[int] = None,
        population: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Grand totals across many licences for one window, in **INR**::

            {'credit_bill', 'debit_bill', 'profit_loss', 'profit_state',
             'opening_position', 'closing_position', 'license_count',
             'licenses_with_activity'}

        Summed from the raw unquantized Decimals of `build_period_activity`, so
        rounding happens ONCE at the presentation layer and never compounds
        per-row.
        """
        activity = LicenseLedgerAccountingService.build_period_activity(
            dfia_ids=dfia_ids,
            incentive_ids=incentive_ids,
            period=period,
            company_id=company_id,
            population=population,
        )
        credit_bill = DEC_0
        debit_bill = DEC_0
        opening_position = DEC_0
        with_activity = 0
        for entry in activity.values():
            credit_bill += entry["credit_bill"]
            debit_bill += entry["debit_bill"]
            opening_position += entry["opening_position"]
            with_activity += 1 if entry["has_period_activity"] else 0

        profit_loss = LicenseLedgerAccountingService.calculate_profit_loss(
            credit_bill, debit_bill
        )
        return {
            "credit_bill": credit_bill,
            "debit_bill": debit_bill,
            "profit_loss": profit_loss,
            "profit_state": profit_state_for(profit_loss),
            "opening_position": opening_position,
            "closing_position": opening_position + net_of(credit_bill, debit_bill),
            "license_count": len(activity),
            "licenses_with_activity": with_activity,
        }

    # ==================================================================
    # 5. THE LEDGER DETAIL DATASET (delegation, not a second builder)
    # ==================================================================

    @staticmethod
    def build_ledger_dataset(
        license_id: int,
        license_type: str = DFIA_LICENSE_TYPE,
        period: Optional[ReportingPeriod] = None,
    ) -> Dict[str, Any]:
        """
        The canonical single-licence ledger dataset — the SAME object the API, PDF
        and Excel consume.

        A thin delegation to
        `CanonicalLedgerService.build_canonical_ledger_dataset` on purpose: that
        service owns the licence's own-currency (CIF USD for DFIA) running balance
        and the row display rule, and it takes its DATE and PROFIT rules from this
        module. Exposing it here gives every consumer one import for the whole
        canonical surface without creating a second dataset builder to keep in
        step.
        """
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService

        return CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=license_id,
            license_type=license_type,
            period=period,
        )

    # -- internal ----------------------------------------------------------

    @staticmethod
    def _single_license_entry(
        license_id: int,
        license_type: str,
        period: Optional[ReportingPeriod],
        *,
        company_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        One licence's activity entry, or None — shared by the single-licence
        accessors above so they cannot diverge in how they key the result.
        """
        family = family_of(license_type)
        is_dfia = family == DFIA_LICENSE_TYPE
        return LicenseLedgerAccountingService.build_period_activity(
            dfia_ids=[license_id] if is_dfia else (),
            incentive_ids=() if is_dfia else [license_id],
            period=period,
            company_id=company_id,
        ).get((family, license_id))


# ---------------------------------------------------------------------------
# Internal: the one SQL shape, and the one Python fold over it
# ---------------------------------------------------------------------------

def _empty_activity_entry(license_type: str, license_id: int) -> Dict[str, Any]:
    return {
        "license_id": license_id,
        "license_type": license_type,
        "companies": {},
        "opening_position": DEC_0,
        "credit_bill": DEC_0,
        "debit_bill": DEC_0,
        "profit_loss": DEC_0,
        "profit_state": "NONE",
        "closing_position": DEC_0,
        "has_period_activity": False,
        "excluded_after_period": 0,
    }


def _period_activity_rows(license_family: str, license_ids: List[int], population: Dict[str, Any]):
    """
    ONE grouped query yielding one row per ``(licence, trade)`` pair that touches
    ``license_ids``, carrying that trade's INR bill amount FOR THAT LICENCE.

    Grouping in SQL rather than iterating trades in Python is what keeps this
    N+1-free: a trade spanning several licences contributes a separate row per
    licence, each already summed over only its own lines.

    The two families are reached by their own relation — DFIA through
    ``LicenseTradeLine.sr_number__license_id``, incentive through
    ``IncentiveTradeLine.incentive_license_id`` — because they share no join path
    (see `license_profit`'s SCOPE section). The SELECTED COLUMNS and the aggregate
    are identical, so the Python fold below is shared.

    Deliberately NOT date-filtered: the fold needs PRE-period rows to build the
    opening position, so the window is applied in Python, once, by
    `ReportingPeriod`. Filtering here would reintroduce the defect this module
    removes.
    """
    if license_family == DFIA_LICENSE_TYPE:
        from apps.trade.models import LicenseTradeLine

        queryset = LicenseTradeLine.objects.filter(sr_number__license_id__in=license_ids)
        license_field = "sr_number__license_id"
    else:
        from apps.trade.models import IncentiveTradeLine

        queryset = IncentiveTradeLine.objects.filter(incentive_license_id__in=license_ids)
        license_field = "incentive_license_id"

    rows = (
        queryset.filter(trade__direction__in=LEDGER_DIRECTIONS, **population)
        .values(
            license_field,
            "trade_id",
            "trade__direction",
            "trade__invoice_date",
            "trade__from_company_id",
            "trade__from_company__name",
            "trade__to_company_id",
            "trade__to_company__name",
        )
        .annotate(
            bill_amount=Coalesce(Sum("amount_inr"), Value(DEC_0), output_field=DecimalField())
        )
        .order_by(license_field, "trade__invoice_date", "trade_id")
    )
    for row in rows:
        yield {
            "license_id": row[license_field],
            "trade_id": row["trade_id"],
            "direction": row["trade__direction"],
            "date": row["trade__invoice_date"],
            "from_company_id": row["trade__from_company_id"],
            "from_company_name": row["trade__from_company__name"],
            "to_company_id": row["trade__to_company_id"],
            "to_company_name": row["trade__to_company__name"],
            "bill_amount": row["bill_amount"] or DEC_0,
        }


#: Which end of a trade is OUR company and which is the COUNTERPARTY, per
#: direction. IDENTICAL to `canonical_ledger_service._TRADE_DIRECTION_SIDES` — a
#: PURCHASE is booked against the BUYER (``to_company``), a SALE against the
#: SELLER (``from_company``) — so the grids and the ledger detail group the same
#: trade under the same company.
_SIDES: Dict[str, Tuple[str, str]] = {
    LicenseTrade.DIR_PURCHASE: ("to", "from"),
    LicenseTrade.DIR_SALE: ("from", "to"),
}


def _own_and_party(row: Dict[str, Any]):
    """
    ``(own_id, own_name, party_id, party_name)`` for one activity row.

    The grids GROUP BY the ``own`` side, so a ``company_id`` scope must match on
    ``own`` too. Filtering on "either side of the trade" pulls in every
    counterparty and makes an unrelated company's licences appear under the
    selected one — a real, diagnosed defect (NEELKANTH IMPEX / LABDHI GLOBAL LLP
    surfacing under a LABDHI MERCANTILE LLP filter). The role-scoped rule below is
    the fix, applied here ONCE for every endpoint.
    """
    own_side, party_side = _SIDES[row["direction"]]
    return (
        row[f"{own_side}_company_id"],
        row[f"{own_side}_company_name"],
        row[f"{party_side}_company_id"],
        row[f"{party_side}_company_name"],
    )


def _accumulate_activity_row(
    entry: Dict[str, Any],
    row: Dict[str, Any],
    period: ReportingPeriod,
    company_id: Optional[int],
) -> None:
    """
    Fold ONE ``(licence, trade)`` row into its licence entry, routing it by date to
    exactly one of: opening position, period activity, or excluded.

    The buckets are mutually exclusive and exhaustive by construction —
    `ReportingPeriod`'s predicates partition the timeline — so no amount can be
    counted twice or silently dropped.
    """
    if row["direction"] not in _SIDES:  # pragma: no cover — filtered in SQL
        return

    own_id, own_name, party_id, party_name = _own_and_party(row)
    if company_id is not None and own_id != company_id:
        return

    amount = row["bill_amount"] or DEC_0
    is_purchase = row["direction"] == LicenseTrade.DIR_PURCHASE
    txn_date = row["date"]

    if period.is_after_period(txn_date):
        entry["excluded_after_period"] += 1
        return

    if period.is_before_period(txn_date):
        # Historical: carried forward as cost basis / opening position, NOT as
        # period activity, and NOT shown as a period transaction row.
        entry["opening_position"] += amount if is_purchase else -amount
        return

    if not period.includes_transaction(txn_date):
        # Only reachable for an UNDATED trade under a bounded window: it belongs to
        # no month, so it is neither opening nor activity. Counted as excluded so
        # the omission is visible rather than silent.
        entry["excluded_after_period"] += 1
        return

    company = entry["companies"].get(own_id)
    if company is None:
        company = {
            "company_id": own_id,
            "company_name": own_name or "Unknown",
            "purchases": [],
            "sales": [],
            "purchase_total": DEC_0,
            "sale_total": DEC_0,
            "profit_loss": DEC_0,
        }
        entry["companies"][own_id] = company

    activity_row = {
        "trade_id": row["trade_id"],
        "date": txn_date,
        "direction": row["direction"],
        "amount": amount,
        "company_id": own_id,
        "company_name": own_name or "Unknown",
        "party_id": party_id,
        "party_name": party_name or None,
    }
    if is_purchase:
        company["purchases"].append(activity_row)
        company["purchase_total"] += amount
        entry["credit_bill"] += amount
    else:
        company["sales"].append(activity_row)
        company["sale_total"] += amount
        entry["debit_bill"] += amount
    entry["has_period_activity"] = True


def _finalise_activity_entry(entry: Dict[str, Any]) -> None:
    """
    Derive every entry-level figure from the two accumulated bill sums.

    Nothing here is a fresh calculation: the per-company ``profit_loss``, the
    licence ``profit_loss`` and the ``closing_position`` are all
    `calculate_profit_loss` / `net_of` applied to sums that already exist, which is
    why the section 7 identity cannot fail and why the section 6 rule exists in
    one expression.
    """
    calc = LicenseLedgerAccountingService.calculate_profit_loss
    for company in entry["companies"].values():
        company["profit_loss"] = calc(company["sale_total"], company["purchase_total"])
    entry["profit_loss"] = calc(entry["debit_bill"], entry["credit_bill"])
    entry["profit_state"] = profit_state_for(entry["profit_loss"])
    entry["closing_position"] = entry["opening_position"] + net_of(
        entry["credit_bill"], entry["debit_bill"]
    )
