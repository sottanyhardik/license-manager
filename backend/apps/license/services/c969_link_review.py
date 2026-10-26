"""Read-only review of C969 import lines whose saved item disagrees with their product name.

Nothing is changed here. The dashboard lists these lines so a person can review them.
"""
from collections import defaultdict

from apps.license.models import LicenseImportItemsModel
from apps.license.services.c969_product_classifier import C969_CLASSIFIERS, C969_NORM, classify_c969_product_name


def c969_link_mismatches(limit=50):
    """Lines with a saved C969 item that is not the item their product name selects."""
    saved = defaultdict(set)
    through = LicenseImportItemsModel.items.through
    for line_id, name in through.objects.filter(
        licenseimportitemsmodel__license__export_license__norm_class__norm_class=C969_NORM,
        itemnamemodel__sion_norm_class__norm_class=C969_NORM,
        itemnamemodel__name__in=C969_CLASSIFIERS,
    ).values_list("licenseimportitemsmodel_id", "itemnamemodel__name"):
        saved[line_id].add(name)
    if not saved:
        return {"count": 0, "rows": []}

    rows = []
    lines = LicenseImportItemsModel.objects.filter(id__in=list(saved)).values(
        "id", "description", "license__license_number",
    )
    for line in lines:
        expected = classify_c969_product_name(line["description"])
        stored = sorted(saved[line["id"]])
        if expected and stored != [expected]:
            rows.append({
                "import_item_id": line["id"],
                "licence_number": line["license__license_number"],
                "description": line["description"] or "",
                "saved_items": stored,
                "expected_item": expected,
            })
    rows.sort(key=lambda row: (row["licence_number"] or "", row["import_item_id"]))
    return {"count": len(rows), "rows": rows[:limit]}
