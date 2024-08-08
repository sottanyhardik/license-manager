from django.db import migrations


def migrate_description(apps, schema_editor):
    LicenseImportItemsModel = apps.get_model('license', 'LicenseImportItemsModel')
    for license_item in LicenseImportItemsModel.objects.all():
        if license_item.item is not None:  # Check if item is not None
            license_item.description = license_item.description
            license_item.save()


class Migration(migrations.Migration):
    dependencies = [
        ('license', '0014_licenseimportitemsmodel_description'),  # Replace with your last migration
    ]

    operations = [
        migrations.RunPython(migrate_description),
    ]
