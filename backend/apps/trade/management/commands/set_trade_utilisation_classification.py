"""Record an explicit utilisation classification for trades.

Dry run unless --apply is given. Only TradeUtilisationClassification rows are written. Trades,
trade lines, invoices, BOEs and allotments are never edited.

Example:
    python manage.py set_trade_utilisation_classification --trade 637 --trade 638 \
        --classification INTERNAL --reason "..." --evidence "..." --by hardik --apply
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.trade.models import LicenseTrade, LicenseTradeLine, TradeUtilisationClassification


class Command(BaseCommand):
    help = "Record an authorised utilisation classification (INTERNAL, EXTERNAL or REVIEW) for trades."

    def add_arguments(self, parser):
        parser.add_argument("--trade", type=int, action="append", required=True, help="Trade id. Repeat for several.")
        parser.add_argument(
            "--classification", required=True,
            choices=[value for value, _label in TradeUtilisationClassification.CLASS_CHOICES],
        )
        parser.add_argument("--reason", required=True, help="Why the trade has this classification.")
        parser.add_argument("--evidence", default="", help="Source documents or confirmations relied on.")
        parser.add_argument("--by", required=True, help="Username of the authorising user.")
        parser.add_argument("--apply", action="store_true", help="Write the records. Without it, nothing is written.")

    def handle(self, *args, **options):
        reason = (options["reason"] or "").strip()
        if not reason:
            raise CommandError("--reason is required.")
        User = get_user_model()
        try:
            user = User.objects.get(username=options["by"])
        except User.DoesNotExist as exc:
            raise CommandError(f"No user named {options['by']!r}.") from exc

        trade_ids = sorted(set(options["trade"]))
        trades = {t.id: t for t in LicenseTrade.objects.filter(id__in=trade_ids)}
        missing = [tid for tid in trade_ids if tid not in trades]
        if missing:
            raise CommandError(f"No trade with id {missing}.")

        classification = options["classification"]
        for tid in trade_ids:
            trade = trades[tid]
            existing = TradeUtilisationClassification.objects.filter(trade=trade).first()
            licences = sorted(set(
                LicenseTradeLine.objects.filter(trade=trade).values_list("sr_number__license__license_number", flat=True)
            ))
            self.stdout.write(
                f"trade {tid} {trade.direction} inv={trade.invoice_number!r} "
                f"licences={licences} "
                f"current={existing.classification if existing else 'none (EXTERNAL)'} -> {classification}"
            )

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry run. Nothing written. Add --apply to record."))
            return

        with transaction.atomic():
            for tid in trade_ids:
                TradeUtilisationClassification.objects.update_or_create(
                    trade=trades[tid],
                    defaults={
                        "classification": classification,
                        "reason": reason,
                        "evidence": options["evidence"],
                        "authorised_by": user,
                    },
                )
        self.stdout.write(self.style.SUCCESS(f"Recorded {classification} for trades {trade_ids}."))
