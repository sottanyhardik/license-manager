# Generated manually for RBAC implementation

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(choices=[('LICENSE_MANAGER', 'License Manager'), ('LICENSE_VIEWER', 'License Viewer'), ('ALLOTMENT_VIEWER', 'Allotment Viewer'), ('ALLOTMENT_MANAGER', 'Allotment Manager'), ('BOE_VIEWER', 'Bill of Entry Viewer'), ('BOE_MANAGER', 'Bill of Entry Manager'), ('TRADE_VIEWER', 'Trade Viewer'), ('TRADE_MANAGER', 'Trade Manager'), ('INCENTIVE_LICENSE_MANAGER', 'Incentive License Manager'), ('INCENTIVE_LICENSE_VIEWER', 'Incentive License Viewer'), ('USER_MANAGER', 'User Manager'), ('REPORT_VIEWER', 'Report Viewer')], max_length=50, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'role',
                'verbose_name_plural': 'roles',
                'ordering': ['name'],
            },
        ),
        migrations.RemoveField(
            model_name='user',
            name='role',
        ),
        migrations.AddField(
            model_name='user',
            name='roles',
            field=models.ManyToManyField(blank=True, help_text='The roles assigned to this user.', related_name='users', to='accounts.role', verbose_name='roles'),
        ),
    ]
