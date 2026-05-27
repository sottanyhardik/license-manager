"""
Migration: Create ActivityLog table for user action audit trail.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_fix_nullable_company_port'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('username',    models.CharField(blank=True, db_index=True, max_length=150)),
                ('action',      models.CharField(
                    choices=[
                        ('LOGIN','Login'), ('LOGOUT','Logout'), ('VIEW','View'),
                        ('CREATE','Create'), ('UPDATE','Update'), ('DELETE','Delete'),
                        ('DOWNLOAD','Download'), ('UPLOAD','Upload'),
                        ('EXPORT','Export'), ('SEARCH','Search'),
                    ],
                    db_index=True, max_length=20,
                )),
                ('module',      models.CharField(blank=True, db_index=True, max_length=60)),
                ('resource_id', models.CharField(blank=True, max_length=60)),
                ('description', models.CharField(blank=True, max_length=500)),
                ('endpoint',    models.CharField(blank=True, max_length=500)),
                ('method',      models.CharField(blank=True, max_length=10)),
                ('ip_address',  models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent',  models.CharField(blank=True, max_length=400)),
                ('status_code', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('extra',       models.JSONField(blank=True, default=dict)),
                ('timestamp',   models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='activity_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-timestamp']},
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['user', 'timestamp'], name='core_actlog_user_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['action', 'timestamp'], name='core_actlog_action_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['module', 'timestamp'], name='core_actlog_module_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='activitylog',
            index=models.Index(fields=['username', 'timestamp'], name='core_actlog_uname_ts_idx'),
        ),
    ]
