"""
Read-only BOE invoice status (hidden / invoiced / invoice_no_recorded /
not_invoiced) for the BOE list, detail and filter.

The "invoiced" decision is NEVER re-implemented here: it is delegated to the
canonical resolver
`LicenseBalanceCalculator.resolve_boes_represented_by_invoice_for_licenses`
(BOE-level rule: a BOE is invoiced if its id is in the represented set of ANY
licence its debit rows touch).

Precedence: hidden > invoiced > invoice_no_recorded > not_invoiced.
Query cost per call is fixed (rows, hidden, resolver) regardless of BOE count.
"""
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails, genuinely_hidden_boe_ids
from apps.core.constants import DEBIT

STATUS_HIDDEN = "hidden"
STATUS_INVOICED = "invoiced"
STATUS_INVOICE_NO_RECORDED = "invoice_no_recorded"
STATUS_NOT_INVOICED = "not_invoiced"

INVOICE_STATUS_LABELS = {
    STATUS_HIDDEN: "Hidden",
    STATUS_INVOICED: "Invoiced",
    STATUS_INVOICE_NO_RECORDED: "Invoice no. recorded",
    STATUS_NOT_INVOICED: "Not invoiced",
}
INVOICE_STATUS_CHOICES = [[k, v] for k, v in INVOICE_STATUS_LABELS.items()]


def _normalise(boes_or_ids):
    """Return {boe_id: invoice_no}. Instances are read in place; bare ids cost one query."""
    items = list(boes_or_ids)
    result = {}
    bare_ids = []
    for item in items:
        if hasattr(item, "pk"):
            result[item.pk] = item.invoice_no or ""
        else:
            bare_ids.append(item)
    if bare_ids:
        result.update({
            pk: inv or ""
            for pk, inv in BillOfEntryModel.objects.filter(pk__in=bare_ids).values_list("pk", "invoice_no")
        })
    return result


def invoice_status_for_boes(boes_or_ids) -> dict:
    """`{boe_id: status}` for the given BOE instances / ids (fixed query count)."""
    from apps.license.services.balance_calculator import LicenseBalanceCalculator

    invoice_nos = _normalise(boes_or_ids)
    if not invoice_nos:
        return {}
    ids = list(invoice_nos)

    licenses_by_boe: dict = {}
    rows = (
        RowDetails.objects.filter(bill_of_entry_id__in=ids, transaction_type=DEBIT)
        .values_list("bill_of_entry_id", "sr_number__license_id")
        .distinct()
    )
    for boe_id, license_id in rows:
        if license_id is not None:
            licenses_by_boe.setdefault(boe_id, set()).add(license_id)

    # Only an 'OTH' BOE can be genuinely hidden (see genuinely_hidden_boe_ids),
    # so skip the audit-history lookup when no requested BOE carries 'OTH'.
    oth_ids = [pk for pk, inv in invoice_nos.items() if inv == "OTH"]
    hidden = genuinely_hidden_boe_ids(boe_ids=oth_ids) if oth_ids else set()
    all_license_ids = set().union(*licenses_by_boe.values()) if licenses_by_boe else set()
    represented = (
        LicenseBalanceCalculator.resolve_boes_represented_by_invoice_for_licenses(sorted(all_license_ids))
        if all_license_ids else {}
    )

    statuses = {}
    for boe_id in ids:
        if boe_id in hidden:
            statuses[boe_id] = STATUS_HIDDEN
        elif any(boe_id in represented.get(lid, ()) for lid in licenses_by_boe.get(boe_id, ())):
            statuses[boe_id] = STATUS_INVOICED
        elif invoice_nos[boe_id].strip():
            statuses[boe_id] = STATUS_INVOICE_NO_RECORDED
        else:
            statuses[boe_id] = STATUS_NOT_INVOICED
    return statuses


def boe_ids_for_statuses(statuses, base_queryset) -> set:
    """
    BOE ids in `base_queryset` whose invoice status is in `statuses`.
    Evaluated over the candidate set in bulk (not per row).
    """
    wanted = set(statuses)
    candidate_ids = list(base_queryset.order_by().values_list("pk", flat=True))
    status_map = invoice_status_for_boes(candidate_ids)
    return {pk for pk, status in status_map.items() if status in wanted}
