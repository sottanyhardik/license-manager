# Celery Setup for License Manager

## Overview
Celery is configured to run the `sync_licenses` command automatically every day at 12:00 AM IST.

## Scheduled Tasks

### 1. Daily License Sync (12:00 AM IST)
- **Task:** `license.tasks.sync_all_licenses`
- **Schedule:** Every day at 12:00 AM IST (18:30 UTC)
- **Function:** Updates balance_cif, flags, and import item balances for ALL licenses

## Running Celery

### Start Celery Worker
```bash
cd backend
celery -A lmanagement worker --loglevel=info
```

### Start Celery Beat (Scheduler)
```bash
cd backend
celery -A lmanagement beat --loglevel=info
```

### Run Both Together (Development)
```bash
cd backend
celery -A lmanagement worker --beat --loglevel=info
```

## Manual Task Execution

### Test the sync task manually:
```python
from license.tasks import sync_all_licenses

# Run synchronously
result = sync_all_licenses()
print(result)
```

### Or via Celery:
```python
from license.tasks import sync_all_licenses

# Run asynchronously
task = sync_all_licenses.delay()
print(f"Task ID: {task.id}")
print(f"Task State: {task.state}")
```

## Production Deployment

### Using Systemd (Recommended)

#### 1. Celery Worker Service
Create `/etc/systemd/system/celery-worker.service`:
```ini
[Unit]
Description=Celery Worker for License Manager
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/license-manager/backend
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A lmanagement worker --loglevel=info --logfile=/var/log/celery/worker.log --pidfile=/var/run/celery/worker.pid

[Install]
WantedBy=multi-user.target
```

#### 2. Celery Beat Service
Create `/etc/systemd/system/celery-beat.service`:
```ini
[Unit]
Description=Celery Beat Scheduler for License Manager
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/license-manager/backend
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A lmanagement beat --loglevel=info --logfile=/var/log/celery/beat.log --pidfile=/var/run/celery/beat.pid

[Install]
WantedBy=multi-user.target
```

#### 3. Enable and Start
```bash
sudo systemctl enable celery-worker celery-beat
sudo systemctl start celery-worker celery-beat
sudo systemctl status celery-worker celery-beat
```

## Monitoring

### Check Celery Status
```bash
celery -A lmanagement inspect active
celery -A lmanagement inspect scheduled
celery -A lmanagement inspect stats
```

### View Logs
```bash
# Worker logs
tail -f /var/log/celery/worker.log

# Beat logs
tail -f /var/log/celery/beat.log

# Django logs (for task execution)
tail -f /path/to/django.log
```

## Task Details

### `sync_all_licenses` Task
- **Location:** `backend/license/tasks.py`
- **Command:** Calls `python manage.py sync_licenses`
- **Batch Size:** 100 licenses per batch
- **Updates:**
  - `balance_cif` - Recalculated from exports/imports/allotments/BOE
  - `is_null` - Set based on balance < $500
  - `is_expired` - Set based on expiry_date < today
  - Import item fields (available_quantity, available_value, etc.)

### Task Output
The task returns a dict with:
```python
{
    'status': 'success' or 'error',
    'output': 'command output',
    'timestamp': 'ISO timestamp',
    'error': 'error message if failed'
}
```

## Troubleshooting

### Task Not Running
1. Check if Celery Beat is running: `systemctl status celery-beat`
2. Check Beat schedule: `celery -A lmanagement inspect scheduled`
3. Check logs for errors

### Task Failed
1. Check Django logs for errors
2. Run command manually: `python manage.py sync_licenses --dry-run`
3. Check database connectivity
4. Verify task registration: `celery -A lmanagement inspect registered`

### Timezone Issues
- Server must use UTC timezone
- Celery Beat schedule is in UTC (18:30 UTC = 12:00 AM IST)
- Django settings: `USE_TZ = True`

## Requirements

Ensure these are in `requirements.txt`:
```txt
celery>=5.3.0
redis>=5.0.0  # or your broker
django-celery-results>=2.5.0  # optional, for result backend
```

## Environment Variables

Set in `.env` or `settings.py`:
```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
```
