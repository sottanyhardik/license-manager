# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('allotment', '0009_allotmentitems_created_by_allotmentitems_created_on_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='allotmentmodel',
            name='is_allotted',
            field=models.BooleanField(default=False, help_text='True if DFIA licenses are allotted'),
        ),
    ]
