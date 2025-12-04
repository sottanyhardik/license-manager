from bill_of_entry.models import BillOfEntryModel

boes = BillOfEntryModel.objects.filter(bill_of_entry_date__gte='2025-03-01').exclude(invoice_no=None, company__in=['313','568'])
from datetime import datetime

for boe in boes:
    data = [{
        'status': item.sr_number.license.purchase_status,
        'company': boe.company.name,
        'company_address_1': boe.company.address_line_1,
        'company_address_2': boe.company.address_line_2,
        'today': str(datetime.now().date()),
        'license': item.sr_number.license.license_number,
        'license_date': item.sr_number.license_date.strftime("%d/%m/%Y"),
        'file_number': item.sr_number.license.file_number, 'quantity': item.qty,
        'v_allotment_inr': round(item.cif_inr, 2),
        'exporter_name': item.sr_number.license.exporter.name,
        'v_allotment_usd': item.cif_fc, 'boe': "BE NUMBER :- " + item.bill_of_entry.bill_of_entry_number} for item in
        boe.item_details.all()]
    be_number = boe.bill_of_entry_number
    from core.models import TransferLetterModel
    transfer_letter = TransferLetterModel.objects.get(pk=39)
    tl_path = transfer_letter.tl.path
    file_path = 'media/tl_' + str(be_number) + '_' + transfer_letter.name.replace(' ', '_') + '/'
    from allotment.scripts.aro import generate_tl_software
    generate_tl_software(data=data, tl_path=tl_path, path=file_path,
                         transfer_letter_name=transfer_letter.name.replace(' ', '_'), be_number=be_number)
