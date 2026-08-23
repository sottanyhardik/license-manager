"""
Ledger API Serializers — Canonical representation of license ledger data

Serializes CanonicalLedgerService output for HTTP response.

**CRITICAL:** These are representation-only serializers. They perform NO calculations,
NO business logic, NO data transformation. They only map canonical dataset fields
to JSON response fields.

All financial calculations are performed by CanonicalLedgerService; this module
just presents the results to the client.
"""

from decimal import Decimal
from rest_framework import serializers


class InvoiceDocumentSerializer(serializers.Serializer):
    invoice_number = serializers.CharField(allow_blank=True)
    document_exists = serializers.BooleanField()
    signed = serializers.BooleanField()
    status = serializers.CharField()
    secure_url = serializers.CharField(allow_null=True, required=False)


class TransactionSerializer(serializers.Serializer):
    """Serialize a single transaction in the canonical ledger."""

    date = serializers.DateField()
    id = serializers.IntegerField()
    invoice_number = serializers.CharField(required=False, allow_blank=True)
    invoice_document = InvoiceDocumentSerializer(required=False, allow_null=True)
    type = serializers.CharField()
    #: OUR side of the trade — what the ledger table groups by.
    company_id = serializers.IntegerField(allow_null=True)
    company_name = serializers.CharField(allow_null=True)
    #: The COUNTERPARTY — what the "Particulars" column shows. NULL when the
    #: relation is absent (the UI renders 'N/A'); never a fabricated stand-in,
    #: and never `company_name`, which is our own company.
    party_id = serializers.IntegerField(allow_null=True, required=False)
    party_name = serializers.CharField(allow_null=True, required=False)
    #: The LICENSE value released/consumed by this trade — CIF FC (USD) for
    #: DFIA. A positive magnitude; the direction lives in `type`. Rendered in
    #: the Purchase column for PURCHASE, the Sale column for SALE
    #: (see `transaction_semantics.ledger_column_for`).
    amount = serializers.DecimalField(max_digits=19, decimal_places=2)
    #: The actual INVOICE value in **INR** (Σ line `amount_inr`). A DIFFERENT
    #: quantity in a DIFFERENT currency from `amount` — never assume they match.
    #: NULL on the OPENING row, which is a state and has no bill.
    bill_amount = serializers.DecimalField(
        max_digits=19, decimal_places=2, allow_null=True, required=False
    )
    ledger_column = serializers.CharField(allow_null=True, required=False)
    purchase_amount = serializers.DecimalField(max_digits=19, decimal_places=2, allow_null=True, required=False)
    sale_amount = serializers.DecimalField(max_digits=19, decimal_places=2, allow_null=True, required=False)
    purchase_bill_amount = serializers.DecimalField(max_digits=19, decimal_places=2, allow_null=True, required=False)
    sale_bill_amount = serializers.DecimalField(max_digits=19, decimal_places=2, allow_null=True, required=False)
    #: Billed licence item names, deduped, first-seen order ([] for incentive
    #: licences and the OPENING row). A list, not a joined string: one trade is
    #: ONE ledger row no matter how many items it bills.
    item_names = serializers.ListField(
        child=serializers.CharField(), required=False
    )
    rate = serializers.DecimalField(
        max_digits=19, decimal_places=4, allow_null=True, required=False
    )
    is_commission = serializers.BooleanField()
    affects_balance = serializers.BooleanField()
    license_running_balance = serializers.DecimalField(max_digits=19, decimal_places=2)
    company_utilization_after = serializers.DecimalField(
        max_digits=19, decimal_places=2, allow_null=True, required=False
    )
    display_status = serializers.CharField(required=False, allow_blank=True)
    # Presentation metadata, NOT a ledger fact: SION norms of the licence items
    # billed on this trade, comma-space joined ('' when none / non-DFIA).
    # Optional + blank-able so older/partial datasets keep serializing.
    sion_norms = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CompanyUtilizationSerializer(serializers.Serializer):
    """Serialize company-scoped balance breakdown."""

    company_id = serializers.IntegerField()
    company_name = serializers.CharField(allow_null=True)
    utilization_balance = serializers.DecimalField(max_digits=19, decimal_places=2)


