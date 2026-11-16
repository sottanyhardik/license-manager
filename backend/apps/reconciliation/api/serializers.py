# reconciliation/api/serializers.py
"""Response serializers for the reconciliation API (plain-dict shapes)."""
from ..models import ReconciliationLog


def _serialize_log(row: ReconciliationLog) -> dict:
    return {
        "id": row.id,
        "action": row.action,
        "trade_id": row.trade_id,
        "invoice_number": row.trade.invoice_number if row.trade_id and row.trade else None,
        "bill_of_entry_id": row.bill_of_entry_id,
        "bill_of_entry_number": row.bill_of_entry.bill_of_entry_number if row.bill_of_entry_id and row.bill_of_entry else None,
        "license_item_id": row.license_item_id,
        "before": row.before,
        "after": row.after,
        "reason": row.reason,
        "user": row.user.username if row.user_id and row.user else None,
        "created_on": row.created_on,
    }
