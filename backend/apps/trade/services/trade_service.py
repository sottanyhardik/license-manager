# trade/services/trade_service.py
"""
Domain service layer for the Trade app.

All functions here accept plain Python arguments (model instances, dicts,
primitives) and return plain Python values or model instances.  No HTTP
Request objects, no DRF Response objects.  Domain errors are raised as
ValueError (or subclasses) so the view layer can map them to HTTP status codes.
"""

from datetime import datetime, date
from uuid import uuid4
from typing import Optional
from django.db import IntegrityError, transaction
from django.utils import timezone


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_date_strict(date_str: Optional[str]) -> Optional[date]:
    """
    Parse a date string in strict ISO format (YYYY-MM-DD) only.

    Args:
        date_str: Date string to parse, or None/empty.

    Returns:
        ``date`` object on success, ``None`` when *date_str* is falsy.

    Raises:
        ValueError: If the string is present but not in YYYY-MM-DD format.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(
            f"Invalid date format. Expected YYYY-MM-DD, got: {date_str}"
        ) from exc


# ---------------------------------------------------------------------------
# Invoice number pre-fill
# ---------------------------------------------------------------------------

_VALID_DIRECTIONS = frozenset(
    ["PURCHASE", "SALE", "COMMISSION_PURCHASE", "COMMISSION_SALE"]
)


def get_prefilled_invoice_number(
    direction: str,
    company_id: int,
    invoice_date: Optional[date] = None,
) -> str:
    """
    Compute the next invoice number for a given direction / company / date.

    Args:
        direction:    Trade direction – one of PURCHASE, SALE, COMMISSION_PURCHASE,
                      COMMISSION_SALE.
        company_id:   PK of the CompanyModel record.
        invoice_date: Optional date that determines the Indian financial year.
                      Defaults to today when omitted.

    Returns:
        Next invoice number string (e.g. ``"LM/2025-26/0024"``).

    Raises:
        ValueError:         When *direction* is not recognised.
        CompanyModel.DoesNotExist: When *company_id* does not match any company.
    """
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(
            f"direction must be one of {sorted(_VALID_DIRECTIONS)}, got: {direction!r}"
        )

    from apps.core.models import CompanyModel
    from apps.trade.models import get_next_invoice_number

    company = CompanyModel.objects.get(pk=company_id)
    return get_next_invoice_number(
        direction=direction,
        company_name=company.name,
        invoice_date=invoice_date,
    )


# ---------------------------------------------------------------------------
# Trade summary
# ---------------------------------------------------------------------------

def build_trade_summary(trade) -> dict:
    """
    Return a plain dict of computed summary fields for a LicenseTrade instance.

    Args:
        trade: A :class:`~apps.trade.models.LicenseTrade` instance.

    Returns:
        Dict with keys: id, direction, invoice_number, invoice_date,
        subtotal_amount, roundoff, total_amount, paid_or_received, due_amount,
        lines_count, payments_count.
    """
    return {
        "id": trade.id,
        "direction": trade.direction,
        "invoice_number": trade.invoice_number,
        "invoice_date": trade.invoice_date,
        "subtotal_amount": str(trade.subtotal_amount),
        "roundoff": str(trade.roundoff),
        "total_amount": str(trade.total_amount),
        "paid_or_received": str(trade.paid_or_received),
        "due_amount": str(trade.due_amount),
        "lines_count": trade.lines.count(),
        "payments_count": trade.payments.count(),
    }


# ---------------------------------------------------------------------------
# Bidirectional trade linking
# ---------------------------------------------------------------------------

def link_trades(trade_pk: int, partner_pk: Optional[int]):
    """
    Bidirectionally link or unlink two LicenseTrade records.

    Linking rules:
    - *partner_pk* == None  → clear the link on *trade* and its current partner.
    - *partner_pk* == *trade_pk* → raises ValueError (cannot link to itself).
    - Otherwise → any stale links on either side are cleared, then both trades
      are linked to each other.

    Args:
        trade_pk:   PK of the primary trade.
        partner_pk: PK of the trade to link to, or ``None`` to unlink.

    Returns:
        The refreshed primary LicenseTrade instance.

    Raises:
        LicenseTrade.DoesNotExist: When *trade_pk* does not match any trade.
        ValueError: When *partner_pk* == *trade_pk*.
        PartnerTradeNotFound: When *partner_pk* is given but does not exist.
    """
    from apps.trade.models import LicenseTrade

    trade = LicenseTrade.objects.get(pk=trade_pk)

    # ---- Unlink ----
    if partner_pk is None:
        old_partner_id = trade.linked_trade_id
        LicenseTrade.objects.filter(pk=trade.pk).update(linked_trade=None)
        if old_partner_id:
            LicenseTrade.objects.filter(
                pk=old_partner_id, linked_trade=trade.pk
            ).update(linked_trade=None)
        trade.refresh_from_db()
        return trade

    # ---- Self-link guard ----
    if partner_pk == trade_pk:
        raise ValueError("Cannot link a trade to itself")

    # ---- Fetch partner ----
    try:
        partner = LicenseTrade.objects.get(pk=partner_pk)
    except LicenseTrade.DoesNotExist:
        raise PartnerTradeNotFound(f"Partner trade {partner_pk} not found")

    # ---- Clear stale links ----
    old_trade_partner = trade.linked_trade_id
    old_partner_partner = partner.linked_trade_id
    if old_trade_partner and old_trade_partner != partner.pk:
        LicenseTrade.objects.filter(pk=old_trade_partner).update(linked_trade=None)
    if old_partner_partner and old_partner_partner != trade.pk:
        LicenseTrade.objects.filter(pk=old_partner_partner).update(linked_trade=None)

    # ---- Set new link ----
    LicenseTrade.objects.filter(pk=trade.pk).update(linked_trade=partner)
    LicenseTrade.objects.filter(pk=partner.pk).update(linked_trade=trade)

    trade.refresh_from_db()
    return trade


class PartnerTradeNotFound(LookupError):
    """Raised when the partner trade PK cannot be resolved."""


# ---------------------------------------------------------------------------
# Canonical Sale <-> Purchase counterpart conversion
# ---------------------------------------------------------------------------

class CounterpartValidationError(ValueError):
    """A source trade cannot safely be mirrored into a counterpart."""


def copy_sale_to_purchase(sale_id: int, user=None):
    return _copy_to_counterpart(sale_id, source_direction='SALE', user=user)


def copy_purchase_to_sale(purchase_id: int, user=None):
    return _copy_to_counterpart(purchase_id, source_direction='PURCHASE', user=user)


def _copy_to_counterpart(source_id: int, *, source_direction: str, user=None):
    """Create exactly one mirrored commercial document under a row lock.

    The pair is deliberately made from distinct header/line rows: linked edits
    can be synchronized later without sharing mutable accounting records.
    """
    from apps.trade.models import LicenseTrade, LicenseTradeLine, IncentiveTradeLine, LicenseTradePayment, TradePairAudit, get_next_invoice_number

    destination_direction = 'PURCHASE' if source_direction == 'SALE' else 'SALE'
    with transaction.atomic():
        source = (LicenseTrade.objects.select_for_update(of=('self',))
                  .select_related('from_company', 'to_company', 'counterpart')
                  .prefetch_related('lines', 'incentive_lines', 'payments', 'boes')
                  .get(pk=source_id))
        if source.direction != source_direction:
            raise CounterpartValidationError(f'Only a {source_direction.lower()} can be copied by this action.')
        if source.counterpart_id:
            return source, source.counterpart, False
        if not source.from_company_id or not source.to_company_id:
            raise CounterpartValidationError('Both seller/supplier and buyer/purchasing company are required.')
        lines = list(source.lines.all())
        incentive_lines = list(source.incentive_lines.all())
        if not lines and not incentive_lines:
            raise CounterpartValidationError('At least one licence line is required before copying.')
        if any(not line.sr_number_id for line in lines) or any(not line.incentive_license_id for line in incentive_lines):
            raise CounterpartValidationError('Every copied line must reference its canonical licence item or licence.')

        pair_uuid = uuid4()
        # The destination owns its normal number sequence.  A sale number is
        # retained only as an auditable source-document reference.
        destination_number = get_next_invoice_number(
            direction=destination_direction,
            company_name=source.to_company.name,
            invoice_date=source.invoice_date,
        )
        try:
            destination = LicenseTrade.objects.create(
                direction=destination_direction, license_type=source.license_type,
                incentive_license=source.incentive_license,
                # This is the same commercial transfer viewed as the other
                # document type: the supplier/seller remains `from_company`
                # and the purchasing/buying company remains `to_company`.
                # Only direction, document number and payment semantics vary.
                from_company=source.from_company, to_company=source.to_company,
                invoice_number=destination_number, invoice_date=source.invoice_date,
                remarks=source.remarks, transaction_pair_uuid=pair_uuid,
                copied_from=source, copied_from_type=source.direction,
                source_document_number=source.invoice_number,
                created_by=user if getattr(user, 'is_authenticated', False) else source.created_by,
            )
        except IntegrityError:
            # Unique counterpart races are resolved by returning the pair that
            # committed first; no second document is exposed.
            source.refresh_from_db(fields=['counterpart'])
            if source.counterpart_id:
                return source, source.counterpart, False
            raise

        for line in lines:
            clone = LicenseTradeLine.objects.create(
                trade=destination, sr_number=line.sr_number, description=line.description,
                hsn_code=line.hsn_code, mode=line.mode, qty_kg=line.qty_kg,
                rate_inr_per_kg=line.rate_inr_per_kg, cif_fc=line.cif_fc,
                exc_rate=line.exc_rate, cif_inr=line.cif_inr, fob_inr=line.fob_inr,
                pct=line.pct, amount_inr=line.amount_inr, transaction_pair_uuid=pair_uuid,
            )
            line.counterpart_line = clone
            line.transaction_pair_uuid = pair_uuid
            line.save(update_fields=['counterpart_line', 'transaction_pair_uuid'])
            clone.counterpart_line = line
            clone.save(update_fields=['counterpart_line'])
        for line in incentive_lines:
            IncentiveTradeLine.objects.create(
                trade=destination, incentive_license=line.incentive_license,
                license_value=line.license_value, rate_pct=line.rate_pct,
                amount_inr=line.amount_inr,
            )
        # Payment amount remains the same commercial settlement: it means
        # received on the sale and paid on the purchase.
        for payment in source.payments.all():
            LicenseTradePayment.objects.create(
                trade=destination, date=payment.date, amount=payment.amount,
                note=f'Copied from {source.invoice_number}: {payment.note}'.strip(),
            )
        destination.recompute_totals()
        destination.refresh_from_db()
        source.recompute_totals()
        source.refresh_from_db()
        if source.total_amount != destination.total_amount:
            raise CounterpartValidationError('Counterpart total differs from source; conversion was rolled back.')
        source.counterpart = destination
        source.transaction_pair_uuid = pair_uuid
        source.save(update_fields=['counterpart', 'transaction_pair_uuid', 'modified_on'])
        destination.counterpart = source
        destination.save(update_fields=['counterpart', 'modified_on'])
        TradePairAudit.objects.create(
            pair_uuid=pair_uuid, source=source, counterpart=destination,
            action='COPIED', user=user if getattr(user, 'is_authenticated', False) else None,
            occurred_at=timezone.now(),
        )
        return source, destination, True


# ---------------------------------------------------------------------------
# BOE invoice stamping
# ---------------------------------------------------------------------------

def stamp_boe_invoice_from_trade(trade, boe) -> None:
    """
    Stamp `boe.invoice_no` / `boe.invoice_date` from `trade`'s own invoice
    fields, when the trade has an invoice number set.

    Shared by `LicenseTradeSerializer.update()` (re-stamps every BOE
    currently linked to the trade after a header/`boes` edit) and the
    reconciliation panel's `link` action (single BOE attach), so both code
    paths that "attach a BOE to a trade" apply the exact same stamping
    rule and can't drift apart.

    A BOE that is currently genuinely hidden (previous-owner utilisation —
    see `apps.bill_of_entry.models.OTH_INVOICE_MARKER` /
    `genuinely_hidden_boe_ids`) is left untouched: overwriting its
    `invoice_no` here would silently un-hide it with no audit trail and no
    balance recompute. Hidden/visible state may only change through the
    audited `hide_boe`/`restore_boe` workflow
    (`apps.bill_of_entry.services.boe_service`); attaching a BOE to a trade
    purely for invoicing must not have that side effect. Restore the BOE
    first if it genuinely needs to be re-linked as visible.

    Args:
        trade: LicenseTrade instance.
        boe: BillOfEntryModel instance to stamp.
    """
    if not trade.invoice_number:
        return

    from apps.bill_of_entry.models import genuinely_hidden_boe_ids

    if boe.id in genuinely_hidden_boe_ids(boe_ids=[boe.id]):
        return

    boe.invoice_no = trade.invoice_number
    boe.invoice_date = trade.invoice_date
    boe.save(update_fields=["invoice_no", "invoice_date"])