class TotalsSerializer(serializers.Serializer):
    """Serialize aggregate transaction totals."""

    total_purchases = serializers.DecimalField(max_digits=19, decimal_places=2)
    total_sales = serializers.DecimalField(max_digits=19, decimal_places=2)
    total_commission = serializers.DecimalField(max_digits=19, decimal_places=2)


class LedgerSummarySerializer(serializers.Serializer):
    """
    Serialize the ledger `summary` block — the four figures above the table.

    Representation only — every value is produced by
    `CanonicalLedgerService._build_summary`; nothing is computed here.

    LEDGER COLUMNS (visual table columns)
      * `total_sale` = Σ the table's **Sale** column = SALE rows
                      (licence value consumed, reduces balance)
      * `total_purchase` = Σ the table's **Purchase** column = PURCHASE rows
                           + OPENING row (when shown)
                           (licence value added, increases balance)

    Backend identities:
        current_balance = total_purchase − total_sale
        total_profit_loss = total_sale_bill_inr − total_purchase_bill_inr

    WHY NO OPENING ADJUSTMENT:
    The display rule (`select_display_rows`) shows the acquisition exactly once:
      - PURCHASE exists  → OPENING suppressed, acquisition counted via purchase
      - no PURCHASE      → OPENING shown as starting state
    In both cases, total_purchase − total_sale gives the correct balance.
    `opening_balance` is licence metadata and is deliberately NOT added here,
    because when a PURCHASE exists, the opening and that purchase are the SAME
    economic event (licence acquisition), so adding would double-count.

    Currencies: `total_sale`/`total_purchase`/`opening_balance`/`current_balance`/
    `current_balance` are in `balance_currency` (USD for DFIA, INR otherwise).
    Bill totals and `total_profit_loss` are in INR.
    """

    total_sale = serializers.DecimalField(max_digits=19, decimal_places=2)
    total_purchase = serializers.DecimalField(max_digits=19, decimal_places=2)
    #: Σ of the two BILL columns, in `bill_currency` (INR). Published so the
    #: client never sums a money column; NOT part of the identity above, NOT in
    #: `balance_currency`, and NEVER an input to Profit / Loss.
    total_sale_bill_inr = serializers.DecimalField(max_digits=19, decimal_places=2)
    total_purchase_bill_inr = serializers.DecimalField(max_digits=19, decimal_places=2)
    bill_currency = serializers.CharField()
    #: The licence's own face value. Metadata only — deliberately OUTSIDE the
    #: identity above (adding it would double-count a purchased licence).
    opening_balance = serializers.DecimalField(max_digits=19, decimal_places=2)
    #: True when the OPENING row is displayed (and therefore already counted in
    #: `total_purchase`) — i.e. when the licence has no PURCHASE. Published so the
    #: client never re-derives the display rule.
    opening_in_purchase = serializers.BooleanField()
    current_balance = serializers.DecimalField(max_digits=19, decimal_places=2)
    balance_currency = serializers.CharField()

    #: Sale Bill − Purchase Bill, in `profit_currency` (INR). Signed.
    total_profit_loss = serializers.DecimalField(max_digits=19, decimal_places=2, allow_null=True)
    profit_currency = serializers.CharField()
    #: PROFIT | LOSS | BREAK_EVEN | UNAVAILABLE — decided in the backend so no
    #: client branches on the sign of a number.
    profit_state = serializers.CharField()


