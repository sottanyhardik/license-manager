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


class TransactionSerializer(serializers.Serializer):
    """Serialize a single transaction in the canonical ledger."""

    date = serializers.DateField()
    id = serializers.IntegerField()
    type = serializers.CharField()
    company_id = serializers.IntegerField(allow_null=True)
    company_name = serializers.CharField(allow_null=True)
    amount = serializers.DecimalField(max_digits=19, decimal_places=2)
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
