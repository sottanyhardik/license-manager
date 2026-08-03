# license/management/commands/link_packaging_items.py
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.utils.item_matcher import bulk_auto_link_license_items, classify_packaging_item


class Command(BaseCommand):
    help = (
        "Run ItemNameModel auto-linking for licences, applying the packaging "
        "pre-classification rules (PP / HDPE / LDPE / Paper / Paper Board — see "
        "item_matcher.classify_packaging_item) ahead of the generic matcher. "
        "The rules apply to every SION norm — each match resolves to "
        "\"<PACKAGING_NAME> - <the licence's own norm>\". Use this to backfill "
        "existing licences after the rules were added or changed; new licences "
        "pick them up automatically via the post_save signal."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Report which import items the packaging rules would match, "
                "without writing any changes. Does not create ItemNameModel "
                "rows or preview the generic (non-packaging-rule) matcher — "
                "pair with `populate_license_items --dry-run` for that."
            ),
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help=(
                "Unlink ALL existing ItemNameModel links on these licences' "
                "import items first, then reclassify from scratch. Without "
                "this flag, only import items with NO existing item links "
                "are (re)classified — matching bulk_auto_link_license_items' "
                "normal behaviour."
            ),
        )
        parser.add_argument(
            "--norm",
            dest="norm_class",
            help="Limit to licences carrying this SION norm class (e.g. E1, PP, COMMON).",
        )
        parser.add_argument(
            "--license",
            dest="license_number",
            help="Limit to a single licence by license_number (for testing).",
        )

    def handle(self, *args, **opts):
        dry_run = bool(opts.get("dry_run"))
        clear_existing = bool(opts.get("clear"))
        norm_class = opts.get("norm_class")
        license_number = opts.get("license_number")

        licenses = (
            LicenseDetailsModel.objects
            .filter(export_license__isnull=False)
            .distinct()
            .order_by("license_number")
        )
        if norm_class:
            licenses = licenses.filter(export_license__norm_class__norm_class=norm_class)
        if license_number:
            licenses = licenses.filter(license_number=license_number)
            if not licenses.exists():
                raise CommandError(
                    f"No licence found with license_number={license_number!r}"
                    + (f" and norm {norm_class!r}" if norm_class else "")
                )

        total = licenses.count()
        self.stdout.write("=" * 80)
        self.stdout.write(f"Packaging item linking — {total} licence(s) found")
        self.stdout.write(f"Dry run: {dry_run}   Clear existing: {clear_existing}   Norm filter: {norm_class or 'ANY'}")
        self.stdout.write("=" * 80)

        if total == 0:
            self.stdout.write(self.style.WARNING("No matching licences found."))
            return

        if dry_run:
            self._preview(licenses, clear_existing=clear_existing)
            return

        through_model = LicenseImportItemsModel.items.through
        total_linked = 0
        for idx, license_obj in enumerate(licenses.iterator(), 1):
            if clear_existing:
                through_model.objects.filter(
                    licenseimportitemsmodel__license=license_obj
                ).delete()
            linked = bulk_auto_link_license_items(license_obj)
            total_linked += linked
            self.stdout.write(
                f"  [{idx}/{total}] {license_obj.license_number}: linked {linked} import item(s)"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✅ Done — linked items on {total_linked} import item(s) across {total} licence(s)."
        ))

    def _preview(self, licenses, *, clear_existing):
        """Read-only preview using classify_packaging_item directly (no
        ItemNameModel creation, no linking) so --dry-run never writes to the
        database. When --clear is also passed, every import item is
        considered (matching what a real --clear run would reclassify);
        otherwise only currently-unlinked import items are. The licence's
        own first norm class is used to render the full item name, exactly
        as bulk_auto_link_license_items would resolve it."""
        total_would_match = 0
        for license_obj in licenses.iterator():
            norm_classes = list(
                license_obj.export_license.values_list("norm_class__norm_class", flat=True).distinct()
            )
            if not norm_classes:
                continue
            current_norm = norm_classes[0]

            import_items = license_obj.import_license.select_related('hs_code')
            if not clear_existing:
                import_items = (
                    import_items
                    .annotate(_link_count=Count('items'))
                    .filter(_link_count=0)
                )
            for ii in import_items:
                hs_code_str = ii.hs_code.hs_code if ii.hs_code_id else None
                result = classify_packaging_item(hs_code_str, ii.description)
                if not result:
                    continue
                packaging_name, rule_tag = result
                total_would_match += 1
                self.stdout.write(
                    f"  + {license_obj.license_number} import item #{ii.serial_number}: "
                    f"{rule_tag} -> {packaging_name!r} -> '{packaging_name} - {current_norm}'"
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Would match {total_would_match} import item(s) via packaging rules "
            f"(generic matcher not previewed)."
        ))
