# Generated manually - Data migration to populate is_allotted field

from django.db import migrations


def populate_is_allotted(apps, schema_editor):
    """
    Update is_allotted field for existing allotments based on whether they have allotment_details.
    """
    AllotmentModel = apps.get_model('allotment', 'AllotmentModel')
    AllotmentItems = apps.get_model('allotment', 'AllotmentItems')

    # Get all allotment IDs that have details
    allotted_ids = AllotmentItems.objects.values_list('allotment_id', flat=True).distinct()

    # Update allotments with details to is_allotted=True
    updated_count = AllotmentModel.objects.filter(id__in=allotted_ids).update(is_allotted=True)

    print(f"Updated {updated_count} allotments to is_allotted=True")

    # Explicitly set is_allotted=False for allotments without details (optional, already default)
    not_allotted_count = AllotmentModel.objects.exclude(id__in=allotted_ids).update(is_allotted=False)

    print(f"Updated {not_allotted_count} allotments to is_allotted=False")


def reverse_populate_is_allotted(apps, schema_editor):
    """
    Reverse migration - set all is_allotted to False
    """
    AllotmentModel = apps.get_model('allotment', 'AllotmentModel')
    AllotmentModel.objects.all().update(is_allotted=False)


class Migration(migrations.Migration):

    dependencies = [
        ('allotment', '0010_add_is_allotted_field'),
    ]

    operations = [
        migrations.RunPython(populate_is_allotted, reverse_populate_is_allotted),
    ]
