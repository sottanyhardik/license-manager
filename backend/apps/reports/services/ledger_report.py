# reports/services/ledger_report.py
"""
License ledger report service.

Assembles the transaction ledger for a single license:
  - License header (number, dates, balance)
  - Related allotments and trade lines where those apps are installed
    (uses _safe_get_model to avoid crashing if apps are absent)

Models are imported inside the function to prevent circular import errors
during app startup.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

_DEC_0 = Decimal("0")


def _safe_get_model(app_label: str, model_name: str):
    """
    Return the Django model class or None if the app/model is not yet
    installed.  Mirrors the pattern in license/services/balance_service.py.
    """
    from django.apps import apps as django_apps

    try:
        return django_apps.get_model(app_label, model_name)
    except LookupError:
        logger.debug(
            "Model %s.%s not installed — skipping in ledger report.",
            app_label,
            model_name,
        )
        return None


def generate_ledger_report(license_id: int) -> dict:
    """
    Build the transaction ledger for *license_id*.

    Returns a dict with:
      - header  : basic license info
      - balance : current balance snapshot
      - transactions : chronological list of debit/credit/allotment events
    """
    from apps.license.models import LicenseBalance, LicenseDetailsModel

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
    RowDetails = _safe_get_model("bill_of_entry", "RowDetails")
    if RowDetails is not None:
        try:
            rows = (
                RowDetails.objects.filter(
                    boe__license_id=license_id,
                )
                .select_related("boe")
                .order_by("boe__date")
            )
            for row in rows:
                transactions.append(
                    {
                        "type": "BOE_DEBIT",
                        "date": (
                            row.boe.date.isoformat() if row.boe.date else None
                        ),
                        "reference": getattr(row.boe, "boe_number", str(row.boe_id)),
                        "description": getattr(row, "description", ""),
                        "cif_fc": row.cif_fc,
                        "transaction_type": getattr(row, "transaction_type", ""),
                    }
                )
        except Exception:
            logger.exception("Error fetching BOE rows for license_id=%s", license_id)

    # --- Allotment transactions ---
    AllotmentItems = _safe_get_model("allotment", "AllotmentItems")
    if AllotmentItems is not None:
        try:
            allotment_items = (
                AllotmentItems.objects.filter(
                    allotment__license_id=license_id,
                )
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
        except Exception:
            logger.exception(
                "Error fetching allotment items for license_id=%s", license_id
            )

    # --- Trade line transactions ---
    LicenseTradeLine = _safe_get_model("trade", "LicenseTradeLine")
    if LicenseTradeLine is not None:
        try:
            trade_lines = (
                LicenseTradeLine.objects.filter(
                    trade__license_id=license_id,
                )
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
        except Exception:
            logger.exception(
                "Error fetching trade lines for license_id=%s", license_id
            )

    # Sort all transactions by date (None dates sort last)
    transactions.sort(key=lambda t: (t["date"] is None, t["date"] or ""))

    return {
        "header": header,
        "transactions": transactions,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
