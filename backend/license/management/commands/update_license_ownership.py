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
# Use the correct server domain
SERVER_BASE_URL = os.getenv('SERVER_BASE_URL', 'https://license-manager.duckdns.org')
SERVER_API = f"{SERVER_BASE_URL}/api/license-actions/update-license-transfer/"
SERVER_AUTH_URL = f"{SERVER_BASE_URL}/api/auth/login/"
SERVER_USERNAME = os.getenv('SERVER_USERNAME', 'admin')
SERVER_PASSWORD = os.getenv('SERVER_PASSWORD', 'admin@123')

# DGFT API Config
APP_ID = "204000000"
SESSION_ID = "A2B93634A5BD42AB7CD0AC7FE0646FD0"
CSRF_TOKEN = "4a119454-6bab-40b7-adb3-b042224073e8"

# Proxy configuration - set via DGFT_PROXY environment variable
# Examples:
#   export DGFT_PROXY="http://proxy.example.com:8080"
#   export DGFT_PROXY="socks5://127.0.0.1:1080"
DGFT_PROXY = os.getenv('DGFT_PROXY')

SLEEP_INTERVAL = 2  # seconds
BATCH_SIZE = 20  # Number of licenses to send to server in each batch

# Global session for authentication
auth_token = None


def fetch_eligible_licenses():
    """
    Get licenses with:
    - Expiry date >= 2025-06-01
    - CIF balance > $200
    - At least one allotment item with is_boe = False
    """
    from django.db.models import Q, Exists, OuterRef
    from allotment.models import AllotmentItems

    # Subquery to check if license has allotment items with is_boe = False
    # AllotmentItems -> item (LicenseImportItemsModel) -> license (LicenseDetailsModel)
    has_non_boe_items = Exists(
        AllotmentItems.objects.filter(
            item__license=OuterRef('pk'),
            is_boe=False
        )
    )

    return LicenseDetailsModel.objects.filter(
        license_expiry_date__gte="2025-06-01",
        balance_cif__gt=200,  # CIF balance > $200
    ).annotate(
        has_non_boe_allotment=has_non_boe_items
    ).filter(
        has_non_boe_allotment=True
    ).order_by("-license_expiry_date")


def build_payload(dfia, data):
    """
    Build payload to post to server from ownership API response.
    """
    current_owner = data.get("meisScripCurrentOwnerDtls", {})
    transfers = data.get("scripTransfer", [])

    payload = {
        "license_number": dfia.license_number,
        "license_date": dfia.license_date.strftime('%Y-%m-%d') if dfia.license_date else None,
        "exporter_iec": dfia.exporter.iec if dfia.exporter else None,
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


def authenticate():
    """
    Authenticate with server and get JWT token.
    """
    global auth_token
    try:
        print(f"   Connecting to: {SERVER_AUTH_URL}")
        print(f"   Username: {SERVER_USERNAME}")

        response = requests.post(
            SERVER_AUTH_URL,
            json={
                'username': SERVER_USERNAME,
                'password': SERVER_PASSWORD
            },
            verify=True,  # SSL verification
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            auth_token = data.get('access')
            print(f"✅ Authenticated successfully")
            print(f"   Token: {auth_token[:50]}...")
            return True
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL Error: {e}")
        print(f"   Try adding verify=False for testing (not recommended for production)")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: {e}")
        return False
    except requests.exceptions.Timeout as e:
        print(f"❌ Timeout Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        import traceback
        traceback.print_exc()
        return False


def save_ownership_locally(dfia, data):
    """
    Save ownership information to local database.
    """
    from license.models import LicenseTransferModel
    from core.models import CompanyModel

    try:
        current_owner = data.get("meisScripCurrentOwnerDtls", {})
        transfers = data.get("scripTransfer", [])

        # Update license with current owner - find or create company by IEC
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
            dfia.save(update_fields=['current_owner'])

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

        return True
    except Exception as e:
        print(f"   ⚠️  Failed to save locally: {e}")
        return False


def fetch_and_update_ownership(dfia, max_retries=3, proxy=None):
    """
    Fetch ownership info from PRC and save locally.
    Returns tuple: (success, payload_or_none, error_msg_or_none)
    """
    import requests.exceptions

    for attempt in range(max_retries):
        try:
            # Step 1: Fetch from PRC
            response = fetch_scrip_ownership(
                scrip_number=dfia.license_number,
                scrip_issue_date=dfia.license_date.strftime('%d/%m/%Y'),
                iec_number=dfia.exporter.iec,
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

            # Step 2: Save to local database
            saved_locally = save_ownership_locally(dfia, data)

            if not saved_locally:
                return (False, None, "Local save failed")

            # Step 3: Build payload for server
            payload = build_payload(dfia, data)
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


def bulk_sync_to_server(payloads):
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
            f"{SERVER_BASE_URL}/api/license-actions/bulk-update-license-transfer/",
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
            if authenticate():
                headers['Authorization'] = f'Bearer {auth_token}'
                res = requests.post(
                    f"{SERVER_BASE_URL}/api/license-actions/bulk-update-license-transfer/",
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

    def handle(self, *args, **options):
        local_only = options['local_only']
        limit = options['limit']
        skip_errors = options['skip_errors']
        retry_count = options['retry_count']
        proxy = options['proxy'] or DGFT_PROXY
        license_numbers_str = options['licenses']

        self.stdout.write("="*80)
        self.stdout.write("📋 License Ownership Update Tool")
        self.stdout.write("="*80)
        self.stdout.write(f"Server: {SERVER_BASE_URL}")
        self.stdout.write(f"Mode: {'LOCAL ONLY' if local_only else 'LOCAL + BULK SERVER SYNC'}")
        self.stdout.write(f"Retry Count: {retry_count}")
        self.stdout.write(f"Skip Errors: {'Yes' if skip_errors else 'No'}")
        if proxy:
            self.stdout.write(f"Proxy: {proxy}")
        if license_numbers_str:
            self.stdout.write(f"Specific Licenses: {license_numbers_str}")
        self.stdout.write("="*80)

        # Authenticate with server if syncing
        if not local_only:
            self.stdout.write("\n🔐 Authenticating with server...")
            if not authenticate():
                self.stdout.write(self.style.ERROR("Failed to authenticate."))
                self.stdout.write(self.style.WARNING("Continuing in LOCAL ONLY mode..."))
                local_only = True

        # Fetch licenses - either specific ones or eligible ones
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
            licenses = fetch_eligible_licenses()
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
                    success, payload, error = fetch_and_update_ownership(dfia, max_retries=retry_count, proxy=proxy)

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

                result = bulk_sync_to_server(batch_payloads)

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
