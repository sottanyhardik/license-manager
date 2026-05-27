from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('license', '0028_alter_licenseexportitemmodel_unit_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensedetailsmodel',
            name='last_ownership_fetch',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
