"""Explicit business-approved CARDAMOM multi-norm consolidation.

This is intentionally *not* a fuzzy/similar-name merger.  It only merges the
four approved legacy names ``CARDAMOM - E1/E5/E126/E132`` into ``CARDAMOM``.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from apps.core.models import ItemNameModel
from apps.core.management.commands.merge_item_name_duplicates import REFERENCE_FIELDS
from apps.license.models import LicenseImportItemsModel


APPROVED_NAMES = frozenset({
    "CARDAMOM - E1", "CARDAMOM - E5", "CARDAMOM - E126", "CARDAMOM - E132",
})


class Command(BaseCommand):
    help = "Merge the explicitly approved CARDAMOM norm-suffixed item masters into one CARDAMOM item."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Perform the transactional merge; default is dry-run.")

    def handle(self, *args, **options):
        items = list(ItemNameModel.objects.filter(name__in=APPROVED_NAMES).order_by("pk").prefetch_related("norms"))
        unexpected = ItemNameModel.objects.filter(name="CARDAMOM").exclude(pk__in=[item.pk for item in items]).exists()
        if unexpected:
            raise CommandError("A separate CARDAMOM master already exists; refusing to choose an identity automatically.")
        if len(items) < 2:
            self.stdout.write("No CARDAMOM merge is required.")
            return
        survivor, *duplicates = items
        norm_codes = sorted({norm.norm_class for item in items for norm in item.norms.all()} | {
            item.sion_norm_class.norm_class for item in items if item.sion_norm_class_id
        })
        self.stdout.write(f"Survivor: {survivor.pk} {survivor.name!r}")
        self.stdout.write(f"Merge: {[item.pk for item in duplicates]}")
        self.stdout.write(f"Final name: CARDAMOM; norms: {', '.join(norm_codes)}")
        if not options["apply"]:
            self.stdout.write("Dry run only. Re-run with --apply after review.")
            return

        try:
            with transaction.atomic():
                locked = list(ItemNameModel.objects.select_for_update().filter(pk__in=[item.pk for item in items]).order_by("pk"))
                survivor, *duplicates = locked
                survivor.name = "CARDAMOM"
                survivor.save(update_fields=["name", "normalized_name", "modified_on"])
                survivor.norms.add(*[norm.pk for item in locked for norm in item.norms.all()])
                through = LicenseImportItemsModel.items.through
                for duplicate in duplicates:
                    for source_id in through.objects.filter(itemnamemodel_id=duplicate.pk).values_list("licenseimportitemsmodel_id", flat=True):
                        through.objects.get_or_create(licenseimportitemsmodel_id=source_id, itemnamemodel_id=survivor.pk)
                    through.objects.filter(itemnamemodel_id=duplicate.pk).delete()
                    for model, field in REFERENCE_FIELDS:
                        model._default_manager.filter(**{f"{field}_id": duplicate.pk}).update(**{f"{field}_id": survivor.pk})
                    if any(model._default_manager.filter(**{f"{field}_id": duplicate.pk}).exists() for model, field in REFERENCE_FIELDS):
                        raise CommandError(f"Item {duplicate.pk} still has a direct reference; rolling back.")
                    duplicate.delete()
        except IntegrityError as exc:
            raise CommandError(f"A unique constraint collision prevented the merge; no changes committed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS("CARDAMOM consolidated into one multi-norm ItemNameModel."))
