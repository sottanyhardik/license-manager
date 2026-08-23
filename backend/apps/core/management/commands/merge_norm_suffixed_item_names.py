"""Safely normalize norm-suffixed and ``- COMMON`` planning masters.

This command intentionally has a narrow, deterministic definition of
"similar": a trailing suffix must be an *actual* SION norm code in the
database, or exactly ``COMMON``. It does not fuzzy-match arbitrary names.
"""
import re
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from apps.core.management.commands.merge_item_name_duplicates import REFERENCE_FIELDS
from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import LicenseImportItemsModel


class Command(BaseCommand):
    help = "Dry-run or normalize ItemNameModel rows ending in an existing SION code or - COMMON."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Perform the transactional merge. Default is dry-run.")

    @staticmethod
    def _groups():
        norms = {norm.norm_class.upper(): norm for norm in SionNormClassModel.objects.all()}
        active_norm_ids = list(SionNormClassModel.objects.filter(is_active=True).values_list("pk", flat=True))
        suffix = re.compile(
            r"^(?P<base>.+?)\s*-\s*(?P<norm>[A-Za-z0-9]+)(?:\s*-\s*[0-9]+)?\s*$"
        )
        grouped = defaultdict(list)
        for item in ItemNameModel.objects.order_by("pk").prefetch_related("norms"):
            match = suffix.match(item.name or "")
            if not match:
                continue
            base = " ".join(match.group("base").split()).strip()
            suffix_code = match.group("norm").upper()
            if not base:
                continue
            if suffix_code == "COMMON":
                grouped[ItemNameModel.normalize_name(base)].append((item, base, active_norm_ids))
            elif suffix_code in norms:
                grouped[ItemNameModel.normalize_name(base)].append((item, base, [norms[suffix_code].pk]))
        return grouped

    def handle(self, *args, **options):
        groups = self._groups()
        candidates = []
        for key, suffixed in groups.items():
            base = suffixed[0][1]
            existing_base = ItemNameModel.objects.filter(normalized_name=key).exclude(pk__in=[item.pk for item, _, _ in suffixed]).order_by("pk").first()
            # A lone suffix is also a valid rename: e.g. "'O' Ring - C969".
            candidates.append((base, suffixed, existing_base))

        self.stdout.write(f"Safe norm-suffix groups: {len(candidates)}")
        for base, suffixed, existing_base in candidates:
            rows = ([existing_base] if existing_base else []) + [item for item, _, _ in suffixed]
            survivor = existing_base or min(rows, key=lambda item: item.pk)
            norm_ids = {norm_id for _, _, ids in suffixed for norm_id in ids}
            norms = sorted({norm.norm_class for norm in SionNormClassModel.objects.filter(pk__in=norm_ids)} | {norm.norm_class for item in rows for norm in item.norms.all()})
            self.stdout.write(f"  {base!r}: survivor={survivor.pk}; merge={[item.pk for item in rows if item.pk != survivor.pk]}; norms={','.join(norms)}")
        if not options["apply"]:
            self.stdout.write("Dry run only. Re-run with --apply after reviewing all groups.")
            return

        try:
            with transaction.atomic():
                for base, suffixed, existing_base in candidates:
                    ids = ([existing_base.pk] if existing_base else []) + [item.pk for item, _, _ in suffixed]
                    rows = list(ItemNameModel.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
                    survivor = (next((item for item in rows if existing_base and item.pk == existing_base.pk), None) or rows[0])
                    survivor.name = base
                    survivor.save(update_fields=["name", "normalized_name", "modified_on"])
                    suffix_norm_ids = [norm_id for _, _, ids in suffixed for norm_id in ids]
                    survivor.norms.add(*suffix_norm_ids, *[norm.pk for item in rows for norm in item.norms.all()])
                    through = LicenseImportItemsModel.items.through
                    for duplicate in [item for item in rows if item.pk != survivor.pk]:
                        for source_id in through.objects.filter(itemnamemodel_id=duplicate.pk).values_list("licenseimportitemsmodel_id", flat=True):
                            through.objects.get_or_create(licenseimportitemsmodel_id=source_id, itemnamemodel_id=survivor.pk)
                        through.objects.filter(itemnamemodel_id=duplicate.pk).delete()
                        for model, field in REFERENCE_FIELDS:
                            model._default_manager.filter(**{f"{field}_id": duplicate.pk}).update(**{f"{field}_id": survivor.pk})
                        if any(model._default_manager.filter(**{f"{field}_id": duplicate.pk}).exists() for model, field in REFERENCE_FIELDS):
                            raise CommandError(f"Item {duplicate.pk} retained a reference; transaction rolled back.")
                        duplicate.delete()
        except IntegrityError as exc:
            raise CommandError(f"A uniqueness collision prevented a safe merge; no changes committed: {exc}") from exc
        # The command's success condition includes referential verification,
        # not merely successful deletes.  Keep this import local so the
        # verifier remains usable independently as a read-only audit.
        from django.core.management import call_command
        call_command("verify_item_name_merge", stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Norm-suffixed item-name consolidation completed."))
