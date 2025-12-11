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

APP_ID = "204000000"
SESSION_ID = "A2B93634A5BD42AB7CD0AC7FE0646FD0"
CSRF_TOKEN = "4a119454-6bab-40b7-adb3-b042224073e8"
SLEEP_INTERVAL = 2  # seconds

# Global session for authentication
auth_token = None


def fetch_eligible_licenses():
    """
    Get all licenses with expiry date in the future.
    """
    return LicenseDetailsModel.objects.filter(
        license_expiry_date__gte="2025-06-01"
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


def fetch_and_update_ownership(dfia, update_server=True):
    """
    Fetch ownership info from PRC, save locally, and optionally update server.
    """
    global auth_token

    try:
        # Step 1: Fetch from PRC
        response = fetch_scrip_ownership(
            scrip_number=dfia.license_number,
            scrip_issue_date=dfia.license_date.strftime('%d/%m/%Y'),
            iec_number=dfia.exporter.iec,
            app_id=APP_ID,
            session_id=SESSION_ID,
            csrf_token=CSRF_TOKEN
        )

        data = response.json()

        # Step 2: Save to local database
        saved_locally = save_ownership_locally(dfia, data)
        local_status = "💾 Saved locally" if saved_locally else "⚠️  Local save failed"

        # Step 3: Upload to server if requested
        if update_server:
            payload = build_payload(dfia, data)

            # Add authentication header
            headers = {}
            if auth_token:
                headers['Authorization'] = f'Bearer {auth_token}'

            res = requests.post(SERVER_API, json=payload, headers=headers)

            if res.status_code in [200, 201]:
                print(f"✅ {dfia.license_number} | {local_status} | 🌐 Synced to server")
            elif res.status_code == 401:
                # Retry with re-authentication
                if authenticate():
                    headers['Authorization'] = f'Bearer {auth_token}'
                    res = requests.post(SERVER_API, json=payload, headers=headers)
                    if res.status_code in [200, 201]:
                        print(f"✅ {dfia.license_number} | {local_status} | 🌐 Synced to server (retry)")
                    else:
                        print(f"❌ {dfia.license_number} | {local_status} | Server error: {res.status_code}")
            else:
                print(f"❌ {dfia.license_number} | {local_status} | Server error: {res.status_code}")
        else:
            print(f"✅ {dfia.license_number} | {local_status}")

    except Exception as e:
        print(f"❌ {dfia.license_number} | Error: {e}")


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

    def handle(self, *args, **options):
        local_only = options['local_only']
        limit = options['limit']

        self.stdout.write("="*80)
        self.stdout.write("📋 License Ownership Update Tool")
        self.stdout.write("="*80)
        self.stdout.write(f"Server: {SERVER_BASE_URL}")
        self.stdout.write(f"Mode: {'LOCAL ONLY' if local_only else 'LOCAL + SERVER SYNC'}")
        self.stdout.write("="*80)

        # Authenticate with server if syncing
        if not local_only:
            self.stdout.write("\n🔐 Authenticating with server...")
            if not authenticate():
                self.stdout.write(self.style.ERROR("Failed to authenticate."))
                self.stdout.write(self.style.WARNING("Continuing in LOCAL ONLY mode..."))
                local_only = True

        # Fetch licenses
        licenses = fetch_eligible_licenses()
        if limit:
            licenses = licenses[:limit]

        total = licenses.count()
        self.stdout.write(f"\n🔎 Found {total} licenses to process")
        self.stdout.write("-"*80)

        # Process each license
        success_count = 0
        failed_count = 0

        for idx, dfia in enumerate(licenses, 1):
            self.stdout.write(f"\n[{idx}/{total}] Processing {dfia.license_number}...")
            try:
                fetch_and_update_ownership(dfia, update_server=not local_only)
                success_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    Failed: {e}"))
                failed_count += 1

            time.sleep(SLEEP_INTERVAL)

        # Summary
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("✅ Ownership update complete!"))
        self.stdout.write(f"📊 Summary:")
        self.stdout.write(f"   ✅ Success: {success_count}")
        self.stdout.write(f"   ❌ Failed: {failed_count}")
        self.stdout.write(f"   📝 Total: {total}")
        self.stdout.write("="*80)
