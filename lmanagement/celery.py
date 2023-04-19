import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')

app = Celery('lmanagement')
# app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
CELERY_IMPORTS = ("tasks")
