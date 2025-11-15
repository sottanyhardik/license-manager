from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from license.models import LicenseDetailsModel


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        from item_fetch_conf import fetch_data, generate_excel, split_list
        generate_excel(fetch_data(split_list()))
        self.stdout.write(self.style.SUCCESS('Report Generated'))

