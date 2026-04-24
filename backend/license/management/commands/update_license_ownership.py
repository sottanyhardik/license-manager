import os
import time
from datetime import datetime

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

from data_script.fetch_ownership import fetch_scrip_ownership
from license.models import LicenseDetailsModel

# === Config ===
# Use the correct server domain (default, can be overridden by --server option)
SERVER_BASE_URL = os.getenv('SERVER_BASE_URL', 'https://license-manager.duckdns.org')
SERVER_API = f"{SERVER_BASE_URL}/api/license-actions/update-license-transfer/"
SERVER_AUTH_URL = f"{SERVER_BASE_URL}/api/auth/login/"
SERVER_USERNAME = os.getenv('SERVER_USERNAME', 'admin')
SERVER_PASSWORD = os.getenv('SERVER_PASSWORD', 'admin@123')

# IP fallbacks use plain HTTP so SSL certificates are not involved — no verify=False needed
SERVER_IP_FALLBACKS = {
    'license-manager.duckdns.org': 'http://143.110.252.201',
    'labdhi.duckdns.org': 'http://139.59.92.226',
    'license-tractor.duckdns.org': 'http://165.232.185.220',
}

# DGFT API Config
APP_ID = "204000000"
SESSION_ID = "ECDCCFE06566EB25ECD234D0B7159888"
CSRF_TOKEN = "fc86ccf3-4638-4828-b271-150b04a3f6cd"

# Proxy configuration - set via DGFT_PROXY environment variable
# Examples:
#   export DGFT_PROXY="http://proxy.example.com:8080"
#   export DGFT_PROXY="socks5://127.0.0.1:1080"
DGFT_PROXY = os.getenv('DGFT_PROXY')

SLEEP_INTERVAL = 2  # seconds
BATCH_SIZE = 20  # Number of licenses to send to server in each batch

# Global session for authentication
auth_token = None


def fetch_eligible_licenses(order=None, expired_only=False):
    """
    Return licenses to fetch from DGFT.

    expired_only=True  → only expired licenses (license_expiry_date <= today)
    expired_only=False → never-fetched OR still-active licenses (default)

    order: 'asc' (soonest/None-first), 'desc' (latest/None-last, default)
    """
    from datetime import date
    from django.db.models import F, Q

    today = date.today()
    if expired_only:
        qs = LicenseDetailsModel.objects.filter(
            license_expiry_date__isnull=False,
            license_expiry_date__lte=today,
        )
    else:
        qs = LicenseDetailsModel.objects.filter(
            Q(last_ownership_fetch__isnull=True) | Q(license_expiry_date__gt=today)
        )
    if order == 'asc':
        qs = qs.order_by(F('license_expiry_date').asc(nulls_first=True))
    else:
        qs = qs.order_by(F('license_expiry_date').desc(nulls_last=True))
    return qs


def _derive_current_owner_from_transfers(transfers, api_current_owner):
    """
    DGFT's meisScripCurrentOwnerDtls reflects the querying IEC's perspective,
    not necessarily the true current owner.  Derive it instead from the last
    Approved transfer's toIEC, which matches what the DGFT portal displays.
    Falls back to api_current_owner when no approved transfers exist.
    """
    from datetime import datetime

    approved = [t for t in transfers if (t.get("transferStatus") or "").strip().lower() == "approved"]
    if not approved:
        return api_current_owner

    def _parse_dt(t):
        for key in ("transferInitiationDate", "transferDate", "transferacceptanceDate"):
            raw = (t.get(key) or "").split("+")[0].strip()
            # Normalise fractional seconds: "13:12:0.0" → "13:12:0" so strptime handles it
            raw_norm = raw.split(".")[0].strip()
            for candidate in (raw_norm, raw):
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",   # DGFT: "2026-02-02 13:12:0" (space, no frac)
                    "%d/%m/%Y %H:%M:%S",   # "02/02/2026 13:12:00"
                    "%Y-%m-%dT%H:%M:%S",   # ISO with T
                    "%d/%m/%Y",            # date only
                    "%Y-%m-%d",            # date only ISO
                ):
                    try:
                        return datetime.strptime(candidate, fmt)
                    except (ValueError, AttributeError):
                        continue
        return datetime.min

    latest = max(approved, key=_parse_dt)
    to_iec = latest.get("toIEC")
    if to_iec:
        return {"iec": to_iec, "firm": latest.get("toIecEntityName")}
    return api_current_owner


