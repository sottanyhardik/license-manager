"""
Data migration: for each AllotmentModel record with item_name_fk unset,
look up a matching ItemNameModel by name (case-insensitive) and set the FK.

Unmatched records are left with item_name_fk=NULL — the CharField is the
authoritative fallback and nothing breaks.
"""
from django.db import migrations


def populate_item_name_fk(apps, schema_editor):
    AllotmentModel = apps.get_model('allotment', 'AllotmentModel')
    ItemNameModel = apps.get_model('core', 'ItemNameModel')

    # Build lookup dict (lowercased name → id) from ItemNameModel
    item_map = {
        name.lower(): pk
        for pk, name in ItemNameModel.objects.values_list('id', 'name')
    }

    batch = []
    for allotment in AllotmentModel.objects.filter(item_name_fk__isnull=True).exclude(item_name='').only('id', 'item_name', 'item_name_fk'):
        fk_id = item_map.get(allotment.item_name.strip().lower())
        if fk_id:
            allotment.item_name_fk_id = fk_id
            batch.append(allotment)
            if len(batch) >= 500:
                AllotmentModel.objects.bulk_update(batch, ['item_name_fk'])
                batch = []

    if batch:
        AllotmentModel.objects.bulk_update(batch, ['item_name_fk'])


def reverse_populate(apps, schema_editor):
    AllotmentModel = apps.get_model('allotment', 'AllotmentModel')
    AllotmentModel.objects.update(item_name_fk=None)


class Migration(migrations.Migration):

    dependencies = [
        ('allotment', '0003_add_item_name_fk'),
    ]

    operations = [
        migrations.RunPython(populate_item_name_fk, reverse_code=reverse_populate),
    ]
