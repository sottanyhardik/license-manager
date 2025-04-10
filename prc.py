import time
import requests
from datetime import date

from PRC.fetch_prc import fetch_scrip_ownership
from license.models import LicenseDetailsModel  # just to get list1

list1 = LicenseDetailsModel.objects.filter(license_number='0311042894',
    license_expiry_date__gte=date(2024, 4, 1)
).order_by('-license_expiry_date')

# SERVER_API = "http://localhost:8000/api/update-license-transfer/"
SERVER_API = "http://167.71.233.211/api/update-license-transfer/"

for dfia in list1:
    try:
        response = fetch_scrip_ownership(
            scrip_number=dfia.license_number,
            scrip_issue_date=dfia.license_date.strftime('%d/%m/%Y'),
            iec_number=dfia.exporter.iec,
            app_id='204000000',
            session_id='A2B93634A5BD42AB7CD0AC7FE0646FD0',
            csrf_token='4a119454-6bab-40b7-adb3-b042224073e8'
        )
        data = response.json()
        payload = {
            "license_number": dfia.license_number,
            "license_date": dfia.license_date.strftime('%Y-%m-%d'),
            "exporter_iec": dfia.exporter.iec,
            "current_owner": {
                "iec": data.get("meisScripCurrentOwnerDtls", {}).get("iec"),
                "name": data.get("meisScripCurrentOwnerDtls", {}).get("firm")
            } if data.get("meisScripCurrentOwnerDtls", {}).get("iec") else None,
            "transfers": []
        }
        for transfer in data.get('scripTransfer', []):
            payload["transfers"].append({
                "from_iec": transfer.get("fromIEC"),
                "to_iec": transfer.get("toIEC"),
                "transfer_status": transfer.get("transferStatus"),
                "transfer_initiation_date": transfer.get("transferInitiationDate"),
                "transfer_date": transfer.get("transferDate"),
                "transfer_acceptance_date": transfer.get("transferacceptanceDate"),
                "cbic_status": transfer.get("cbicStatus"),
                "cbic_response_date": transfer.get("cbicResponseDate"),
                "user_id_transfer_initiation": transfer.get("userIdTransferInitiation"),
                "user_id_acceptance": transfer.get("userIdAcceptance"),
                "from_iec_entity_name": transfer.get("fromIecEntityName"),
                "to_iec_entity_name": transfer.get("toIecEntityName"),
            })
        res = requests.post(SERVER_API, json=payload)
        print("Done For DFIA", dfia.license_number, res.status_code)
    except Exception as e:
        print("Error For DFIA", dfia.license_number, e)
    time.sleep(2)



# combined_rows = []
#
# for scrip in scrip_data:
#     scrip_number = scrip["license_number"]
#     df_current_owner = pd.DataFrame([scrip["meisScripCurrentOwnerDtls"]]).add_prefix("current_")
#     df_combined = pd.concat([
#         df_current_owner.reset_index(drop=True),
#     ], axis=1)
#     combined_rows.append(df_combined)
#
# # Final DataFrame
# df_all_combined = pd.concat(combined_rows, ignore_index=True)
# # Preview the result
# print(df_all_combined)
#
#
# rows = []
# for scrip in scrip_data:
#     current_owner = scrip["meisScripCurrentOwnerDtls"]
#     current_owner["scripNumber"] = scrip["license_number"]
#     rows.append(current_owner)
#
# df = pd.DataFrame(rows)
# df.to_excel("scrip_current_owners.xlsx", index=False)
#
# print("✅ Excel file saved as 'scrip_current_owners.xlsx'")