# Generated migration for adding company field to User model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),  # Ensure CompanyModel exists first
        ('accounts', '0002_alter_user_avatar'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='company',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='users',
                to='core.CompanyModel',
                help_text='The company this user belongs to. Required for ledger/license access.',
            ),
        ),
    ]
