# Run All Configuration Guide

## Overview

The **"Run All (React + Beat; backend/worker launchd)"** configuration is the recommended way to run the entire development stack with a single command.

## What Gets Started

When you run the "Run All" configuration, it automatically starts:

1. **Django Debug Server** (Port 8000)
   - Backend API server
   - Auto-reloads on code changes
   - Debugging support enabled

2. **React/Vite Dev Server** (Port 5173)
   - Frontend development server
   - Hot module replacement (HMR)
   - CSS modules and modern tooling

3. **Celery Beat**
   - Task scheduler
   - Handles periodic tasks
   - Required for background job scheduling

4. **Celery Worker**
   - Background job processor
   - Processes async tasks
   - Required for file uploads, exports, etc.

## How to Use

### In PyCharm

1. **Select the Run Configuration:**
   - Top-right dropdown: `Run All (React + Beat; backend/worker launchd)`

2. **Start the Application:**
   - Click the ▶️ (Run) button, or
   - Press `Ctrl+R` (Mac: `⌘R`)

3. **Monitor All Services:**
   - View → Tool Windows → Run
   - Each service's output appears in separate tabs
   - Look for: "Started development server at http://0.0.0.0:8000"

4. **Stop All Services:**
   - Click the ⏹️ (Stop) button, or
   - Press `Ctrl+F2` (Mac: `⌘F2`)

### From Command Line

If you prefer to run services individually:

```bash
# Terminal 1: Django backend
cd backend
python manage.py runserver 0.0.0.0:8000

# Terminal 2: React frontend
cd frontend
npm run dev

# Terminal 3: Celery beat
celery -A lmanagement beat -l info

# Terminal 4: Celery worker
celery -A lmanagement worker -Q default --loglevel=info --pool=solo
```

## Port Mapping

| Service | Port | URL |
|---------|------|-----|
| Django API | 8000 | http://localhost:8000/ |
| React Vite | 5173 | http://localhost:5173/ |
| PostgreSQL | 5432 | localhost:5432 |

## Configuration Details

The run configuration is defined in:
```
.idea/runConfigurations/Run_All__React___Beat__backend_worker_launchd_.xml
```

**Includes:**
- Django: debug runserver (8000)
- React: Vite dev
- Celery: beat
- Celery: worker

## Troubleshooting

### Error: "Port 8000 already in use"

**Solution 1:** Kill existing processes
```bash
lsof -i :8000 -t | xargs kill -9
```

**Solution 2:** Use a different port
```bash
# Modify the run config to use port 8001 instead
# Or run Django directly:
cd backend && python manage.py runserver 0.0.0.0:8001
```

**Solution 3:** Check what's using the port
```bash
lsof -i :8000 -n -P
```

### React dev server not working

Check that port 5173 is available:
```bash
lsof -i :5173 || echo "Port 5173 is free"
```

### Celery tasks not processing

Verify both beat and worker are running in the Run tool windows. Check for errors in their output tabs.

### Database connection errors

Ensure PostgreSQL is running:
```bash
# Check if PostgreSQL is running
psql -U lmanagement -d lmanagement -c "SELECT 1;"

# Start PostgreSQL if using Homebrew
brew services start postgresql
```

## Best Practices

### ✅ Do

- Use "Run All" for full-stack development
- Monitor all four service windows in the Run tool
- Stop cleanly with the ⏹️ button
- Check service logs for errors
- Keep IDE and backend in sync

### ❌ Don't

- Don't use "Django: debug runserver (8000)" alone (missing workers)
- Don't manually start `manage.py runserver` while "Run All" is active
- Don't leave multiple instances running on the same port
- Don't kill terminal processes with Ctrl+C (use IDE Stop button)

## Accessing the Application

### Frontend
- URL: http://localhost:5173/
- Proxy: Automatically forwards API calls to http://localhost:8000

### Backend API
- URL: http://localhost:8000/
- Admin: http://localhost:8000/admin/
- Credentials: See `.env` file or ask team lead

### API Documentation
- Swagger UI: http://localhost:8000/api/schema/swagger/
- ReDoc: http://localhost:8000/api/schema/redoc/

## Development Workflow

1. **Start "Run All"** configuration
2. **Edit code** in any service
3. **Services auto-reload** (Django/Vite)
4. **View changes** in browser (with live reload)
5. **Check console** for errors
6. **Stop "Run All"** when done

## Performance Tips

- If the IDE slows down with all 4 services:
  - Close unnecessary IDE panels
  - Reduce background tasks in settings
  - Consider running some services in separate terminals

- If you only need frontend:
  ```bash
  # Run only React
  cd frontend && npm run dev
  ```

- If you only need backend:
  ```bash
  # Run Django only (for API development)
  cd backend && python manage.py runserver 0.0.0.0:8000
  ```

## Environment Variables

The configuration sets:
- `PYTHONUNBUFFERED=1` - Real-time Python output
- `DJANGO_SETTINGS_MODULE=lmanagement.settings` - Django config
- `DEBUG=True` - Development mode enabled

Edit `.idea/runConfigurations/Run_All__React___Beat__backend_worker_launchd_.xml` to customize environment variables.

## Summary

**The "Run All" configuration is your one-click solution to start the entire development stack.**

Never use Django debug runserver alone—use the "Run All" configuration instead!
