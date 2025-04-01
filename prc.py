from datetime import date

import pandas as pd

from PRC.fetch_prc import fetch_scrip_ownership
from core.models import CompanyModel
from license.models import LicenseDetailsModel

list1 = LicenseDetailsModel.objects.filter(
    license_expiry_date__gte=date(2025, 4, 1), current_owner__isnull=True
).order_by('license_expiry_date')

for dfia in list1:
    response = fetch_scrip_ownership(
        scrip_number=dfia.license_number, scrip_issue_date=dfia.license_date.strftime('%d/%m/%Y'), iec_number=dfia.exporter.iec, app_id='204000000', session_id='A2B93634A5BD42AB7CD0AC7FE0646FD0', csrf_token='4a119454-6bab-40b7-adb3-b042224073e8')
    data = response.json()
    iec = data.get('meisScripCurrentOwnerDtls').get('iec')
    if iec:
        name = data.get('meisScripCurrentOwnerDtls').get('firm')
        company, bool = CompanyModel.objects.update_or_create(iec=iec, defaults={'name': name})
        dfia.current_owner = company
        dfia.save()
    print("Done For DFIA ",str(dfia.license_number) )

combined_rows = []

for scrip in scrip_data:
    scrip_number = scrip["license_number"]
    df_current_owner = pd.DataFrame([scrip["meisScripCurrentOwnerDtls"]]).add_prefix("current_")
    df_combined = pd.concat([
        df_current_owner.reset_index(drop=True),
    ], axis=1)
    combined_rows.append(df_combined)

# Final DataFrame
df_all_combined = pd.concat(combined_rows, ignore_index=True)
# Preview the result
print(df_all_combined)


rows = []
for scrip in scrip_data:
    current_owner = scrip["meisScripCurrentOwnerDtls"]
    current_owner["scripNumber"] = scrip["license_number"]
    rows.append(current_owner)

df = pd.DataFrame(rows)
df.to_excel("scrip_current_owners.xlsx", index=False)

print("✅ Excel file saved as 'scrip_current_owners.xlsx'")