#!/bin/bash

# Setup sudoers configuration for django user
# Run this ONCE on the server as root or with sudo access

echo "🔧 Setting up passwordless sudo for deployment tasks..."

# Create sudoers file for django user
sudo tee /etc/sudoers.d/django-deploy > /dev/null <<'EOF'
# Allow django user to run specific commands without password for deployment
django ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl restart license-manager
django ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl restart license-manager-celery
django ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl restart license-manager-celery-beat
django ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl status
django ALL=(ALL) NOPASSWD: /usr/bin/supervisorctl status license-manager*
django ALL=(ALL) NOPASSWD: /bin/systemctl reload nginx
django ALL=(ALL) NOPASSWD: /bin/systemctl restart nginx
django ALL=(ALL) NOPASSWD: /bin/systemctl status nginx
django ALL=(ALL) NOPASSWD: /bin/chown -R django\:django /home/django/license-manager/backend/media
django ALL=(ALL) NOPASSWD: /bin/chown -R django\:django /home/django/license-manager/frontend/dist
django ALL=(ALL) NOPASSWD: /bin/chmod -R * /home/django/license-manager/backend/media
django ALL=(ALL) NOPASSWD: /bin/chmod -R * /home/django/license-manager/frontend/dist
EOF

# Set proper permissions on sudoers file
sudo chmod 0440 /etc/sudoers.d/django-deploy

# Validate sudoers file
if sudo visudo -c -f /etc/sudoers.d/django-deploy; then
    echo "✅ Sudoers configuration created successfully!"
    echo ""
    echo "The django user can now run the following commands without password:"
    echo "  - supervisorctl restart/status for license-manager services"
    echo "  - systemctl reload/restart/status nginx"
    echo "  - chown/chmod for deployment directories"
else
    echo "❌ Error: Sudoers configuration is invalid!"
    sudo rm -f /etc/sudoers.d/django-deploy
    exit 1
fi
