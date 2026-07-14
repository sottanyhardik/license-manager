#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PWD}"
BACKUP_DIR="${HOME}/pip-backups"
TIMESTAMP="$(date +%F_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/requirements-${TIMESTAMP}.txt"
LOG_DIR="${BACKUP_DIR}/logs"
OUTDATED_JSON="${BACKUP_DIR}/outdated-${TIMESTAMP}.json"
OUTDATED_LIST="${BACKUP_DIR}/outdated-names-${TIMESTAMP}.txt"
UPGRADE_LOG="${LOG_DIR}/upgrade-${TIMESTAMP}.log"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"

echo "1) Make sure virtualenv is activated. (already activated?)"
echo "2) Backing up current installed packages to ${BACKUP_FILE}"
pip freeze > "$BACKUP_FILE"

echo "3) Upgrading pip, setuptools and wheel"
python -m pip install --upgrade pip setuptools wheel | tee -a "$UPGRADE_LOG"

echo "4) Listing outdated packages (json) to ${OUTDATED_JSON}"
pip list --outdated --format=json > "$OUTDATED_JSON"

# Build a simple newline-separated package name list
python - <<PY > "$OUTDATED_LIST"
import json,sys
data = json.load(open("$OUTDATED_JSON"))
# write package names only
with open("$OUTDATED_LIST", "w") as f:
    for pkg in data:
        f.write(pkg["name"] + "\n")
print(f"Wrote {len(data)} outdated package names to $OUTDATED_LIST")
PY

if [[ ! -s "$OUTDATED_LIST" ]]; then
  echo "No outdated packages. Nothing to upgrade."
  exit 0
fi

echo "Packages to upgrade (from $OUTDATED_LIST):"
cat "$OUTDATED_LIST"
echo

echo "5) Upgrading packages (logging to ${UPGRADE_LOG})"
while IFS= read -r pkg; do
  echo "---- upgrading: $pkg ----" | tee -a "$UPGRADE_LOG"
  if pip install -U "$pkg" >> "$UPGRADE_LOG" 2>&1; then
    echo "OK: $pkg" | tee -a "$UPGRADE_LOG"
  else
    echo "ERROR upgrading $pkg (see ${UPGRADE_LOG}). Continuing." | tee -a "$UPGRADE_LOG"
  fi
done < "$OUTDATED_LIST"

echo
echo "6) Post-upgrade tasks:"
echo " - Run tests: python manage.py test"
echo " - Migrate: python manage.py migrate"
echo " - Collectstatic (if used): python manage.py collectstatic --noinput"
echo
echo "Rollback: pip install -r ${BACKUP_FILE}"
echo "Logs: ${UPGRADE_LOG}"
echo "Done."