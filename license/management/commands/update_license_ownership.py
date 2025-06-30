import time
import requests
from django.core.management.base import BaseCommand
from license.models import LicenseDetailsModel
from data_script.fetch_ownership import fetch_scrip_ownership

# === Config ===
SERVER_API = "http://167.71.233.211/api/update-license-transfer/"
APP_ID = "204000000"
SESSION_ID = "A2B93634A5BD42AB7CD0AC7FE0646FD0"
CSRF_TOKEN = "4a119454-6bab-40b7-adb3-b042224073e8"
SLEEP_INTERVAL = 2  # seconds


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

    return {
        "license_number": dfia.license_number,
        "license_date": dfia.license_date.strftime('%Y-%m-%d'),
        "exporter_iec": dfia.exporter.iec,
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


def fetch_and_post_license_status(dfia):
    """
    Fetch ownership info from PRC and POST it to the server.
    """
    try:
        response = fetch_scrip_ownership(
            scrip_number=dfia.license_number,
            scrip_issue_date=dfia.license_date.strftime('%d/%m/%Y'),
            iec_number=dfia.exporter.iec,
            app_id=APP_ID,
            session_id=SESSION_ID,
            csrf_token=CSRF_TOKEN
        )

        data = response.json()
        payload = build_payload(dfia, data)
        res = requests.post(SERVER_API, json=payload)

        print(f"✅ DFIA {dfia.license_number} updated | Status Code: {res.status_code}")
    except Exception as e:
        print(f"❌ Error for DFIA {dfia.license_number}: {e}")


class Command(BaseCommand):
    help = "Fetch ownership status for DFIA licenses and update server"

    def handle(self, *args, **options):
        licenses = fetch_eligible_licenses()
        self.stdout.write(f"🔎 Found {licenses.count()} licenses to update")

        for dfia in licenses:
            fetch_and_post_license_status(dfia)
            time.sleep(SLEEP_INTERVAL)
