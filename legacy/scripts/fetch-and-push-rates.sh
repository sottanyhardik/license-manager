#!/bin/bash
# ============================================================
#  fetch-and-push-rates.sh
#
#  Fetch the latest DGFT customs exchange rate (USD/EUR/GBP/CNY)
#  on this Mac (which can reach DGFT — production servers can't, 403'd),
#  then push the row to license-manager's DB via SSH+Django shell.
#
#  The existing master-sync cron (every 15 min) propagates the row to
#  labdhi + tractor automatically (ExchangeRateModel is in the sync list).
#
#  Usage:
#    bash fetch-and-push-rates.sh              # full run, prints summary
#    bash fetch-and-push-rates.sh --quiet      # silent except errors (cron)
# ============================================================

set -e

QUIET="${1:-}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { [ "$QUIET" != "--quiet" ] && echo "→ $*"; return 0; }
ok()   { [ "$QUIET" != "--quiet" ] && echo -e "${GREEN}✓${NC} $*"; return 0; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

LANDING_URL="https://www.dgft.gov.in/CP/?opt=currency-list-exchange-rates"
COOKIE_FILE=$(mktemp /tmp/dgft-cookies-XXXXXX.txt)
RESPONSE_FILE=$(mktemp /tmp/dgft-rates-XXXXXX.json)
trap "rm -f $COOKIE_FILE $RESPONSE_FILE" EXIT

# 1. Hit the landing page → get session + CSRF
log "Fetching DGFT landing page..."
HTML=$(curl -s -k -c "$COOKIE_FILE" -A "Mozilla/5.0" "$LANDING_URL")
CSRF=$(echo "$HTML" | grep -oE 'name="_csrf"[^>]*content="[a-f0-9-]+"' | grep -oE '[a-f0-9-]{36}')
if [ -z "$CSRF" ]; then
    err "Could not get CSRF token from DGFT"
    exit 1
fi
ok "CSRF token obtained"

# 2. POST to the rates API
log "Fetching rates JSON..."
API_URL="https://www.dgft.gov.in/CP/webHP?requestType=ApplicationRH&actionVal=service&screen=viewRates&screenId=9000012354&_csrf=$CSRF"
HTTP_CODE=$(curl -s -k -b "$COOKIE_FILE" -A "Mozilla/5.0" \
    -H "accept: application/json, text/javascript, */*; q=0.01" \
    -H "content-type: application/x-www-form-urlencoded; charset=UTF-8" \
    -H "origin: https://www.dgft.gov.in" \
    -H "referer: $LANDING_URL" \
    -H "x-requested-with: XMLHttpRequest" \
    --data-raw 'dataJson%5BformData%5D=%7B%22dateFrom%22%3A%22%22%2C%22dateTo%22%3A%22%22%2C%22currencyCodeInput%22%3A%22%22%7D' \
    "$API_URL" \
    -o "$RESPONSE_FILE" -w "%{http_code}")

if [ "$HTTP_CODE" != "200" ]; then
    err "DGFT API returned HTTP $HTTP_CODE"
    exit 1
fi
ok "Rates JSON fetched"

# 3. Extract USD/EUR/GBP/CNY for the latest effective date
PAYLOAD=$(/usr/bin/python3 -c "
import json, sys
d = json.load(open('$RESPONSE_FILE'))
records = d.get('data', [])
by_date = {}
for r in records:
    code = r.get('currcode')
    if code not in ('USD','EUR','GBP','CNY'): continue
    date = r.get('effdate')
    rate = r.get('importval')
    unit = r.get('fcrUnit') or 1
    if not date or rate is None: continue
    by_date.setdefault(date, {})[code] = float(rate) / float(unit)
if not by_date:
    print('ERROR:no_rates')
    sys.exit(2)
latest = max(by_date.keys())
fields = by_date[latest]
missing = [c for c in ('USD','EUR','GBP','CNY') if c not in fields]
if missing:
    print(f'ERROR:missing:{\",\".join(missing)}')
    sys.exit(3)
print(f'DATE={latest}')
print(f'USD={fields[\"USD\"]:.4f}')
print(f'EUR={fields[\"EUR\"]:.4f}')
print(f'GBP={fields[\"GBP\"]:.4f}')
print(f'CNY={fields[\"CNY\"]:.4f}')
")

if echo "$PAYLOAD" | grep -q "^ERROR"; then
    err "$PAYLOAD"
    exit 1
fi

DATE=$(echo "$PAYLOAD" | grep "^DATE=" | cut -d= -f2)
USD=$(echo "$PAYLOAD"  | grep "^USD="  | cut -d= -f2)
EUR=$(echo "$PAYLOAD"  | grep "^EUR="  | cut -d= -f2)
GBP=$(echo "$PAYLOAD"  | grep "^GBP="  | cut -d= -f2)
CNY=$(echo "$PAYLOAD"  | grep "^CNY="  | cut -d= -f2)

ok "Parsed rates for $DATE: USD=$USD EUR=$EUR GBP=$GBP CNY=$CNY"

# 4. Push to license-manager via SSH + Django shell
log "Pushing to license-manager..."
SHELL_SNIPPET="from core.models import ExchangeRateModel
from decimal import Decimal
obj, created = ExchangeRateModel.objects.update_or_create(
    date='$DATE',
    defaults={
        'usd': Decimal('$USD'),
        'euro': Decimal('$EUR'),
        'pound_sterling': Decimal('$GBP'),
        'chinese_yuan': Decimal('$CNY'),
    }
)
print('CREATED' if created else 'UPDATED', '$DATE', 'USD=$USD EUR=$EUR GBP=$GBP CNY=$CNY')"

RESULT=$(sshpass -p admin ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR django@143.110.252.201 \
    "cd /home/django/license-manager/backend && source /home/django/license-manager/venv/bin/activate && python manage.py shell -c \"$SHELL_SNIPPET\"" 2>&1 | grep -E "CREATED|UPDATED")

if [ -z "$RESULT" ]; then
    err "Failed to push to license-manager"
    exit 1
fi

ok "license-manager: $RESULT"
log "Master sync will propagate to labdhi + tractor within 15 min."
