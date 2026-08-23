#!/bin/bash
# ============================================================
#  scripts/imports/fetch-all-sion-from-dgft.sh
#
#  Fetch the COMPLETE catalog of SION norms (~2074 codes across
#  12 product groups) from DGFT, then push to all 3 servers.
#
#  Resumable — if /tmp/dgft-sion-raw/<CODE>.json already exists
#  it's skipped, so you can re-run safely after a network blip.
#
#  Usage:
#    bash scripts/imports/fetch-all-sion-from-dgft.sh            # full catalog
#    bash scripts/imports/fetch-all-sion-from-dgft.sh --groups E,A   # limit to letters
#    bash scripts/imports/fetch-all-sion-from-dgft.sh --dry-run  # fetch only, don't push
# ============================================================

set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}→${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

LIMIT_LETTERS=""
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --groups=*) LIMIT_LETTERS="${arg#*=}" ;;
        --dry-run)  DRY_RUN=1 ;;
    esac
done

RAW_DIR="/tmp/dgft-sion-raw"
mkdir -p "$RAW_DIR"
LANDING_URL="https://www.dgft.gov.in/CP/?opt=norms-search"
COOKIE_FILE=$(mktemp -t dgft-sion-cookies)
PAYLOAD_FILE=$(mktemp -t sion-full-payload)
trap "rm -f $COOKIE_FILE $PAYLOAD_FILE" EXIT

# Product groups (id:letter:name)
PRODUCT_GROUPS=(
    "62:A:Chemical and Allied Products"
    "83:B:Electronic Products"
    "61:C:Engineering Products"
    "66:D:Fish and marine Products"
    "67:E:Food Products"
    "68:F:Handicraft Products"
    "64:G:Leather Products"
    "63:H:Plastic Products"
    "65:I:Sports Goods"
    "71:J:Textile Products"
    "90:K:Miscellaneous Products"
    "99:M:Gem and Jewellery Products"
)

# ── 1. Get DGFT session + CSRF ──────────────────────────────
log "Establishing DGFT session..."
HTML=$(curl -s -k -c "$COOKIE_FILE" -A "Mozilla/5.0" "$LANDING_URL")
CSRF=$(echo "$HTML" | grep -oE 'name="_csrf"[^>]*content="[a-f0-9-]+"' | grep -oE '[a-f0-9-]{36}')
[ -z "$CSRF" ] && { err "No CSRF"; exit 1; }
ok "Session OK (CSRF=${CSRF:0:8}…)"

PREVIEW_URL="https://www.dgft.gov.in/CP/webHP?requestType=ApplicationRH&actionVal=preview&screenId=9000012350&_csrf=$CSRF"
DETAIL_URL_TPL="https://www.dgft.gov.in/CP/webHP?requestType=ApplicationRH&actionVal=exportImportDetail&screenId=90000534&sion=__CODE__&_csrf=$CSRF"

