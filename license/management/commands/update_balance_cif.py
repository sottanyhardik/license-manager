from django.core.management.base import BaseCommand
from license.models import LicenseDetailsModel

class Command(BaseCommand):
    help = 'Update balance_cif field for all LicenseDetailsModel records'

    def handle(self, *args, **kwargs):
        licenses = LicenseDetailsModel.objects.all()
        updated = 0
        for lic in licenses:
            actual_balance = lic.get_balance_cif  # computed property
            if lic.balance_cif != actual_balance:
                lic.balance_cif = actual_balance
                lic.save(update_fields=['balance_cif'])
                updated += 1
                self.stdout.write(f"Updated {lic.license_number} with balance_cif = {actual_balance}")
        self.stdout.write(self.style.SUCCESS(f"✅ Updated {updated} license(s) with new balance_cif values."))
