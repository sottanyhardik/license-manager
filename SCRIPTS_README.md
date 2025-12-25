# Deployment Scripts Guide

This directory contains all the deployment and management scripts for the License Manager application.

---

## 📋 Available Scripts

### 1. **auto-deploy.sh** - Primary Deployment Tool
**Purpose**: Deploy latest code to production servers (automated deployment)

**What it does**:
- Pulls latest code from `version-4.1` branch
- Builds frontend (npm install + build)
- Installs Python dependencies
- Runs database migrations (with auto-fix for permissions)
- Collects static files
- Restarts all services (gunicorn, celery, nginx)
- Verifies deployment with health checks

**Usage**:
```bash
./auto-deploy.sh
```

**Servers**: 143.110.252.201, 139.59.92.226
**Time**: 10-20 minutes (both servers)
**Prerequisites**: SSH access with password `admin`

---

### 2. **verify-deployment.sh** - Pre-Deployment Checker
**Purpose**: Validate all prerequisites before deployment

**What it checks**:
- Local git status and branch
- Uncommitted changes
- Remote sync status
- Frontend/backend configuration files
- SSH connectivity to all servers
- Server disk space and services

**Usage**:
```bash
./verify-deployment.sh
```

**When to use**: Run BEFORE `auto-deploy.sh` to ensure everything is ready

---

### 3. **db-tools.sh** - Database Management Utility
**Purpose**: Unified tool for all database operations

**Commands**:
```bash
# Create backup of remote database
./db-tools.sh backup

# Download database from server to local
./db-tools.sh download

# Restore database from backup file
./db-tools.sh restore backups/backup_20241225.sql

# Download and restore in one command
./db-tools.sh sync
```

**Features**:
- Automatic backup creation
- Safe restore with warnings
- Backup file management
- Migration execution

---

### 4. **sync-media.sh** - Media Files Sync
**Purpose**: Sync media files from production to local development

**What it does**:
- Downloads all media files from production server
- Uses rsync for efficient transfer
- Deletes old local media first (with confirmation)
- Excludes unnecessary files (.pyc, __pycache__, .DS_Store)

**Usage**:
```bash
./sync-media.sh
```

**Server**: 143.110.252.201
**Local path**: backend/media/

---

### 5. **start-server.sh** - Manual Server Startup
**Purpose**: Start server manually (for 64.227.129.26)

**What it does**:
- Starts Gunicorn with 3 workers
- Starts Nginx
- Verifies both services are running
- Tests HTTP response

**Usage** (on server):
```bash
ssh django@64.227.129.26
cd /home/django/license-manager
./start-server.sh
```

**Note**: This is for a different server than auto-deploy.sh

---

### 6. **setup-labdhi-server.sh** - Initial Server Setup
**Purpose**: One-time server setup for new servers

**What it installs**:
- System packages (Python, PostgreSQL, Node.js, Nginx)
- Python virtual environment
- PostgreSQL database and user
- Supervisor configuration
- Nginx configuration
- Frontend dependencies

**Usage** (on new server):
```bash
./setup-labdhi-server.sh
```

**When to use**: Only when setting up a brand new server

---

### 7. **setup-ssl-labdhi.sh** - SSL Certificate Setup
**Purpose**: Configure HTTPS with Let's Encrypt certificates

**What it does**:
- Installs certbot
- Obtains SSL certificates for domain
- Configures Nginx for HTTPS
- Sets up automatic renewal

**Usage** (on server):
```bash
./setup-ssl-labdhi.sh
```

**Domain**: labdhi.duckdns.org
**When to use**: After initial server setup, to enable HTTPS

---

## 🚀 Typical Workflows

### Daily Development Workflow
```bash
# 1. Sync database from production
./db-tools.sh sync

# 2. Sync media files
./sync-media.sh

# 3. Start local development
cd backend
python manage.py runserver
```

