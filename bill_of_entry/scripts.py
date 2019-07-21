import datetime

from allotment.models import Credit
from bill_of_entry.models import RowDetails, BillOfEntryModel
from core.models import CompanyModel, PortModel
from license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseExportItemModel


def extract_data(line, text):
    split_text = text + ' \t:'
    try:
        return line.split(split_text)[1].split('\t')[0].strip()
    except:
        print(text)
        return None


def parse_file(data):
    # split lines
    lines = data.split('\n')
    data_dict = {
        'row': []
    }
    for line in lines:
        if 'Printed By' in line:
            ledger_date = line.split('Dated:')[-1].strip().split(' ')[0]
            data_dict['ledger_date'] = datetime.datetime.strptime(ledger_date, '%d/%m/%Y')
        if 'Regn.No.' in line:
            data_dict['regn_no'] = extract_data(line, 'Regn.No.')
        if 'Regn.Date' in line:
            data_dict['regn_date'] = extract_data(line, 'Regn.Date')
        if 'Lic.Date' in line:
            data_dict['lic_date'] = datetime.datetime.strptime(extract_data(line, 'Lic.Date'), '%d/%m/%Y')
        if 'Lic.No.' in line:
            data_dict['lic_no'] = extract_data(line, 'Lic.No.')
        if 'Frgn.Curr' in line:
            data_dict['foregin_currency'] = extract_data(line, 'Frgn.Curr')
        if 'CIF-INR.' in line:
            data_dict['cif_inr'] = extract_data(line, 'CIF-INR.')
        if '\tCIF-FC \t:' in line:
            data_dict['cif_fc'] = extract_data(line, 'CIF-FC')
        if 'Tot.Qty.' in line:
            data_dict['total_quantity'] = extract_data(line, 'Tot.Qty.')
        if 'IEC \t:' in line:
            data_dict['iec'] = extract_data(line, 'IEC')
        if 'Regn.No. \t:' in line:
            data_dict['registration_no'] = extract_data(line, 'Regn.No.')
        if 'Regn.Date \t:' in line:
            data_dict['registration_date'] = datetime.datetime.strptime(extract_data(line, 'Regn.Date'), '%d/%m/%Y')
        if 'Iss.CH. \t:' in line:
            data_dict['port'] = extract_data(line, 'Iss.CH.')
        if 'Schm.Cd. \t:' in line:
            data_dict['scheme_code'] = extract_data(line, 'Schm.Cd.')
        if 'Notifcn. \t:' in line:
            data_dict['notification'] = extract_data(line, 'Notifcn.')
        if 'Credit-' in line:
            split_line = line.split('\t')
            row_dict = {
                'type': 'C',
                'sr_no': split_line[1].strip(),
                'cif_inr': split_line[3].strip(),
                'cif_fc': split_line[4].strip(),
                'qty': split_line[5].strip(),
                'be_number': '',
                'port': '',
                'be_date': '',

            }
            if row_dict['cif_inr'] == '':
                row_dict['cif_inr'] = 0
            if row_dict['cif_fc'] == '':
                row_dict['cif_fc'] = 0
            data_dict['row'].append(row_dict)
        if 'Debit-' in line:
            split_line = line.split('\t')
            row_dict = {
                'type': 'D',
                'sr_no': split_line[1].strip(),
                'cif_inr': split_line[3].strip(),
                'cif_fc': split_line[4].strip(),
                'qty': float(split_line[5].strip()),
                'be_number': split_line[7].strip(),
                'be_date': split_line[8].strip(),
                'port': split_line[9].strip()
            }
            if row_dict['cif_inr'] == '':
                row_dict['cif_inr'] = 0
            if row_dict['cif_fc'] == '':
                row_dict['cif_fc'] = 0
            data_dict['row'].append(row_dict)
    company, bool = CompanyModel.objects.get_or_create(iec=data_dict['iec'])
    license, bool = LicenseDetailsModel.objects.get_or_create(license_number=data_dict['lic_no'])
    license.license_date = data_dict['lic_date']
    license.exporter_id = company.pk
    license.notification_number = data_dict['notification']
    license.registration_number = data_dict['regn_no']
    license.registration_date = data_dict['registration_date']
    license.port, bool = PortModel.objects.get_or_create(code=data_dict['port'])
    license.scheme_code = data_dict['scheme_code']
    if not license.ledger_date or data_dict['ledger_date'].date() > license.ledger_date:
        license.ledger_date = data_dict['ledger_date']
    license.save()
    exp, bool = LicenseExportItemModel.objects.get_or_create(license=license)
    exp.net_quantity = data_dict['total_quantity']
    exp.cif_fc = data_dict['cif_fc']
    exp.cif_inr = data_dict['cif_inr']
    exp.save()
    for row in data_dict['row']:
        if row['qty'] == "":
            row['qty'] = 0
        if row['be_date'] == "":
            datetime_object = None
        else:
            datetime_object = datetime.datetime.strptime(row['be_date'], '%d/%m/%Y')
        row_obj, bool = LicenseImportItemsModel.objects.get_or_create(serial_number=row['sr_no'], license=license)
        if row['type'] == Credit:
            row_obj.quantity = float(row['qty'])
            row_obj.cif_fc = float(row['cif_fc'])
            row_obj.cif_inr = float(row['cif_inr'])
            row_obj.save()
        if row['type'] == 'C':
            drow_obj, bool = RowDetails.objects.get_or_create(sr_number=row_obj, transaction_type=row['type'])
            drow_obj.cif_inr = row['cif_inr']
            drow_obj.cif_fc = row['cif_fc']
            drow_obj.qty = float(row['qty'])
            drow_obj.save()
        else:
            boe_port, bool = PortModel.objects.get_or_create(code=row['port'])
            bill_of_entry, bool = BillOfEntryModel.objects.get_or_create(bill_of_entry_number=row['be_number'],
                                                                         bill_of_entry_date=datetime_object,
                                                                         port=boe_port)
            drow_obj, bool = RowDetails.objects.get_or_create(sr_number=row_obj, transaction_type=row['type'],
                                                              bill_of_entry=bill_of_entry)
            drow_obj.cif_inr = row['cif_inr']
            drow_obj.cif_fc = row['cif_fc']
            drow_obj.qty = float(row['qty'])
            drow_obj.save()
    return license.id
