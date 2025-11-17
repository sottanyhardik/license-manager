# license/management/commands/update_license_expiry.py
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from license.models import LicenseDetailsModel


class Command(BaseCommand):
    help = (
        "Update is_expired flag for all licenses based on expiry date. "
        "Sets is_expired=True if license_expiry_date <= today - 30 days."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--license",
            dest="license_number",
            help="Limit to a specific license_number (exact match).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write any changes; just report what would be updated.",
        )

    def handle(self, *args, **opts):
        license_number = opts.get("license_number")
        dry_run = bool(opts.get("dry_run"))

        qs = LicenseDetailsModel.objects.all()
        if license_number:
            qs = qs.filter(license_number=license_number)

        today = date.today()
        thirty_days_ago = today - timedelta(days=30)

        updated_count = 0
        expired_count = 0
        not_expired_count = 0

        self.stdout.write(f"Today's date: {today}")
        self.stdout.write(f"30 days ago: {thirty_days_ago}")
        self.stdout.write(f"Checking {qs.count()} licenses...")
        self.stdout.write("")

        for lic in qs.iterator():
            if not lic.license_expiry_date:
                # Skip licenses without expiry date
                continue

            # Check if license should be expired
            should_be_expired = lic.license_expiry_date <= thirty_days_ago

            if should_be_expired != lic.is_expired:
                self.stdout.write(
                    f"License {lic.license_number} (Expiry: {lic.license_expiry_date}): "
                    f"is_expired {lic.is_expired} → {should_be_expired}"
                )

                if not dry_run:
                    lic.is_expired = should_be_expired
                    lic.save(update_fields=['is_expired'])

                updated_count += 1

                if should_be_expired:
                    expired_count += 1
                else:
                    not_expired_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Done. Total licenses updated: {updated_count} | "
                f"Marked as expired: {expired_count} | "
                f"Marked as not expired: {not_expired_count} | "
                f"dry_run={dry_run}"
            )
        )
