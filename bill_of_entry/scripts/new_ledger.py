list1 = ['5611002535', '5611002533', '5211007631', '5211007496', '5211007086', '5211006995', '5211006893', '5211006864', '5211006127', '5211005930', '5211005814', '5211005135', '5211005013', '3011004758', '3011004657', '3011004633', '3011004632', '3011004502', '3011004500', '3011004359', '3011004230', '3011004226', '3011004088', '3011004087', '3011003976', '0311031558', '0311031557', '0311031514', '0311031513', '0311031512', '0311031511', '0311031473', '0311031471', '0311031455', '0311031454', '0311030812', '0311030805', '0311030617', '0311030356', '0311030281', '0311030280', '0311030002', '0311029850', '0311027042', '0311024589', '0311021589', '0311020706', '0311018481', '0311018479', '0311018289', '0311018476', '0311032349', '0311028888', '0311028882', '3011004781', '3011004780', '3011004779', '0311018478', '0311001701', '0311029645', '0311031571', '0311031559', '0311031533', '0311031510', '0311031456', '0311031453', '0311031358', '0311031107', '0311031011', '0311030657']

RowDetails.objects.filter(sr_number__license__license_number__in=list1,transaction_type='D').delete()


import csv
from datetime import datetime

with open('debit_list.csv', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        sr_number = LicenseImportItemsModel.objects.get(license__license_number=row['DFIA'].replace('\xa0',''), serial_number=row['sr_no'])
        be_number, bool = BillOfEntryModel.objects.get_or_create(bill_of_entry_number=row['BENO'])
        be_number.bill_of_entry_date = datetime.strptime(row['BEDT'], '%d/%m/%y')
        be_number.port,bool = PortModel.objects.get_or_create(code=row['PORT'])
        if 'BEARING' in str(sr_number.item):
            be_number.product_name = 'BEARING'
        if 'ALLOY STEEL' in str(sr_number.item):
            be_number.product_name = 'ALLOY STEEL'
        if 'air filter' in str(sr_number.item):
            be_number.product_name = 'Air Filter'
        be_number.save()
        row_details,bool = RowDetails.objects.get_or_create(bill_of_entry=be_number,sr_number=sr_number)
        row_details.cif_inr = row['CIFINR']
        row_details.cif_fc = row['CIFD']
        row_details.qty = row['QTY']
        row_details.save()
