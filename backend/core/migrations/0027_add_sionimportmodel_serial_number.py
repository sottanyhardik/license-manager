# Generated migration to add missing serial_number column to SIONImportModel

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_celerytasktracker'),
    ]

    operations = [
        migrations.AddField(
            model_name='sionimportmodel',
            name='serial_number',
            field=models.IntegerField(default=0),
        ),
    ]
