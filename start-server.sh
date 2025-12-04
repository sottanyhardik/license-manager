#!/bin/bash

# Start Server Script for License Manager
# Server: 64.227.129.26

set -e

echo "========================================="
echo "Starting License Manager Server"
echo "========================================="
echo "Started at: $(date)"
echo ""

# Step 1: Start Gunicorn
echo "[1/4] Starting Gunicorn..."
cd /home/django/license-manager/backend

# Check if gunicorn is already running
if pgrep -f "gunicorn.*lmanagement.wsgi" > /dev/null; then
    echo "Gunicorn is already running. Stopping it first..."
    pkill -f "gunicorn.*lmanagement.wsgi" || true
    sleep 2
fi

# Activate virtual environment and start gunicorn in background
source /home/django/license-manager/venv/bin/activate
nohup gunicorn --workers 3 --bind 0.0.0.0:8000 lmanagement.wsgi:application > /home/django/license-manager/logs/gunicorn.log 2>&1 &

echo "Gunicorn started with PID: $!"
sleep 3

# Step 2: Verify Gunicorn is running
echo "[2/4] Verifying Gunicorn..."
if pgrep -f "gunicorn.*lmanagement.wsgi" > /dev/null; then
    echo "✅ Gunicorn is running"
    ps aux | grep gunicorn | grep -v grep | head -3
else
    echo "❌ ERROR: Gunicorn failed to start"
    echo "Check logs: tail -f /home/django/license-manager/logs/gunicorn.log"
    exit 1
fi

# Step 3: Test if Gunicorn responds
echo "[3/4] Testing Gunicorn response..."
sleep 2
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200\|302\|301"; then
    echo "✅ Gunicorn is responding on port 8000"
else
    echo "⚠️  WARNING: Gunicorn may not be responding correctly"
fi

# Step 4: Start Nginx
echo "[4/4] Starting Nginx..."
sudo systemctl start nginx
sudo systemctl enable nginx

# Verify Nginx
if sudo systemctl is-active --quiet nginx; then
    echo "✅ Nginx is running"
else
    echo "❌ ERROR: Nginx failed to start"
    echo "Check nginx config: sudo nginx -t"
    echo "Check nginx logs: sudo tail -f /var/log/nginx/error.log"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ Server Started Successfully!"
echo "========================================="
echo ""
echo "Service Status:"
echo "---------------"
echo "Gunicorn: $(pgrep -f 'gunicorn.*lmanagement.wsgi' > /dev/null && echo '✅ Running' || echo '❌ Not running')"
echo "Nginx: $(sudo systemctl is-active nginx 2>/dev/null | grep -q 'active' && echo '✅ Running' || echo '❌ Not running')"
echo ""
echo "Your server should be accessible at:"
echo "  - http://64.227.129.26"
echo "  - http://labdhi.duckdns.org"
echo ""
echo "Logs:"
echo "  Gunicorn: tail -f /home/django/license-manager/logs/gunicorn.log"
echo "  Nginx: sudo tail -f /var/log/nginx/error.log"
echo ""
