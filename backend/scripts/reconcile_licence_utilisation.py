"""Read-only utilisation reconstruction for one licence.

Usage (from backend/):
    PYTHONPATH=$(pwd) DJANGO_SETTINGS_MODULE=lmanagement.settings ../.venv/bin/python \
        scripts/reconcile_licence_utilisation.py <licence_number> [item_serial ...]

Writes nothing. Reads trades, trade lines, pair-audit rows, BOE debit rows, allotments and the
stored balance. Classifications and reasons are printed for audit.

Classification of a PURCHASE/SALE pair (never by name, date or amount alone):
  INTER-RELATED  - a COPIED pair-audit row joins the two trades AND one trade's copied_from points
                   at the other AND the canonical graph has marked the sale INTERLINKED.
  REVIEW         - a COPIED pair-audit row joins them but the graph does not agree.
  INDEPENDENT    - no pair relationship.

Entitlement effect:
  INTER-RELATED trades are excluded from utilisation, both sides.
  INDEPENDENT purchases carry no entitlement effect.
  INDEPENDENT sales are uncovered invoice utilisation unless a BOE already covers them.
  REVIEW trades are held, not counted either way.

BOE debits are VERIFIED only when the filing company is the licence holder or a party on the
documented ownership chain. The chain comes from the transfer letter, because the database holds
no transfer record. Anything else is REVIEW. Allotments are read as CREATED rows.
"""
import sys
from collections import defaultdict
from decimal import Decimal

import django

django.setup()

from apps.allotment.models import AllotmentItems  # noqa: E402
from apps.bill_of_entry.models import RowDetails  # noqa: E402
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseBalance  # noqa: E402
from apps.trade.models import LicenseTradeLine, TradePairAudit  # noqa: E402

Z = Decimal("0")

# Documented ownership chain, from the transfer letter dated 27 Aug 2026 (5611004885_TL.pdf).
# The database has no LicenseTransferModel rows for this licence. Each entry is a company name.
DOCUMENTED_HOLDERS = {"MONTY CONFECTIONERY", "VISION GURUKRUPA BUILDCON LLP"}


# Internal (group-company) classification. Nothing in the database records one. The only explicit
# sale classifications are FINAL_PARTY, INTERLINKED and NOT_APPLICABLE, and INTERLINKED means a
# paired or copied transfer branch, not group ownership. Add approved trade IDs here only after
# an authorised decision. Anything not listed here is REVIEW.
VERIFIED_INTERNAL_TRADE_IDS = set()
VERIFIED_EXTERNAL_TRADE_IDS = set()


def classify_trade(trade, counterpart, audit_actions):
    """Return (class, reason). Never infers internal status from amount, name, date or pairing."""
    if trade.id in VERIFIED_INTERNAL_TRADE_IDS:
        return "VERIFIED_INTERNAL", "explicit approved internal classification"
    if trade.id in VERIFIED_EXTERNAL_TRADE_IDS:
        return "VERIFIED_EXTERNAL", "explicit approved external classification"
    notes = []
    if counterpart is not None:
        copied = "COPIED" in audit_actions
        copied_link = trade.copied_from_id == counterpart.id or counterpart.copied_from_id == trade.id
        notes.append(
            f"pair-audit {sorted(audit_actions)} with {counterpart.id}"
            f"{', copied_from link' if copied_link else ''}"
            f"{', graph ' + str(trade.final_party_status) if trade.final_party_status != 'UNKNOWN' else ''}"
        )
    if trade.final_party_status == "INTERLINKED":
        notes.append("graph INTERLINKED = paired/copied transfer branch, not a group classification")
    return "REVIEW", "; ".join(notes) or "no explicit internal or external classification"