# ── 2. List SION codes per group ────────────────────────────
LIST_FILE=$(mktemp -t sion-list)
log "Listing SION codes per product group..."
total=0
for entry in "${PRODUCT_GROUPS[@]}"; do
    IFS=':' read -r GID LETTER GNAME <<< "$entry"
    if [ -n "$LIMIT_LETTERS" ] && ! echo "$LIMIT_LETTERS" | tr ',' '\n' | grep -qx "$LETTER"; then
        continue
    fi
    JSON=$(curl -s -k -b "$COOKIE_FILE" -A "Mozilla/5.0" -X POST \
        -H "Content-Type: application/x-www-form-urlencoded; charset=UTF-8" \
        -H "x-requested-with: XMLHttpRequest" \
        --data-raw "sionSerialNumber=&ExpoProdGroup=$GID" \
        "$PREVIEW_URL")
    COUNT=$(echo "$JSON" | /usr/bin/python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d: print(r['value'], '$GID', '$LETTER', '${GNAME}')
" 2>/dev/null | tee -a "$LIST_FILE" | wc -l)
    printf "  %-3s %-30s %4d codes\n" "$LETTER" "$GNAME" "$COUNT"
    total=$((total + COUNT))
done
ok "Total SION codes to fetch: $total"

# ── 3. Fetch each SION detail (resumable, ~0.5s per request) ─
log "Fetching SION details (this will take a while)..."
fetched=0
cached=0
failed=0
i=0
TOTAL_CODES=$(wc -l < "$LIST_FILE")
while IFS=' ' read -r CODE GID LETTER REST; do
    i=$((i + 1))
    OUT="$RAW_DIR/${CODE}.json"
    if [ -f "$OUT" ] && [ -s "$OUT" ]; then
        cached=$((cached + 1))
        continue
    fi
    URL=$(echo "$DETAIL_URL_TPL" | sed "s|__CODE__|$CODE|")
    HTTP=$(curl -s -k -b "$COOKIE_FILE" -A "Mozilla/5.0" -X POST \
        -H "accept: application/json, text/javascript, */*; q=0.01" \
        -H "content-length: 0" \
        -H "origin: https://www.dgft.gov.in" \
        -H "referer: $LANDING_URL" \
        -H "x-requested-with: XMLHttpRequest" \
        "$URL" \
        -o "$OUT" -w "%{http_code}")
    if [ "$HTTP" = "200" ] && [ -s "$OUT" ] && head -c 1 "$OUT" | grep -q "[\[{]"; then
        fetched=$((fetched + 1))
    else
        failed=$((failed + 1))
        rm -f "$OUT"
    fi
    # Progress every 50
    if [ $((i % 50)) -eq 0 ]; then
        printf "  [%d/%d] fetched=%d cached=%d failed=%d\n" "$i" "$TOTAL_CODES" "$fetched" "$cached" "$failed"
    fi
    sleep 0.4
done < "$LIST_FILE"

rm -f "$LIST_FILE"
ok "Fetch complete: fetched=$fetched cached=$cached failed=$failed"

# ── 4. Parse all responses into a single payload ─────────────
log "Parsing $((fetched + cached)) responses..."
/usr/bin/python3 << PY
import json, os, re
RAW_DIR = "$RAW_DIR"
LIST = """
$(for entry in "${PRODUCT_GROUPS[@]}"; do
    IFS=':' read -r GID LETTER GNAME <<< "$entry"
    echo "$LETTER|$GNAME"
done)
"""
# group letter → group name
letter_to_group = {}
for ln in LIST.strip().splitlines():
    if '|' in ln:
        letter, name = ln.split('|', 1)
        letter_to_group[letter] = name

out = {}
for fn in sorted(os.listdir(RAW_DIR)):
    if not fn.endswith('.json'): continue
    code = fn.replace('.json', '')
    try:
        rows = json.load(open(os.path.join(RAW_DIR, fn)))
    except Exception:
        continue
    if not rows or not isinstance(rows, list):
        continue
    first = rows[0]
    description = first.get('description') or first.get('exportItemName') or ''
    # Group letter is first char of the SION code (e.g. "E126" → E)
    letter = code[0] if code else ''
    head_name = letter_to_group.get(letter) or first.get('exportProductGroup') or 'Unknown'
    exports = []
    imports = []
    remarks = set()
    for i, r in enumerate(rows, start=1):
        ex_name = (r.get('exportItemName') or '').strip()
        if ex_name and not any(e['description'] == ex_name for e in exports):
            exports.append({'description': ex_name,
                            'quantity': r.get('qtyExportItem'),
                            'unit': r.get('uomExport')})
        im_name = (r.get('importItemName') or '').strip()
        if im_name:
            imports.append({'serial_number': i,
                            'description': im_name,
                            'quantity': r.get('qtyImportItem'),
                            'unit': r.get('uomImport'),
                            'hsn_code': None,
                            'condition': ''})
        rk = (r.get('remarks') or '').strip()
        if rk: remarks.add(rk)
    out[code] = {
        'description': description,
        'head_name': head_name,
        'exports': exports,
        'imports': imports,
        'notes': sorted(remarks),
    }
json.dump(out, open("$PAYLOAD_FILE", 'w'))
print(f"Parsed {len(out)} SION norms")
PY

if [ "$DRY_RUN" = "1" ]; then
    log "Dry-run mode — not pushing to servers"
    cp "$PAYLOAD_FILE" /tmp/sion-full-payload-dry.json
    ok "Payload saved to /tmp/sion-full-payload-dry.json"
    exit 0
fi

# ── 5. Push to all 3 servers (creates missing SION classes) ──
PY_TEMPLATE=$(mktemp -t sion-full-import)
cat > "$PY_TEMPLATE" << 'PY'
import os, sys, django
sys.path.insert(0, '/home/django/license-manager/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

import json
from decimal import Decimal, InvalidOperation
from core.models import HeadSIONNormsModel, SionNormClassModel, SIONExportModel, SIONImportModel, SionNormNote

PAYLOAD_PATH = '__PAYLOAD_PATH__'
data = json.load(open(PAYLOAD_PATH))

def dec(v, default='0'):
    try: return Decimal(str(v if v not in (None, '') else default))
    except (InvalidOperation, TypeError): return Decimal(default)

stats = {'sion_created': 0, 'sion_updated': 0, 'head_created': 0,
         'exports': 0, 'imports': 0, 'notes': 0, 'errors': 0}

for code, payload in data.items():
    # Resolve / create head
    head = None
    if payload['head_name']:
        head, h_created = HeadSIONNormsModel.objects.get_or_create(name=payload['head_name'])
        if h_created: stats['head_created'] += 1

    # Resolve / create SION class
    sion = SionNormClassModel.objects.filter(norm_class=code).first()
    if not sion:
        try:
            sion = SionNormClassModel.objects.create(
                norm_class=code,
                description=(payload['description'] or '')[:255] or code,
                head_norm=head,
                is_active=False,    # new SIONs land as inactive on every server
            )
            stats['sion_created'] += 1
        except Exception as e:
            stats['errors'] += 1
            continue
    else:
        changed = False
        new_desc = (payload['description'] or '')[:255]
        if new_desc and sion.description != new_desc:
            sion.description = new_desc
            changed = True
        if head and sion.head_norm_id != head.id:
            sion.head_norm = head
            changed = True
        if changed:
            sion.save()
            stats['sion_updated'] += 1

    # Wipe & repopulate child tables
    SIONExportModel.objects.filter(norm_class=sion).delete()
    SIONImportModel.objects.filter(norm_class=sion).delete()
    SionNormNote.objects.filter(sion_norm=sion).delete()

    for e in payload['exports']:
        SIONExportModel.objects.create(
            norm_class=sion,
            description=(e['description'] or '')[:255],
            quantity=dec(e['quantity']),
            unit=(e['unit'] or '')[:50],
        )
        stats['exports'] += 1
    for i in payload['imports']:
        SIONImportModel.objects.create(
            serial_number=i['serial_number'],
            norm_class=sion,
            hsn_code=None,
            description=(i['description'] or '')[:255],
            quantity=dec(i['quantity']),
            unit=(i['unit'] or '')[:50],
            condition=(i['condition'] or '')[:255],
        )
        stats['imports'] += 1
    for idx, note in enumerate(payload['notes'], start=1):
        SionNormNote.objects.create(sion_norm=sion, note_text=note, display_order=idx)
        stats['notes'] += 1

print(f"sion_created:{stats['sion_created']} sion_updated:{stats['sion_updated']} "
      f"head_created:{stats['head_created']} exports:{stats['exports']} "
      f"imports:{stats['imports']} notes:{stats['notes']} errors:{stats['errors']}")
PY

for entry in "143.110.252.201:license-manager" "139.59.92.226:labdhi" "165.232.185.220:tractor"; do
    IFS=':' read -r IP LABEL <<< "$entry"
    log "Pushing to $LABEL ($IP)..."
    REMOTE_PAYLOAD="/tmp/sion-full-payload-$$.json"
    REMOTE_SCRIPT="/tmp/sion-full-import-$$.py"
    PY_REAL=$(mktemp -t sion-full-import-real)
    sed "s|__PAYLOAD_PATH__|$REMOTE_PAYLOAD|g" "$PY_TEMPLATE" > "$PY_REAL"

    sshpass -p admin scp -o StrictHostKeyChecking=no -o LogLevel=ERROR "$PAYLOAD_FILE" "django@$IP:$REMOTE_PAYLOAD" >/dev/null
    sshpass -p admin scp -o StrictHostKeyChecking=no -o LogLevel=ERROR "$PY_REAL"      "django@$IP:$REMOTE_SCRIPT"  >/dev/null

    RESULT=$(sshpass -p admin ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR django@$IP \
        "cd /home/django/license-manager/backend && source /home/django/license-manager/venv/bin/activate && python $REMOTE_SCRIPT 2>&1" \
        | grep -E "sion_created|Error|Traceback" | tail -3)

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
ok "Done — all 3 servers updated with the full SION catalog"
