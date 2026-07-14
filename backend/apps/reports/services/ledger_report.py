# reports/services/ledger_report.py
"""
License ledger report service.

Assembles the transaction ledger for a single license:
  - License header (number, dates, balance)
  - Related allotments and trade lines where those apps are installed
    (uses lazy imports inside the function body to avoid circular import
    errors during app startup and to gracefully skip missing models)
"""
import logging
from datetime import UTC, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

_DEC_0 = Decimal("0")


def generate_ledger_report(license_id: int) -> dict:
    """
    Build the transaction ledger for *license_id*.

    Returns a dict with:
      - header  : basic license info
      - balance : current balance snapshot
      - transactions : chronological list of debit/credit/allotment events

    All cross-app model imports are deferred to this function body so that
    (a) circular-import risks at module load are eliminated, and (b) missing
    apps degrade gracefully rather than raising ImportError at startup.
    """
    from apps.license.models import LicenseDetailsModel

    logger.info("Generating ledger report for license_id=%s", license_id)

    lic = (
        LicenseDetailsModel.objects.select_related("exporter", "balance", "flags")
        .get(pk=license_id)
    )

    balance_obj = getattr(lic, "balance", None)
    balance_cif = balance_obj.balance_cif if balance_obj else _DEC_0

    # Header
    header = {
        "license_id": lic.pk,
        "license_number": lic.license_number,
        "license_date": lic.license_date.isoformat() if lic.license_date else None,
        "license_expiry_date": (
            lic.license_expiry_date.isoformat() if lic.license_expiry_date else None
        ),
        "exporter": str(lic.exporter) if lic.exporter_id else lic.archived_exporter_name,
        "balance_cif": balance_cif,
    }

    transactions = []

    # --- BOE / RowDetails debit transactions ---
    try:
        from apps.bill_of_entry.models import RowDetails  # type: ignore[import]

        rows = (
            RowDetails.objects.filter(boe__license_id=license_id)
            .select_related("boe")
            .order_by("boe__date")
        )
        for row in rows:
            transactions.append(
                {
                    "type": "BOE_DEBIT",
                    "date": (row.boe.date.isoformat() if row.boe.date else None),
                    "reference": getattr(row.boe, "boe_number", str(row.boe_id)),
                    "description": getattr(row, "description", ""),
                    "cif_fc": row.cif_fc,
                    "transaction_type": getattr(row, "transaction_type", ""),
                }
            )
    except ImportError:
        logger.debug("bill_of_entry app not installed — skipping BOE rows in ledger report.")
    except Exception:
        logger.exception("Error fetching BOE rows for license_id=%s", license_id)

    # --- Allotment transactions ---
    try:
        from apps.allotment.models import AllotmentItems  # type: ignore[import]

        allotment_items = (
            AllotmentItems.objects.filter(allotment__license_id=license_id)
            .select_related("allotment")
            .order_by("allotment__date")
        )
        for ai in allotment_items:
            allotment = ai.allotment
            transactions.append(
                {
                    "type": "ALLOTMENT",
                    "date": (
                        allotment.date.isoformat()
                        if getattr(allotment, "date", None)
                        else None
                    ),
                    "reference": str(allotment.pk),
                    "description": getattr(ai, "description", ""),
                    "cif_fc": ai.cif_fc,
                    "transaction_type": "ALLOTMENT",
                }
            )
    except ImportError:
        logger.debug("allotment app not installed — skipping allotment items in ledger report.")
    except Exception:
        logger.exception("Error fetching allotment items for license_id=%s", license_id)

    # --- Trade line transactions ---
    try:
        from apps.trade.models import LicenseTradeLine  # type: ignore[import]

        trade_lines = (
            LicenseTradeLine.objects.filter(trade__license_id=license_id)
            .select_related("trade")
            .order_by("trade__date")
        )
        for tl in trade_lines:
            trade = tl.trade
            transactions.append(
                {
                    "type": "TRADE",
                    "date": (
                        trade.date.isoformat()
                        if getattr(trade, "date", None)
                        else None
                    ),
                    "reference": str(trade.pk),
                    "description": getattr(trade, "direction", ""),
                    "cif_fc": tl.cif_fc,
                    "transaction_type": getattr(trade, "direction", "TRADE"),
                }
            )
    except ImportError:
        logger.debug("trade app not installed — skipping trade lines in ledger report.")
    except Exception:
        logger.exception("Error fetching trade lines for license_id=%s", license_id)

    # Sort all transactions by date (None dates sort last)
    transactions.sort(key=lambda t: (t["date"] is None, t["date"] or ""))

    return {
        "header": header,
        "transactions": transactions,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }
