from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate the CONF detail report from the legacy item_fetch_conf provider"

    def handle(self, *args, **options):
        from item_fetch_conf import fetch_data, generate_excel, split_list

        generate_excel(fetch_data(split_list()))
        self.stdout.write(self.style.SUCCESS("Report Generated"))