### Deployment Workflow
```bash
# 1. Commit and push changes
git add .
git commit -m "Your changes"
git push origin version-4.1

# 2. Verify deployment readiness
./verify-deployment.sh

# 3. Deploy to production
./auto-deploy.sh
```

### New Server Setup Workflow
```bash
# On new server:
# 1. Initial setup
./setup-labdhi-server.sh

# 2. Configure SSL
./setup-ssl-labdhi.sh

# 3. Deploy code
./auto-deploy.sh
```

### Database Backup Workflow
```bash
# Regular backup
./db-tools.sh backup

# Download for local testing
./db-tools.sh download

# Restore from specific backup
./db-tools.sh restore backups/backup_20241225.sql
```

---

## 📁 Directory Structure

```
license-manager/
├── auto-deploy.sh          # Main deployment script
├── verify-deployment.sh    # Pre-deployment checks
├── db-tools.sh            # Database management
├── sync-media.sh          # Media sync utility
├── start-server.sh        # Manual server start
├── setup-labdhi-server.sh # Initial server setup
├── setup-ssl-labdhi.sh    # SSL configuration
└── backups/               # Database backups (created by db-tools.sh)
```

---

## ⚙️ Configuration

### Server Details

| Server IP        | Purpose    | Database         | User   |
|------------------|------------|------------------|--------|
| 143.110.252.201  | Production | license_manager_db | django |
| 139.59.92.226    | Production | lmanagement      | django |
| 64.227.129.26    | Staging    | lmanagement      | django |

### Branch
- **Deployment branch**: `version-4.1`
- **Main branch**: `develop`

---

## 🔧 Troubleshooting

### Deployment fails with "permission denied"
```bash
# Check SSH access
ssh django@143.110.252.201

# Verify password is correct (default: admin)
```

### Database restore fails
```bash
# Check PostgreSQL is running locally
brew services list | grep postgresql

# Verify database credentials in db-tools.sh
```

### Frontend build fails
```bash
# Check Node.js version (need v16+)
node --version

# Clear npm cache
cd frontend
rm -rf node_modules
npm install
```

### Services not restarting
```bash
# SSH to server and check manually
ssh django@139.59.92.226
sudo supervisorctl status
sudo systemctl status nginx
```

---

## 🔒 Security Notes

⚠️  **Password**: Currently hardcoded as `admin` in scripts
⚠️  **Database credentials**: Exposed in db-tools.sh
⚠️  **Backup files**: Contains production data, handle securely

**Recommendations**:
1. Use environment variables for passwords
2. Add `.env` file support
3. Encrypt sensitive backup files
4. Rotate passwords regularly

---

## 📝 Maintenance

### Regular Tasks
- **Daily**: Database backups via `db-tools.sh backup`
- **Weekly**: Check disk space on servers
- **Monthly**: Review and clean old backup files
- **Quarterly**: Update SSL certificates (auto-renewed)

### Backup Retention
- Keep last 7 daily backups
- Keep last 4 weekly backups
- Keep last 3 monthly backups

---

## 🆘 Emergency Procedures

### Rollback Deployment
```bash
# SSH to affected server
ssh django@139.59.92.226
cd /home/django/license-manager

# Revert to previous commit
git log --oneline -5  # Find previous commit
git checkout <commit-hash>

# Rebuild and restart
cd frontend && npm run build
sudo supervisorctl restart license-manager
sudo systemctl reload nginx
```

### Restore Database from Backup
```bash
# Find latest backup
ls -lht backups/ | head -5

# Restore
./db-tools.sh restore backups/backup_YYYYMMDD_HHMMSS.sql
```

---

## 📚 Related Documentation

- **REFACTORING.md** - Code refactoring details
- **backend/CELERY_SETUP.md** - Celery configuration
- **frontend/README.md** - Frontend build process

---

**Last Updated**: December 25, 2024
**Version**: 4.1
**Maintainer**: License Manager Team
