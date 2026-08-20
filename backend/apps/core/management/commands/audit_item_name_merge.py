"""Read-only preflight for safe ItemNameModel identity consolidation."""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.core.models import ItemNameModel


class Command(BaseCommand):
    help = "Report exact-normalized ItemNameModel duplicate groups and every FK that must be repointed."

    def handle(self, *args, **options):
        items = list(ItemNameModel.objects.prefetch_related("norms").order_by("pk"))
        groups = defaultdict(list)
        for item in items:
            groups[ItemNameModel.normalize_name(item.name)].append(item)

        references = []
        for relation in ItemNameModel._meta.related_objects:
            field = relation.field
            if not getattr(field, "many_to_one", False) and not getattr(field, "one_to_one", False):
                continue
            references.append((relation.related_model, field.name, field.remote_field.on_delete.__name__))
        # ``related_name='+'`` intentionally suppresses Django reverse
        # metadata for strategy-child FKs, so include them explicitly.
        from apps.license.models import SionPlanningPercentageRow, SionPlanningUnitValueRow
        references.extend([
            (SionPlanningPercentageRow, "import_item", "PROTECT"),
            (SionPlanningUnitValueRow, "import_item", "PROTECT"),
        ])

        self.stdout.write(f"ItemNameModel rows: {len(items)}")
        self.stdout.write("Reference inventory:")
        for model, field, on_delete in sorted(references, key=lambda value: (value[0]._meta.label, value[1])):
            self.stdout.write(f"  {model._meta.label}.{field}  on_delete={on_delete}")

        duplicate_groups = [members for members in groups.values() if len(members) > 1]
        self.stdout.write(f"Exact normalized duplicate groups: {len(duplicate_groups)}")
        for members in duplicate_groups:
            survivor, *duplicates = members
            norms = sorted({norm.norm_class for member in members for norm in member.norms.all()})
            self.stdout.write("")
            self.stdout.write(f"{survivor.normalized_name or ItemNameModel.normalize_name(survivor.name)}")
            self.stdout.write(f"  survivor: {survivor.pk} {survivor.name!r}")
            self.stdout.write(f"  merge: {[item.pk for item in duplicates]}")
            self.stdout.write(f"  final norms: {', '.join(norms) or '-'}")
            for model, field, _ in references:
                counts = {
                    item.pk: model._default_manager.filter(**{f"{field}_id": item.pk}).count()
                    for item in members
                }
                if any(counts.values()):
                    self.stdout.write(f"  {model._meta.label}.{field}: {counts}")

        questionable = [item for item in items if item.name != " ".join(item.name.strip().split())]
        self.stdout.write(f"Whitespace-normalization candidates: {len(questionable)}")
        self.stdout.write("No data was changed.")
