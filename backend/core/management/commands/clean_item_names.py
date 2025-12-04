# core/management/commands/clean_item_names.py
from django.core.management.base import BaseCommand
from core.models import ItemNameModel


class Command(BaseCommand):
    help = "Clean (delete) all ItemNameModel records from the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm deletion of all item names. Required to actually delete.",
        )

    def handle(self, *args, **opts):
        confirm = opts.get("confirm")

        # Count existing records
        total_count = ItemNameModel.objects.count()

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✓ No item names found. Database is already clean."))
            return

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.WARNING(f"⚠️  DANGER: This will delete ALL {total_count} ItemNameModel records!"))
        self.stdout.write("=" * 80)

        if not confirm:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("Deletion NOT confirmed. No changes made."))
            self.stdout.write("")
            self.stdout.write("To actually delete all item names, run:")
            self.stdout.write(self.style.WARNING("  python manage.py clean_item_names --confirm"))
            self.stdout.write("")
            self.stdout.write("Current ItemNameModel records:")

            # Show first 10 records as preview
            preview_items = ItemNameModel.objects.all()[:10]
            for item in preview_items:
                group_name = item.group.name if item.group else "No Group"
                self.stdout.write(f"  - {item.name} (Group: {group_name})")

            if total_count > 10:
                self.stdout.write(f"  ... and {total_count - 10} more")

            return

        # Confirmed deletion
        self.stdout.write("")
        self.stdout.write("Deleting all ItemNameModel records...")

        # Delete all records
        deleted_count, details = ItemNameModel.objects.all().delete()

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS(f"✅ Successfully deleted {deleted_count} records"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("Deletion details:")
        for model, count in details.items():
            self.stdout.write(f"  - {model}: {count} records")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✓ ItemNameModel table is now empty"))
