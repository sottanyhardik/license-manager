#!/bin/bash
# ============================================================
#  scripts/imports/fetch-and-push-sion-norms.sh
#
#  For every SION norm code currently in SionNormClassModel on
#  license-manager, fetch the full export+import detail from DGFT
#  (which blocks the production server IPs, so this must run from
#  the local Mac), then push the parsed records into:
#     - SIONExportModel
#     - SIONImportModel
#     - SionNormNote (if remarks/notes present)
#
#  The existing master-sync cron then propagates to labdhi + tractor.
#
#  Usage:
#    bash scripts/imports/fetch-and-push-sion-norms.sh           # full run
#    bash scripts/imports/fetch-and-push-sion-norms.sh --quiet   # silent (cron mode)
#    bash scripts/imports/fetch-and-push-sion-norms.sh --codes E126,A1234   # only these
# ============================================================

set -e
QUIET=""
CODES=""
for arg in "$@"; do
    case "$arg" in
        --quiet) QUIET=1 ;;
        --codes=*) CODES="${arg#*=}" ;;
        --codes) shift; CODES="$1" ;;
    esac
done

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { [ -z "$QUIET" ] && echo "→ $*"; return 0; }
ok()   { [ -z "$QUIET" ] && echo -e "${GREEN}✓${NC} $*"; return 0; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

LANDING_URL="https://www.dgft.gov.in/CP/?opt=norms-search"
COOKIE_FILE=$(mktemp -t dgft-sion-cookies)
RAW_DIR=$(mktemp -d /tmp/dgft-sion-raw-XXXXXX)
PAYLOAD_FILE=$(mktemp -t sion-payload)
trap "rm -rf $COOKIE_FILE $RAW_DIR $PAYLOAD_FILE" EXIT

# ── 1. Discover SION codes to fetch ──────────────────────────
if [ -n "$CODES" ]; then
    SION_LIST=$(echo "$CODES" | tr ',' '\n')
    log "Using explicit codes: $CODES"
else
    log "Fetching list of known SION codes from license-manager..."
    SION_LIST=$(sshpass -p admin ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR django@143.110.252.201 \
        "cd /home/django/license-manager/backend && source /home/django/license-manager/venv/bin/activate && python manage.py shell -c \"
from core.models import SionNormClassModel
for s in SionNormClassModel.objects.filter(is_active=True).values_list('norm_class', flat=True):
    print(s)
\"" 2>/dev/null | grep -v "objects imported" | grep -v "^$")
fi

SION_COUNT=$(echo "$SION_LIST" | grep -c .)
ok "Will fetch $SION_COUNT SION codes"

# ── 2. Get DGFT session + CSRF ───────────────────────────────
log "Getting DGFT session + CSRF..."
HTML=$(curl -s -k -c "$COOKIE_FILE" -A "Mozilla/5.0" "$LANDING_URL")
CSRF=$(echo "$HTML" | grep -oE 'name="_csrf"[^>]*content="[a-f0-9-]+"' | grep -oE '[a-f0-9-]{36}')
if [ -z "$CSRF" ]; then
    err "Could not get CSRF token from DGFT"
    exit 1
fi
ok "Session ready (CSRF=${CSRF:0:8}…)"

# ── 3. Fetch each SION code ─────────────────────────────────
log "Fetching SION data (sequential, ~1 req/sec to be polite)..."
FETCHED=0
FAILED=()
echo "$SION_LIST" | while IFS= read -r CODE; do
    [ -z "$CODE" ] && continue
    OUT="$RAW_DIR/${CODE}.json"
    HTTP=$(curl -s -k -b "$COOKIE_FILE" -A "Mozilla/5.0" -X POST \
        -H "accept: application/json, text/javascript, */*; q=0.01" \
        -H "content-length: 0" \
        -H "origin: https://www.dgft.gov.in" \
        -H "referer: $LANDING_URL" \
        -H "x-requested-with: XMLHttpRequest" \
        "https://www.dgft.gov.in/CP/webHP?requestType=ApplicationRH&actionVal=exportImportDetail&screenId=90000534&sion=${CODE}&_csrf=${CSRF}" \
        -o "$OUT" -w "%{http_code}")
    if [ "$HTTP" = "200" ] && [ -s "$OUT" ] && head -c 1 "$OUT" | grep -q "[\[{]"; then
        FETCHED=$((FETCHED+1))
        [ -z "$QUIET" ] && printf "  ✓ %-12s (%d bytes)\n" "$CODE" "$(wc -c < $OUT)"
    else
        [ -z "$QUIET" ] && printf "  ✗ %-12s HTTP=%s\n" "$CODE" "$HTTP"
    fi
    sleep 0.6
done
ok "Fetch loop complete"

# ── 4. Parse all responses into a single JSON payload ───────
log "Parsing responses..."
/usr/bin/python3 << PY
import json, os, re, sys
RAW_DIR = "$RAW_DIR"
out = {}
for fn in sorted(os.listdir(RAW_DIR)):
    code = fn.replace('.json', '')
    try:
        rows = json.load(open(os.path.join(RAW_DIR, fn)))
    except Exception:
        continue
    if not rows or not isinstance(rows, list):
        continue
    first = rows[0]
    description = first.get('description') or first.get('exportItemName') or ''
    head_name   = first.get('exportProductGroup') or ''
    exports = []
    imports = []
    remarks = set()
    for i, r in enumerate(rows, start=1):
        ex_name = (r.get('exportItemName') or '').strip()
        ex_qty  = r.get('qtyExportItem')
        ex_uom  = r.get('uomExport')
        if ex_name and not any(e['description'] == ex_name for e in exports):
            exports.append({'description': ex_name, 'quantity': ex_qty, 'unit': ex_uom})
        im_name = (r.get('importItemName') or '').strip()
        im_qty  = r.get('qtyImportItem')
        im_uom  = r.get('uomImport')
        if im_name:
            imports.append({
                'serial_number': i,
                'description': im_name,
                'quantity': im_qty,
                'unit': im_uom,
                'hsn_code': None,
                'condition': '',
            })
        rk = (r.get('remarks') or '').strip()
        if rk: remarks.add(rk)
    out[code] = {
        'description': description,
        'head_name': head_name,
        'exports': exports,
        'imports': imports,
        'notes': sorted(remarks),
    }
json.dump(out, open("$PAYLOAD_FILE", 'w'), indent=2)
print(f"Parsed {len(out)} SION norms")
PY

# ── 5. Push to all 3 servers ────────────────────────────────
#
# Push directly to each server (master_sync doesn't handle SION child tables).
# We write the Python import script to a file and SCP it over — running
# `manage.py shell < file.py` avoids all the shell-quoting hell that comes
# with `manage.py shell -c "…"`.

PY_TEMPLATE=$(mktemp -t sion-import)
cat > "$PY_TEMPLATE" << 'PY'
# Standalone Django script — bootstrap Django, then run.
import os, sys, django
sys.path.insert(0, '/home/django/license-manager/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

import json
from decimal import Decimal, InvalidOperation
from core.models import HeadSIONNormsModel, SionNormClassModel, SIONExportModel, SIONImportModel, SionNormNote

PAYLOAD_REMOTE_PATH = '__PAYLOAD_PATH__'
data = json.load(open(PAYLOAD_REMOTE_PATH))

def dec(v, default='0'):
    try: return Decimal(str(v if v not in (None, '') else default))
    except (InvalidOperation, TypeError): return Decimal(default)

ex_created = im_created = note_created = sion_updated = head_created = 0
skipped_unknown_sion = 0

for code, payload in data.items():
    sion = SionNormClassModel.objects.filter(norm_class=code).first()
    if not sion:
        skipped_unknown_sion += 1
        continue
    changed = False
    if payload['description'] and sion.description != payload['description']:
        sion.description = payload['description']
        changed = True
    if payload['head_name']:
        head, h_created = HeadSIONNormsModel.objects.get_or_create(name=payload['head_name'])
        if h_created: head_created += 1
        if sion.head_norm_id != head.id:
            sion.head_norm = head
            changed = True
    if changed:
        sion.save()
        sion_updated += 1
    SIONExportModel.objects.filter(norm_class=sion).delete()
    SIONImportModel.objects.filter(norm_class=sion).delete()
    SionNormNote.objects.filter(sion_norm=sion).delete()
    for e in payload['exports']:
        SIONExportModel.objects.create(
            norm_class=sion,
            description=(e['description'] or '')[:500],
            quantity=dec(e['quantity']),
            unit=(e['unit'] or '')[:50],
        )
        ex_created += 1
    for i in payload['imports']:
        SIONImportModel.objects.create(
            serial_number=i['serial_number'],
            norm_class=sion,
            hsn_code=None,
            description=(i['description'] or '')[:500],
            quantity=dec(i['quantity']),
            unit=(i['unit'] or '')[:50],
            condition=(i['condition'] or '')[:255],
        )
        im_created += 1
    for idx, note in enumerate(payload['notes'], start=1):
        SionNormNote.objects.create(sion_norm=sion, note_text=note, display_order=idx)
        note_created += 1

print(f'SION updated:{sion_updated} heads_created:{head_created} '
      f'exports:{ex_created} imports:{im_created} notes:{note_created} '
      f'skipped:{skipped_unknown_sion}')
PY

for entry in "143.110.252.201:license-manager" "139.59.92.226:labdhi" "165.232.185.220:tractor"; do
    IFS=':' read -r IP LABEL <<< "$entry"
    log "Pushing to $LABEL ($IP)..."
    REMOTE_PAYLOAD="/tmp/sion-payload-$$.json"
    REMOTE_SCRIPT="/tmp/sion-import-$$.py"

    # Substitute the remote payload path into the script before uploading
    PY_REAL=$(mktemp -t sion-import-real)
    sed "s|__PAYLOAD_PATH__|$REMOTE_PAYLOAD|g" "$PY_TEMPLATE" > "$PY_REAL"

    sshpass -p admin scp -o StrictHostKeyChecking=no -o LogLevel=ERROR "$PAYLOAD_FILE" "django@$IP:$REMOTE_PAYLOAD" >/dev/null
    sshpass -p admin scp -o StrictHostKeyChecking=no -o LogLevel=ERROR "$PY_REAL"      "django@$IP:$REMOTE_SCRIPT"  >/dev/null

    # Run the script as a standalone Python program (NOT via manage.py shell)
    RESULT=$(sshpass -p admin ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR django@$IP \
        "cd /home/django/license-manager/backend && source /home/django/license-manager/venv/bin/activate && python $REMOTE_SCRIPT 2>&1" \
        | grep -E "SION updated|Error|Traceback" | tail -5)

    sshpass -p admin ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR django@$IP \
        "rm -f $REMOTE_PAYLOAD $REMOTE_SCRIPT"
    rm -f "$PY_REAL"

    if echo "$RESULT" | grep -qE "Error|Traceback"; then
        err "  $LABEL: $RESULT"
    else
        ok "  $LABEL: $RESULT"
    fi
done

rm -f "$PY_TEMPLATE"
ok "Done — all 3 servers updated"
