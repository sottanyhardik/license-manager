#!/usr/bin/env bash
set -euo pipefail

# ====== CONFIGURATION ======
VENV_DIR="/Users/hardiksottany/PycharmProjects/license-manager/.venv"
PY_BIN="$VENV_DIR/bin/python"
MANAGE="/Users/hardiksottany/PycharmProjects/license-manager/manage.py"
# ============================

echo "⚙️ Activating virtual environment..."
if [ -f "$VENV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
else
  echo "❌ Virtual environment not found at $VENV_DIR"
  exit 1
fi

echo "🧠 Checking Django DB settings..."
DB_ENGINE=$($PY_BIN $MANAGE shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])")
DB_NAME=$($PY_BIN $MANAGE shell -c "from django.conf import settings; print(settings.DATABASES['default']['NAME'])")

echo "Database engine: $DB_ENGINE"
echo "Database name: $DB_NAME"
echo

echo "📦 Backing up current django_migrations table..."
BACKUP_FILE="django_migrations_backup_$(date +%Y%m%d_%H%M%S).csv"
$PY_BIN $MANAGE dbshell <<EOF || true
.output $BACKUP_FILE
SELECT * FROM django_migrations;
EOF
echo "✅ Backup saved to $BACKUP_FILE"

echo
echo "⚠️  Deleting 'django_migrations' table from database '$DB_NAME'..."

if [[ "$DB_ENGINE" == *"sqlite3"* ]]; then
  echo "Detected SQLite database."
  $PY_BIN $MANAGE dbshell <<'EOF'
DROP TABLE IF EXISTS django_migrations;
EOF

elif [[ "$DB_ENGINE" == *"postgresql"* ]]; then
  echo "Detected PostgreSQL database."
  $PY_BIN $MANAGE dbshell <<'EOF'
DROP TABLE IF EXISTS django_migrations CASCADE;
EOF

elif [[ "$DB_ENGINE" == *"mysql"* ]]; then
  echo "Detected MySQL database."
  $PY_BIN $MANAGE dbshell <<'EOF'
DROP TABLE IF EXISTS django_migrations;
EOF

else
  echo "❌ Unknown or unsupported DB engine: $DB_ENGINE"
  exit 1
fi

echo "✅ 'django_migrations' table dropped successfully."

echo
echo "📜 Rebuilding migration history..."
$PY_BIN $MANAGE makemigrations --noinput
$PY_BIN $MANAGE migrate --fake-initial --noinput

echo
echo "🎉 Done! Database schema and migration table are now consistent."
echo "You can verify with:"
echo "   $PY_BIN $MANAGE showmigrations"
