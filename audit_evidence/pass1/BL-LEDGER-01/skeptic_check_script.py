import django, os, sys
sys.path.insert(0, "/Users/drushahardiksottany/PycharmProjects/license-manager/backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
django.setup()

from django.db import transaction
from apps.bill_of_entry.models import BillOfEntryModel, genuinely_hidden_boe_ids, OTH_INVOICE_MARKER
from apps.reconciliation.models import ReconciliationLog
from apps.trade.models import LicenseTrade
from apps.trade.services.trade_service import stamp_boe_invoice_from_trade
from apps.license.models import LicenseDetailsModel, LicenseBalance
from apps.license.services.balance_calculator import LicenseBalanceCalculator as C

print("=== Step A: independently re-derive genuinely-hidden BOE ids (not trusting claim's pick) ===")
hidden_ids = genuinely_hidden_boe_ids()
print("count genuinely hidden BOEs (system-wide):", len(hidden_ids))
print("is 27511 in independently-derived hidden set?", 27511 in hidden_ids)

boe = BillOfEntryModel.objects.get(id=27511)
print("boe 27511 invoice_no:", boe.invoice_no, " bill_of_entry_number:", boe.bill_of_entry_number)

logs = list(ReconciliationLog.objects.filter(bill_of_entry_id=27511).order_by("created_on").values("action","created_on","before","after"))
print("ReconciliationLog rows for boe 27511:")
for l in logs:
    print(" ", l)

print()
print("=== Step B: find license + row for this BOE's debit, independent query ===")
from apps.bill_of_entry.models import RowDetails
row = RowDetails.objects.select_related("sr_number__license").get(id=274336)
print("row 274336 cif_fc:", row.cif_fc, "transaction_type:", row.transaction_type)
lic = row.sr_number.license
print("license_number:", lic.license_number)

lb = LicenseBalance.objects.get(license=lic)
print("stored LicenseBalance.balance_cif BEFORE:", lb.balance_cif)
live_before = C.calculate_financial_balance(lic)
print("live calculate_financial_balance BEFORE:", live_before)

print()
print("=== Step C: confirm trade 542 is unrelated (not currently linked to boe 27511) and has its own invoice_number ===")
trade = LicenseTrade.objects.get(id=542)
print("trade.invoice_number:", trade.invoice_number)
print("trade currently linked boe ids:", list(trade.boes.values_list("id", flat=True)))
print("is boe 27511 already linked to trade 542?", trade.boes.filter(id=27511).exists())

print()
print("=== Step D: reproduce link action's effect inside atomic() rolled back ===")
try:
    with transaction.atomic():
        trade.boes.add(boe)
        stamp_boe_invoice_from_trade(trade, boe)

        boe.refresh_from_db()
        print("boe.invoice_no AFTER stamp:", boe.invoice_no)

        lic.refresh_from_db()
        lb_after = LicenseBalance.objects.get(license=lic)
        print("stored LicenseBalance.balance_cif AFTER (still not refreshed by any signal?):", lb_after.balance_cif)
        live_after = C.calculate_financial_balance(lic)
        print("live calculate_financial_balance AFTER:", live_after)
        print("delta:", live_after - live_before)

        # independent check: is boe 27511 still counted as genuinely hidden now?
        hidden_after = genuinely_hidden_boe_ids([27511])
        print("27511 still in genuinely_hidden_boe_ids([27511]) AFTER stamp?", 27511 in hidden_after)

        # check reconciliation log: did stamp_boe_invoice_from_trade itself write any log row?
        log_count_after = ReconciliationLog.objects.filter(bill_of_entry_id=27511).count()
        print("ReconciliationLog row count for boe 27511 AFTER stamp (should be unchanged if no audit trail):", log_count_after)

        raise RuntimeError("SKEPTIC ROLLBACK - no permanent change")
except RuntimeError as e:
    print("rolled back:", e)

print()
print("=== Step E: post-rollback sanity - confirm nothing persisted ===")
boe.refresh_from_db()
print("boe.invoice_no POST-ROLLBACK (should be back to OTH):", boe.invoice_no)
print("boe 27511 still linked to trade 542 POST-ROLLBACK?", LicenseTrade.objects.get(id=542).boes.filter(id=27511).exists())
lb_final = LicenseBalance.objects.get(license=lic)
print("stored LicenseBalance.balance_cif POST-ROLLBACK:", lb_final.balance_cif)
live_final = C.calculate_financial_balance(lic)
print("live calculate_financial_balance POST-ROLLBACK:", live_final)