def build_payload(dfia, data, fetched_iec=None):
    """
    Build payload to post to server from ownership API response.
    """
    original_owner = data.get("meisScripOriginalOwnerDtls", {})
    transfers = data.get("scripTransfer", [])
    current_owner = _derive_current_owner_from_transfers(
        transfers, data.get("meisScripCurrentOwnerDtls", {})
    )

    # Get exporter IEC from license, original owner, or the IEC used to fetch
    exporter_iec = None
    if dfia.exporter:
        exporter_iec = dfia.exporter.iec
    elif original_owner.get("iec"):
        exporter_iec = original_owner.get("iec")
    elif fetched_iec:
        exporter_iec = fetched_iec

    payload = {
        "license_number": dfia.license_number,
        "license_date": dfia.license_date.strftime('%Y-%m-%d') if dfia.license_date else None,
        "exporter_iec": exporter_iec,
        "validity": original_owner.get("validity"),
        "last_ownership_fetch": dfia.last_ownership_fetch.isoformat() if dfia.last_ownership_fetch else None,
        "current_owner": {
            "iec": current_owner.get("iec"),
            "name": current_owner.get("firm")
        } if current_owner.get("iec") else None,
        "transfers": [
            {
                "from_iec": t.get("fromIEC"),
                "to_iec": t.get("toIEC"),
                "transfer_status": t.get("transferStatus"),
                "transfer_initiation_date": t.get("transferInitiationDate"),
                "transfer_date": t.get("transferDate"),
                "transfer_acceptance_date": t.get("transferacceptanceDate"),
                "cbic_status": t.get("cbicStatus"),
                "cbic_response_date": t.get("cbicResponseDate"),
                "user_id_transfer_initiation": t.get("userIdTransferInitiation"),
                "user_id_acceptance": t.get("userIdAcceptance"),
                "from_iec_entity_name": t.get("fromIecEntityName"),
                "to_iec_entity_name": t.get("toIecEntityName"),
            } for t in transfers
        ]
    }

    return payload