class CanonicalLedgerSerializer(serializers.Serializer):
    """
    Serialize the canonical ledger dataset for HTTP response.

    **IMPORTANT:** This is a representation layer only. It performs NO calculations.
    All financial values come directly from CanonicalLedgerService.build_canonical_ledger_dataset().

    Fields:
    - license_* : metadata about the license
    - opening_balance : starting balance (0.00 if none)
    - license_running_balance : final balance after all transactions
    - closing_balance : alias for license_running_balance
    - transactions : list of transaction objects
    - company_utilizations : per-company balance breakdown
    - totals : aggregate amounts
    - available_balance : DEPRECATED, alias to license_running_balance
    - db_balance : DEPRECATED, alias to license_running_balance
    """

    license_id = serializers.IntegerField()
    license_type = serializers.CharField()
    license_number = serializers.CharField()
    license_date = serializers.DateField()
    expiry_date = serializers.DateField()
    exporter_id = serializers.IntegerField(allow_null=True, required=False)
    exporter_name = serializers.CharField(allow_null=True)
    port_id = serializers.IntegerField(allow_null=True, required=False)
    port_name = serializers.CharField(allow_null=True)
    #: MIN(qualifying purchase invoice_date) — the licence's acquisition date,
    #: from the one canonical definition in `license_profit`. NULL when the
    #: licence has no qualifying purchase (and for incentive licences, which that
    #: definition does not reach). This is the field the ledger list's Purchase
    #: Date Range filters on, so a client can always see WHY a licence matched.
    first_purchase_date = serializers.DateField(allow_null=True, required=False)
    # Licence-level metadata across every DFIA import item, not transaction
    # rows. Empty for incentive licences or genuinely unclassified items.
    sion_norms = serializers.CharField(required=False, allow_blank=True)

    #: Purchase bill detection — TRUE if license has ≥1 qualifying PURCHASE with
    #: non-zero bill amount; FALSE if no such purchase exists. NOT inferred from
    #: balance state, but computed from actual trade bills.
    has_purchase_bill = serializers.BooleanField()
    #: Enumerated status: "WITH_PURCHASE_BILL" | "NO_PURCHASE_BILL"
    #: Derived from has_purchase_bill for easier client-side filtering.
    purchase_bill_status = serializers.CharField()
    has_purchase_transaction = serializers.BooleanField()

    opening_balance = serializers.DecimalField(max_digits=19, decimal_places=2)
    license_running_balance = serializers.DecimalField(max_digits=19, decimal_places=2)
    closing_balance = serializers.DecimalField(max_digits=19, decimal_places=2)

    transactions = TransactionSerializer(many=True)

    # ── Presentation only — carries NO financial meaning ──────────────────
    # `transactions` above remains the complete financial record. These two
    # fields are the ledger transaction display rule, applied ONCE in
    # `transaction_semantics.select_display_rows` and consumed verbatim by
    # every client. Clients must render these and must NOT re-derive the rule.
    #   * display_transactions — PURCHASE + SALE only, chronological order
    #     preserved, never contains OPENING.
    #   * opening_display — the OPENING starting-state row, present only when
    #     no PURCHASE exists; null otherwise.
    display_transactions = TransactionSerializer(many=True, read_only=True)
    opening_display = TransactionSerializer(read_only=True, allow_null=True)

    company_utilizations = serializers.DictField(child=CompanyUtilizationSerializer())
    totals = TotalsSerializer()

    # On-screen reconciliation block + canonical Profit / Loss. Additive: it
    # derives from the figures above and changes none of them. See
    # LedgerSummarySerializer for the Debit/Credit column-naming warning.
    summary = LedgerSummarySerializer(read_only=True)

    # Backward compatibility: old field names (Phase 4C only; deprecated in Phase 4D+).
    # Declared as DecimalField (not SerializerMethodField) so the aliases are
    # rendered IDENTICALLY to `license_running_balance` — i.e. as 2dp strings.
    # A SerializerMethodField returned the raw Decimal, which the JSON renderer
    # coerced to a float, so the same number was a string under one key and a
    # float under its own alias.
    available_balance = serializers.DecimalField(
        max_digits=19, decimal_places=2, source="license_running_balance", read_only=True
    )
    db_balance = serializers.DecimalField(
        max_digits=19, decimal_places=2, source="license_running_balance", read_only=True
    )