def main(licence_number, serials):
    lic = LicenseDetailsModel.objects.get(license_number=licence_number)
    items = list(LicenseImportItemsModel.objects.filter(license=lic, serial_number__in=serials).order_by("serial_number"))
    lines = list(
        LicenseTradeLine.objects.filter(sr_number__in=items)
        .select_related("trade__from_company", "trade__to_company", "sr_number")
        .order_by("sr_number__serial_number", "trade__invoice_date", "trade_id")
    )
    trade_ids = {ln.trade_id for ln in lines}
    audits = defaultdict(set)
    partner = {}
    for a in TradePairAudit.objects.filter(source_id__in=trade_ids) | TradePairAudit.objects.filter(counterpart_id__in=trade_ids):
        audits[frozenset((a.source_id, a.counterpart_id))].add(a.action)
        partner.setdefault(a.source_id, a.counterpart)
        partner.setdefault(a.counterpart_id, a.source)

    from apps.trade.models import LicenseTrade
    trades = {t.id: t for t in LicenseTrade.objects.filter(id__in=trade_ids).select_related("from_company", "to_company", "copied_from")}

    summary = {}
    for it in items:
        print(f"\n==== SR {it.serial_number}  item {it.id}  {it.description!r}  HS {it.hs_code_id}")
        print(f"     authorised CIF (FFE) {it.cif_fc}   authorised qty {it.quantity} {it.unit}")
        item_lines = [ln for ln in lines if ln.sr_number_id == it.id]
        gross_p = Z; gross_pq = Z; gross_s = Z; gross_sq = Z
        excluded_p = Z; excluded_s = Z; review_p = Z; review_s = Z
        indep_sale_c = Z; indep_sale_q = Z
        review_sale_c = Z; review_sale_q = Z
        boe_covered_trades = set()
        for ln in item_lines:
            t = trades[ln.trade_id]
            counterpart = None
            actions = set()
            for other_id in trade_ids:
                if other_id == t.id:
                    continue
                key = frozenset((t.id, other_id))
                if key in audits:
                    counterpart = trades[other_id] if other_id in trades else None
                    actions = audits[key]
                    break
            cls, reason = classify_trade(t, counterpart, actions)
            boes = list(t.boes.values_list("id", flat=True))
            if boes:
                boe_covered_trades.add(t.id)
            if t.direction == "PURCHASE":
                gross_p += ln.cif_fc; gross_pq += ln.qty_kg
            else:
                gross_s += ln.cif_fc; gross_sq += ln.qty_kg
            if cls == "VERIFIED_INTERNAL":
                if t.direction == "PURCHASE":
                    excluded_p += ln.cif_fc
                else:
                    excluded_s += ln.cif_fc
            elif cls == "REVIEW":
                if t.direction == "PURCHASE":
                    review_p += ln.cif_fc
                else:
                    review_s += ln.cif_fc
                    if not boes:
                        review_sale_c += ln.cif_fc; review_sale_q += ln.qty_kg
            elif t.direction == "SALE" and not boes:
                indep_sale_c += ln.cif_fc; indep_sale_q += ln.qty_kg
            print(
                f"  TRADE {t.id:>4} {t.direction:<8} inv={t.invoice_number!r:<22} {t.invoice_date}  "
                f"from={t.from_company.name} -> to={t.to_company.name}  CIF {ln.cif_fc}  qty {ln.qty_kg}  "
                f"exc {ln.exc_rate}  boes={boes}  copied_from={t.copied_from_id} graph={t.final_party_status}"
            )
            print(f"        class={cls}: {reason}")

        rows = list(RowDetails.objects.filter(sr_number=it, transaction_type="D").select_related("bill_of_entry__company"))
        boe_verified_c = Z; boe_verified_q = Z; boe_review_c = Z; boe_review_q = Z
        for r in rows:
            filer = r.bill_of_entry.company.name
            verified = filer in DOCUMENTED_HOLDERS
            print(
                f"  BOE row {r.id} BOE {r.bill_of_entry_id} {r.bill_of_entry.bill_of_entry_number} "
                f"{r.bill_of_entry.bill_of_entry_date} filer={filer!r}  CIF {r.cif_fc}  qty {r.qty}  "
                f"-> {'VERIFIED' if verified else 'REVIEW (filer not on documented chain)'}"
            )
            if verified:
                boe_verified_c += r.cif_fc; boe_verified_q += r.qty
            else:
                boe_review_c += r.cif_fc; boe_review_q += r.qty

        allot = list(AllotmentItems.objects.filter(item=it, status="CREATED"))
        allot_c = sum((a.cif_fc for a in allot), Z); allot_q = sum((a.qty for a in allot), Z)
        print(f"  allotments CREATED: {len(allot)} rows  CIF {allot_c}  qty {allot_q}")

        verified_util_c = boe_verified_c + allot_c + indep_sale_c
        verified_util_q = boe_verified_q + allot_q + indep_sale_q
        avail_c = it.cif_fc - verified_util_c
        avail_q = it.quantity - verified_util_q
        pending_c = boe_review_c
        pending_q = boe_review_q
        print("  --- sections")
        print(f"  gross purchase CIF {gross_p} qty {gross_pq}")
        print(f"  gross sale     CIF {gross_s} qty {gross_sq}")
        print(f"  excluded inter-related: purchases {excluded_p}  sales {excluded_s}")
        print(f"  held for REVIEW: purchases {review_p}  sales {review_s}")
        print(f"  BOE verified CIF {boe_verified_c} qty {boe_verified_q}; BOE held for REVIEW CIF {boe_review_c} qty {boe_review_q}")
        print(f"  uncovered independent sales CIF {indep_sale_c} qty {indep_sale_q}")
        print(f"  VERIFIED available  CIF {avail_c}  qty {avail_q}")
        print(f"  PENDING (if REVIEW BOE confirmed) CIF {avail_c - pending_c}  qty {avail_q - pending_q}")
        # The REVIEW sales are not deducted in the verified figure. Scenario A treats them as internal, so
        # nothing is deducted. Scenario B treats them as external uncovered utilisation.
        print(f"  SCENARIO A (REVIEW sales internal)  CIF {avail_c - pending_c}  qty {avail_q - pending_q}")
        print(f"  SCENARIO B (REVIEW sales external)  CIF {avail_c - pending_c - review_sale_c}  qty {avail_q - pending_q - review_sale_q}")
        summary[it.serial_number] = dict(original=it.cif_fc, avail=avail_c, avail_q=avail_q, pending=avail_c - pending_c, pending_q=avail_q - pending_q,
                                         gross_p=gross_p, gross_s=gross_s, excluded_p=excluded_p, excluded_s=excluded_s,
                                         boe_verified=boe_verified_c, boe_review=boe_review_c, original_q=it.quantity)

    print("\n==== STORED / LEGACY")
    lb = LicenseBalance.objects.filter(license=lic).first()
    print("stored LicenseBalance.balance_cif", lb and lb.balance_cif)
    return summary


if __name__ == "__main__":
    number = sys.argv[1] if len(sys.argv) > 1 else "5611004885"
    serials = [int(s) for s in sys.argv[2:]] or [1, 20]
    main(number, serials)
