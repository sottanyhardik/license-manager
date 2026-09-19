# Django Development Server - Port Management Guide

## The Problem: "Error: That port is already in use"

The "port already in use" error occurs when multiple Django runserver instances compete for port 8000. This commonly happens due to:

1. **PyCharm Background Processes**: PyCharm's IDE automatically starts Django servers for debugging
2. **Multiple Manual Instances**: Running `manage.py runserver` multiple times
3. **Zombie Processes**: Processes that didn't terminate cleanly (e.g., crashed scripts)
4. **Lingering Listeners**: Previous sessions not fully cleaned up

## Current Issue Analysis

### Running Processes
```bash
# Check what's running on port 8000
lsof -i :8000 -n -P

# Check all Django processes
ps aux | grep -E "runserver|manage.py" | grep -v grep
```

### Why Port Stays In Use
1. **PyCharm Debug Mode**: Runs `manage.py runserver 127.0.0.1:8000 --noreload` automatically
2. **Multiple Listeners**: Port can have multiple processes bound to it simultaneously
3. **Incomplete Cleanup**: Some processes may still hold file descriptors after termination

---

## Solutions

### Solution 1: Use the Python Manager Script (Recommended)

This script automatically handles port conflicts and cleans up lingering processes.

```bash
# Start Django with automatic port cleanup
python3 run_django.py 8000 0.0.0.0

# Or with default settings
python3 run_django.py
```

**Features:**
- ✅ Automatically detects and kills conflicting processes
- ✅ Cross-platform (macOS, Linux, Windows)
- ✅ Color-coded output
- ✅ Environment validation
- ✅ Clean shutdown (Ctrl+C)

### Solution 2: Use the Bash Script

```bash
# Start Django
./run_django.sh 8000 0.0.0.0

# Or with defaults
./run_django.sh
```

### Solution 3: Manual Cleanup + Start

If you prefer manual control:

```bash
# Step 1: Kill all Django processes
pkill -9 -f "runserver"
pkill -9 -f "manage.py.*8000"
sleep 2

# Step 2: Verify port is free
lsof -i :8000 || echo "Port is free"

# Step 3: Start Django
cd backend
python ../../../.venv/bin/python manage.py runserver 0.0.0.0:8000
```

### Solution 4: Disable PyCharm Auto-Start

If PyCharm keeps auto-starting Django:

1. **Stop PyCharm's Run Configuration:**
   - Menu → Run → Stop (or Ctrl+F2)
   - This stops the auto-started server

2. **Disable Auto-Run:**
   - Settings → Tools → Python Integrated Tools
   - Uncheck "Run manage.py task in console"

3. **Kill any lingering processes:**
   ```bash
   pkill -9 -f "manage.py"
   ```

---

## Clean Port Release Procedure

If a port remains stuck even after killing processes:

```bash
# For macOS/Linux - Force close with SO_REUSEADDR
python3 -c "
import socket
import os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(('0.0.0.0', 8000))
    print('✓ Port 8000 is available')
except:
    print('✗ Port 8000 is still blocked')
"

# For Windows - Use alternative port
python manage.py runserver 0.0.0.0:8001
```

---

## Troubleshooting

### Issue: "Address already in use" even after killing processes

**Root Cause:** Process TCP state is in TIME_WAIT (socket not fully released)

**Solution:**
```bash
# Wait 30-60 seconds for socket to be released naturally
# OR use a different port temporarily
python run_django.py 8001

# OR modify Django settings to use SO_REUSEADDR:
# backend/config/settings.py:
WSGI_APPLICATION = 'config.wsgi.application'
```

### Issue: PyCharm keeps restarting Django after killing it

**Root Cause:** PyCharm's debug session still active

**Solution:**
1. Click "Stop" button (⏹) in PyCharm Run Console
2. Wait 2-3 seconds
3. Try to start Django manually
4. Or restart PyCharm completely

### Issue: "Address already in use" on 0.0.0.0:8000 but not 127.0.0.1:8000

**Root Cause:** One process bound to all interfaces, another to localhost

**Solution:**
```bash
# Kill both explicitly
lsof -i :8000 | awk 'NR>1 {print $2}' | xargs kill -9

# Or use a Python helper
python3 -c "
import subprocess
pids = subprocess.check_output('lsof -ti:8000', shell=True).decode().strip().split()
for pid in pids:
    subprocess.run(['kill', '-9', pid])
"
```

---

## Best Practices

### 1. Always use the Manager Script
Instead of running `manage.py runserver` directly, use:
```bash
python3 run_django.py
```

### 2. Single Django Instance Rule
- Only ONE Django server per port at a time
- Check before starting: `lsof -i :8000`
- Use different ports for multiple projects

### 3. Clean IDE Integration
- Disable PyCharm's auto-run if using manual scripts
- Use IDE Run → Stop to cleanly shut down servers
- Don't use "Run in Background" for development servers

### 4. Check Port Status Before Pushing
```bash
# Before committing, verify the dev setup
lsof -i :8000 || echo "✓ Port 8000 available"
ps aux | grep -E "runserver|manage" | wc -l  # Should show only grep
```

---

## Reference Commands

```bash
# Check port status
lsof -i :8000 -n -P          # Detailed process info
netstat -tulpn | grep 8000   # Linux alternative

# Kill specific process
kill -9 <PID>                 # Force kill
kill -TERM <PID>              # Graceful shutdown

# Kill all Django processes
pkill -9 -f "manage.py"
pkill -9 -f "runserver"

# Find Django processes
ps aux | grep -E "manage.py|runserver"
pgrep -f "manage.py"

# Test port connectivity
nc -zv 127.0.0.1 8000         # Check if listening
curl http://127.0.0.1:8000    # Check HTTP response
```

---

## Summary

| Scenario | Solution |
|----------|----------|
| First time running | `python3 run_django.py` |
| Port conflict error | `python3 run_django.py` (auto-cleanup) |
| PyCharm auto-started | Click "Stop" button, then use manager script |
| Multiple projects | Use different ports (`python3 run_django.py 8001`) |
| Can't kill process | Restart IDE or machine |

---

## Questions?

If you still get "port already in use":
1. Run `lsof -i :8000` to see what's blocking
2. Note the PID
3. Check if it's PyCharm with `ps <PID>`
4. Either kill it or click IDE's Stop button
5. Use `python3 run_django.py` to start fresh