def authenticate(server_url=None):
    """
    Authenticate with server and get JWT token.
    Tries domain first, then IP fallback if DNS fails.
    Returns (success: bool, resolved_url: str)
    """
    global auth_token

    if server_url is None:
        server_url = SERVER_BASE_URL

    from urllib.parse import urlparse
    domain = urlparse(server_url).hostname or ''

    # Build list of URLs to try: domain first, then IP fallback if available
    urls_to_try = [server_url]
    if domain in SERVER_IP_FALLBACKS:
        ip_url = SERVER_IP_FALLBACKS[domain]
        if ip_url != server_url:
            urls_to_try.append(ip_url)

    for attempt_url in urls_to_try:
        auth_url = f"{attempt_url}/api/auth/login/"
        try:
            print(f"   Connecting to: {auth_url}")
            print(f"   Username: {SERVER_USERNAME}")

            response = requests.post(
                auth_url,
                json={'username': SERVER_USERNAME, 'password': SERVER_PASSWORD},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                auth_token = data.get('access')
                print(f"✅ Authenticated successfully (via {attempt_url})")
                return True, attempt_url
            else:
                print(f"❌ Authentication failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False, attempt_url

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"⚠️  Could not reach {attempt_url}: {e}")
            if attempt_url != urls_to_try[-1]:
                print(f"   Trying fallback IP...")
            continue
        except requests.exceptions.SSLError as e:
            print(f"❌ SSL Error on {attempt_url}: {e}")
            continue
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            import traceback
            traceback.print_exc()
            return False, attempt_url

    print(f"❌ All connection attempts failed for {server_url}")
    return False, server_url


def save_ownership_locally(dfia, data, fetched_iec=None):
    """
    Save ownership information to local database.
    """
    from license.models import LicenseTransferModel
    from core.models import CompanyModel

    try:
        original_owner = data.get("meisScripOriginalOwnerDtls", {})
        transfers = data.get("scripTransfer", [])
        current_owner = _derive_current_owner_from_transfers(
            transfers, data.get("meisScripCurrentOwnerDtls", {})
        )

        # Update license exporter if not set - try to get from original owner
        if not dfia.exporter and original_owner.get("iec"):
            original_iec = original_owner.get("iec")
            original_name = original_owner.get("firm")

            # Find or create company for original owner
            try:
                exporter_company = CompanyModel.objects.get(iec=original_iec)
                print(f"   📋 Found exporter: {exporter_company.name} ({original_iec})")
            except CompanyModel.DoesNotExist:
                exporter_company = CompanyModel.objects.create(
                    iec=original_iec,
                    name=original_name or f"Company {original_iec}"
                )
                print(f"   ➕ Created exporter: {exporter_company.name} ({original_iec})")

            # Update license with exporter
            dfia.exporter = exporter_company
            dfia.save(update_fields=['exporter'])
            print(f"   ✅ Updated license exporter to {original_iec}")
        elif not dfia.exporter and fetched_iec:
            # Use the IEC that was used to fetch as fallback
            try:
                exporter_company = CompanyModel.objects.get(iec=fetched_iec)
                print(f"   📋 Found exporter: {exporter_company.name} ({fetched_iec})")
            except CompanyModel.DoesNotExist:
                exporter_company = CompanyModel.objects.create(
                    iec=fetched_iec,
                    name=f"Company {fetched_iec}"
                )
                print(f"   ➕ Created exporter: {exporter_company.name} ({fetched_iec})")

            dfia.exporter = exporter_company
            dfia.save(update_fields=['exporter'])
            print(f"   ✅ Updated license exporter to {fetched_iec}")

        # Update license expiry date from validity field if available
        validity_date = original_owner.get("validity")
        if validity_date:
            # Parse validity date (assuming DD/MM/YYYY format)
            from datetime import datetime
            try:
                if '/' in validity_date:
                    parsed_validity = datetime.strptime(validity_date, '%d/%m/%Y').date()
                elif '-' in validity_date:
                    parsed_validity = datetime.strptime(validity_date, '%Y-%m-%d').date()
                else:
                    parsed_validity = None

                if parsed_validity and parsed_validity != dfia.license_expiry_date:
                    print(f"   📅 Updating expiry date: {dfia.license_expiry_date} → {parsed_validity}")
                    dfia.license_expiry_date = parsed_validity
                    dfia.save(update_fields=['license_expiry_date'])
            except (ValueError, AttributeError) as e:
                print(f"   ⚠️  Could not parse validity date '{validity_date}': {e}")

        # Update license with current owner - find or create company by IEC
        update_fields = []
        if current_owner.get("iec"):
            owner_iec = current_owner.get("iec")
            owner_name = current_owner.get("firm")

            # Try to find existing company by IEC
            try:
                owner_company = CompanyModel.objects.get(iec=owner_iec)
            except CompanyModel.DoesNotExist:
                # Create new company if not found
                owner_company = CompanyModel.objects.create(
                    iec=owner_iec,
                    name=owner_name or f"Company {owner_iec}"
                )

            dfia.current_owner = owner_company
            update_fields.append('current_owner')

        if update_fields:
            dfia.save(update_fields=update_fields)

        # Save/update transfers
        for transfer_data in transfers:
            from_iec = transfer_data.get("fromIEC")
            to_iec = transfer_data.get("toIEC")
            from_name = transfer_data.get("fromIecEntityName")
            to_name = transfer_data.get("toIecEntityName")

            # Find or create from_company
            from_company = None
            if from_iec:
                try:
                    from_company = CompanyModel.objects.get(iec=from_iec)
                except CompanyModel.DoesNotExist:
                    from_company = CompanyModel.objects.create(
                        iec=from_iec,
                        name=from_name or f"Company {from_iec}"
                    )

            # Find or create to_company
            to_company = None
            if to_iec:
                try:
                    to_company = CompanyModel.objects.get(iec=to_iec)
                except CompanyModel.DoesNotExist:
                    to_company = CompanyModel.objects.create(
                        iec=to_iec,
                        name=to_name or f"Company {to_iec}"
                    )

            # Create or update transfer record
            # Use license + transfer_initiation_date as unique identifier
            transfer_init_date_str = transfer_data.get("transferInitiationDate")
            if transfer_init_date_str:
                # Parse datetime and make timezone-aware
                transfer_init_date = parse_datetime(transfer_init_date_str)
                if transfer_init_date and timezone.is_naive(transfer_init_date):
                    transfer_init_date = timezone.make_aware(transfer_init_date)

                # Parse other datetime fields
                transfer_date = transfer_data.get("transferDate")
                if transfer_date:
                    transfer_date = parse_date(transfer_date)

                transfer_accept_date = transfer_data.get("transferacceptanceDate")
                if transfer_accept_date:
                    transfer_accept_date = parse_datetime(transfer_accept_date)
                    if transfer_accept_date and timezone.is_naive(transfer_accept_date):
                        transfer_accept_date = timezone.make_aware(transfer_accept_date)

                cbic_resp_date = transfer_data.get("cbicResponseDate")
                if cbic_resp_date:
                    cbic_resp_date = parse_datetime(cbic_resp_date)
                    if cbic_resp_date and timezone.is_naive(cbic_resp_date):
                        cbic_resp_date = timezone.make_aware(cbic_resp_date)

                LicenseTransferModel.objects.update_or_create(
                    license=dfia,
                    transfer_initiation_date=transfer_init_date,
                    defaults={
                        'from_company': from_company,
                        'to_company': to_company,
                        'transfer_status': transfer_data.get("transferStatus"),
                        'transfer_date': transfer_date,
                        'transfer_acceptance_date': transfer_accept_date,
                        'cbic_status': transfer_data.get("cbicStatus"),
                        'cbic_response_date': cbic_resp_date,
                        'user_id_transfer_initiation': transfer_data.get("userIdTransferInitiation"),
                        'user_id_acceptance': transfer_data.get("userIdAcceptance"),
                    }
                )

        # Record the timestamp of this successful fetch
        dfia.last_ownership_fetch = timezone.now()
        dfia.save(update_fields=['last_ownership_fetch'])

        return True
    except Exception as e:
        print(f"   ⚠️  Failed to save locally: {e}")
        return False


def fetch_and_update_ownership(dfia, max_retries=3, proxy=None, iec_number=None, default_iec=None):
    """
    Fetch ownership info from PRC and save locally.
    Returns tuple: (success, payload_or_none, error_msg_or_none)
    """
    import requests.exceptions

    # Get IEC number - from parameter, or from exporter, or from default_iec
    # Always try to fetch, using default IEC if needed
    if iec_number:
        iec = iec_number
    elif dfia.exporter:
        iec = dfia.exporter.iec
    elif default_iec:
        iec = default_iec
        print(f"   ℹ️  Using default IEC to fetch: {iec}")
    else:
        # If no IEC is available at all, skip but don't fail
        return (False, None, "No IEC available (no exporter, no default IEC)")

    for attempt in range(max_retries):
        try:
            # Step 1: Fetch from PRC
            response = fetch_scrip_ownership(
                scrip_number=dfia.license_number,
                scrip_issue_date=dfia.license_date.strftime('%d/%m/%Y'),
                iec_number=iec,
                app_id=APP_ID,
                session_id=SESSION_ID,
                csrf_token=CSRF_TOKEN,
                proxy=proxy
            )

            if response is None:
                if attempt < max_retries - 1:
                    time.sleep(5)  # Wait before retry
                    continue
                return (False, None, "Failed to fetch from PRC API")

            data = response.json()

            # Step 2: Save to local database (pass the IEC used for fetching)
            saved_locally = save_ownership_locally(dfia, data, fetched_iec=iec)

            if not saved_locally:
                return (False, None, "Local save failed")

            # Step 3: Build payload for server (pass the IEC used for fetching)
            payload = build_payload(dfia, data, fetched_iec=iec)
            return (True, payload, None)

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️  Connection error, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(5)
                continue
            return (False, None, f"Network error after {max_retries} attempts: {str(e)}")
        except AttributeError as e:
            if "'NoneType' object has no attribute 'json'" in str(e):
                return (False, None, "PRC API returned empty response")
            return (False, None, str(e))
        except Exception as e:
            return (False, None, str(e))

    return (False, None, "Max retries exceeded")


def bulk_sync_to_server(payloads, server_url):
    """
    Send all payloads to server in a single batch request.
    """
    global auth_token

    if not payloads:
        return {"success": 0, "failed": 0}

    try:
        headers = {}
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'

        # Send batch request
        batch_payload = {"licenses": payloads}
        res = requests.post(
            f"{server_url}/api/license-actions/bulk-update-license-transfer/",
            json=batch_payload,
            headers=headers,
            timeout=300  # 5 minutes for bulk operation
        )

        if res.status_code in [200, 201]:
            result = res.json()
            return {
                "success": result.get("success", len(payloads)),
                "failed": result.get("failed", 0),
                "errors": result.get("errors", [])
            }
        elif res.status_code == 401:
            # Retry with re-authentication
            auth_ok, _ = authenticate(server_url)
            if auth_ok:
                headers['Authorization'] = f'Bearer {auth_token}'
                res = requests.post(
                    f"{server_url}/api/license-actions/bulk-update-license-transfer/",
                    json=batch_payload,
                    headers=headers,
                    timeout=300
                )
                if res.status_code in [200, 201]:
                    result = res.json()
                    return {
                        "success": result.get("success", len(payloads)),
                        "failed": result.get("failed", 0),
                        "errors": result.get("errors", [])
                    }

        return {
            "success": 0,
            "failed": len(payloads),
            "errors": [f"Server error: {res.status_code} - {res.text}"]
        }

    except Exception as e:
        return {
            "success": 0,
            "failed": len(payloads),
            "errors": [str(e)]
        }


class Command(BaseCommand):
    help = "Fetch ownership status for DFIA licenses, save locally, and sync to server"

    def add_arguments(self, parser):
        parser.add_argument(
            '--local-only',
            action='store_true',
            help='Only update local database, do not sync to server',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of licenses to process',
        )
        parser.add_argument(
            '--skip-errors',
            action='store_true',
            help='Continue processing even if network errors occur',
        )
        parser.add_argument(
            '--retry-count',
            type=int,
            default=3,
            help='Number of retries for failed API calls (default: 3)',
        )
        parser.add_argument(
            '--proxy',
            type=str,
            default=None,
            help='Proxy URL for DGFT API (e.g., http://proxy:8080 or socks5://127.0.0.1:1080)',
        )
        parser.add_argument(
            '--licenses',
            type=str,
            default=None,
            help='Comma-separated list of specific license numbers to process',
        )
        parser.add_argument(
            '--server',
            type=str,
            default=None,
            help='Server URL to sync to (e.g., https://license-manager.duckdns.org, http://139.59.92.226, http://165.232.185.220)',
        )
        parser.add_argument(
            '--iec',
            type=str,
            default='LACPS9967D',
            help='Default IEC number to use for licenses without exporter (default: LACPS9967D)',
        )
        parser.add_argument(
            '--fetch-all',
            action='store_true',
            help='Fetch ALL licenses including expired ones (by default only fetches non-expired licenses)',
        )
        parser.add_argument(
            '--order',
            type=str,
            choices=['asc', 'desc'],
            default=None,
            help='Order licenses by expiry date: asc (soonest first) or desc (latest first, default)',
        )
        parser.add_argument(
            '--expired',
            action='store_true',
            default=False,
            help='Only process expired DFIA licenses (license_expiry_date <= today)',
        )

    def handle(self, *args, **options):
        local_only = options['local_only']
        limit = options['limit']
        skip_errors = options['skip_errors']
        retry_count = options['retry_count']
        proxy = options['proxy'] or DGFT_PROXY
        license_numbers_str = options['licenses']
        order = options['order']
        expired_only = options['expired']
        server_url = options['server']
        default_iec = options['iec']  # Default IEC for licenses without exporter
        fetch_all = options['fetch_all']  # Fetch all licenses including expired

        # If not local-only and no server specified, ask for server
        if not local_only and not server_url:
            self.stdout.write("\n" + "="*80)
            self.stdout.write("🌐 Select Server to Sync")
            self.stdout.write("="*80)
            self.stdout.write("1. https://license-manager.duckdns.org (143.110.252.201)")
            self.stdout.write("2. https://labdhi.duckdns.org (139.59.92.226)")
            self.stdout.write("3. http://165.232.185.220 (license-tractor.duckdns.org)")
            self.stdout.write("4. Custom URL")
            self.stdout.write("5. Skip server sync (local only)")
            self.stdout.write("="*80)

            choice = input("\nEnter your choice (1-5): ").strip()

            if choice == '1':
                server_url = 'https://license-manager.duckdns.org'
            elif choice == '2':
                server_url = 'https://labdhi.duckdns.org'
            elif choice == '3':
                server_url = 'http://165.232.185.220'
            elif choice == '4':
                server_url = input("Enter custom server URL: ").strip()
            elif choice == '5':
                local_only = True
                self.stdout.write(self.style.WARNING("\n⚠️  Continuing in LOCAL ONLY mode"))
            else:
                self.stdout.write(self.style.ERROR("\n❌ Invalid choice. Exiting."))
                return

        # Use provided server or default
        if not server_url and not local_only:
            server_url = SERVER_BASE_URL

        self.stdout.write("\n" + "="*80)
        self.stdout.write("📋 License Ownership Update Tool")
        self.stdout.write("="*80)
        if not local_only:
            self.stdout.write(f"Server: {server_url}")
        self.stdout.write(f"Mode: {'LOCAL ONLY' if local_only else 'LOCAL + BULK SERVER SYNC'}")
        filter_label = "Expired only" if expired_only else "Never-fetched + Active (expired+fetched skipped)"
        self.stdout.write(f"License Filter: {filter_label}")
        self.stdout.write(f"Retry Count: {retry_count}")
        self.stdout.write(f"Skip Errors: {'Yes' if skip_errors else 'No'}")
        if proxy:
            self.stdout.write(f"Proxy: {proxy}")
        if license_numbers_str:
            self.stdout.write(f"Specific Licenses: {license_numbers_str}")
        if default_iec:
            self.stdout.write(f"Default IEC (for licenses without exporter): {default_iec}")
        self.stdout.write("="*80)

        # Authenticate with server if syncing
        if not local_only:
            self.stdout.write("\n🔐 Authenticating with server...")
            auth_ok, resolved_url = authenticate(server_url)
            if not auth_ok:
                self.stdout.write(self.style.ERROR(
                    f"\n❌ Cannot authenticate with server at {server_url}.\n"
                    "   Check network/VPN, credentials, or use --local-only to skip server sync."
                ))
                return
            # Use the URL that actually worked (may be IP fallback instead of domain)
            server_url = resolved_url

        # Fetch licenses - either specific ones, all licenses, or eligible ones
        if license_numbers_str:
            # Process specific license numbers
            license_numbers = [ln.strip() for ln in license_numbers_str.split(',')]
            licenses = LicenseDetailsModel.objects.filter(license_number__in=license_numbers)

            # Check which licenses were not found
            found_numbers = set(licenses.values_list('license_number', flat=True))
            missing_numbers = set(license_numbers) - found_numbers
            if missing_numbers:
                self.stdout.write(self.style.WARNING(
                    f"\n⚠️  Licenses not found: {', '.join(sorted(missing_numbers))}"
                ))
        else:
            licenses = fetch_eligible_licenses(order=order, expired_only=expired_only)
            if limit:
                licenses = licenses[:limit]

        total = licenses.count()
        self.stdout.write(f"\n🔎 Found {total} licenses to process")
        self.stdout.write("-"*80)

        # Process licenses in batches: fetch batch, then sync to server
        success_count = 0
        failed_count = 0
        total_synced = 0
        total_sync_failed = 0
        failed_licenses = []
        all_sync_errors = []

        # Process in batches of BATCH_SIZE
        for batch_start in range(0, total, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total)
            batch_licenses = list(licenses[batch_start:batch_end])
            batch_num = (batch_start // BATCH_SIZE) + 1
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

            self.stdout.write("\n" + "="*80)
            self.stdout.write(f"📦 BATCH {batch_num}/{total_batches} - Processing licenses {batch_start + 1} to {batch_end}")
            self.stdout.write("="*80)

            # Step 1: Fetch and save locally for this batch
            batch_payloads = []

            for idx, dfia in enumerate(batch_licenses, start=batch_start + 1):
                self.stdout.write(f"\n[{idx}/{total}] Processing {dfia.license_number}...")
                try:
                    success, payload, error = fetch_and_update_ownership(dfia, max_retries=retry_count, proxy=proxy, default_iec=default_iec)

                    if success:
                        self.stdout.write(f"   ✅ Fetched and saved locally")
                        batch_payloads.append(payload)
                        success_count += 1
                    else:
                        self.stdout.write(self.style.ERROR(f"   ❌ Failed: {error}"))
                        failed_licenses.append((dfia.license_number, error))
                        failed_count += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Failed: {e}"))
                    failed_licenses.append((dfia.license_number, str(e)))
                    failed_count += 1

                time.sleep(SLEEP_INTERVAL)

            # Step 2: Sync this batch to server (if not local-only and we have data)
            if not local_only and batch_payloads:
                self.stdout.write("\n" + "-"*80)
                self.stdout.write(f"🌐 Syncing batch {batch_num} ({len(batch_payloads)} licenses) to server...")

                result = bulk_sync_to_server(batch_payloads, server_url)

                batch_success = result.get("success", 0)
                batch_failed = result.get("failed", 0)

                total_synced += batch_success
                total_sync_failed += batch_failed

                if batch_success > 0:
                    self.stdout.write(self.style.SUCCESS(
                        f"   ✅ Successfully synced {batch_success}/{len(batch_payloads)} licenses"
                    ))

                if batch_failed > 0:
                    self.stdout.write(self.style.ERROR(
                        f"   ❌ Failed to sync {batch_failed}/{len(batch_payloads)} licenses"
                    ))

                if result.get("errors"):
                    all_sync_errors.extend(result["errors"])
                    for error in result["errors"][:3]:  # Show first 3 errors for this batch
                        self.stdout.write(f"      • {error}")

                self.stdout.write("-"*80)

            # Check if we should stop (error occurred and skip_errors is False)
            # Only break if we encountered an error in this batch
            if not skip_errors and failed_count > 0 and len(batch_payloads) == 0:
                # No successful fetches in this batch and skip_errors is False
                self.stdout.write(self.style.ERROR(
                    "\n⚠️  No successful fetches in batch. Stopping. Use --skip-errors to continue."
                ))
                break

            # Continue to next batch regardless of individual failures if skip_errors is True

        # Final Summary
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("✅ Ownership update complete!"))
        self.stdout.write(f"📊 Final Summary:")
        self.stdout.write(f"   ✅ Local Success: {success_count}")
        self.stdout.write(f"   ❌ Local Failed: {failed_count}")
        self.stdout.write(f"   📝 Total Processed: {success_count + failed_count}")

        if not local_only and total_synced > 0:
            self.stdout.write(f"   🌐 Server Synced: {total_synced}")
            if total_sync_failed > 0:
                self.stdout.write(f"   🌐 Server Failed: {total_sync_failed}")

        if failed_licenses:
            self.stdout.write(f"\n❌ Failed licenses:")
            for lic_num, error in failed_licenses[:10]:  # Show first 10
                self.stdout.write(f"   • {lic_num}: {error}")

        if all_sync_errors:
            self.stdout.write(f"\n⚠️  Server sync errors (first 10):")
            for error in all_sync_errors[:10]:
                self.stdout.write(f"   • {error}")

        self.stdout.write("="*80)
