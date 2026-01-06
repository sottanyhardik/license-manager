import datetime

from django.db.models import Q

from bill_of_entry.models import BillOfEntryModel, RowDetails
from core.models import CompanyModel, PortModel
from core.scripts.calculate_balance import update_balance_values
from license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseExportItemModel


def extract_value_from_splits(split_values):
    try:
        return split_values[1].split('\t')[0].replace(':', '').strip()
    except IndexError:
        raise IndexError(f'Extraction operation failed for the splits: {split_values}')


def extract_data(line, text):
    try:
        split_values = None
        # Determine split method based on line structure
        if '\t' in line:
            split_text = text + '\t'
            split_values = line.split(split_text)
        else:
            # Assume the line contains ' ,:' characters
            split_text = text + ' ,:'
            split_values = line.split(split_text)
        return extract_value_from_splits(split_values)
    except IndexError as e:
        raise IndexError(f'Split operation failed for the text: "{text}" in line: "{line}".\n{e}')

    except Exception as e:
        raise Exception(f'An error occurred while processing the line: "{line}" and text: "{text}".\n{e}')


# import datetime on the top

def parse_file(data):
    def extract_date(line):
        try:
            ledger_date = line.split('Dated:')[-1].strip().split(' ')[0]
            try:
                return datetime.datetime.strptime(ledger_date, '%Y/%m/%d')
            except:
                return datetime.datetime.strptime(ledger_date, '%y/%m/%d')
        except Exception:
            return datetime.datetime.now()

    # split lines
    lines = data.split('\n')

    data_dict = {
        'row': [],
        'ledger_date': None
    }

    for line in lines:
        line = line.replace(" ", '').replace('Â', '').replace('\xa0', '')
        if 'Printed By' in line:
            data_dict['ledger_date'] = extract_date(line)
        else:
            if not data_dict['ledger_date']:
                data_dict['ledger_date'] = datetime.datetime.now()

        # If 'Bal.CIF-FC' in line, skip the line
        if 'Bal.CIF-FC' in line:
            continue

        keys_mapping = {
            'Lic.Date': 'lic_date',
            'Lic.No.': 'lic_no',
            'Frgn.Curr': 'foregin_currency',
            'CIF-INR.': 'cif_inr',
            'CIF-FC': 'cif_fc',
            'Tot.Qty.': 'total_quantity',
            'IEC': 'iec',
            'Regn.No.': 'registration_no',
            'Regn.Date': 'registration_date',
            'Iss.CH.': 'port',
            'Schm.Cd.': 'scheme_code',
            'Notifcn.': 'notification'
        }

        for phrase, key in keys_mapping.items():
            if phrase in line:
                try:
                    if extract_data(line, phrase) != 'Qty':
                        data_dict[key] = extract_data(line, phrase)
                except Exception as e:
                    print(e)

        if 'Debit-' in line or 'Credit-' in line:
            split_line = line.split('\t')
            row_type = 'C' if 'Credit-' in line else 'D'
            split_line[1] = split_line[1].strip().replace('/01/00', '')
            row_dict = {
                'type': row_type,
                'sr_no': split_line[1].strip(),
                'cif_inr': split_line[3].strip() or 0,
                'cif_fc': split_line[4].strip() or 0,
                'qty': float(split_line[5].strip()) if split_line[5].strip() else 0.0,
                'be_number': split_line[7].strip() if row_type == 'D' else '',
                'be_date': '',
                'port': split_line[9].strip() if row_type == 'D' else '',
            }
            if row_type == 'D':
                try:
                    row_dict['be_date'] =datetime.datetime.strptime(split_line[8].strip(), '%d/%m/%Y').strftime('%Y/%m/%d')
                except Exception as e:
                    row_dict['be_date'] = datetime.datetime.strptime(split_line[8].strip(), '%d/%m/%y').strftime(
                        '%Y/%m/%d')
            data_dict['row'].append(row_dict)

    return data_dict


from django.db import transaction


def bulk_get_or_create_license_items(type_credit_list, license):
    license_import_list = [LicenseImportItemsModel(
        license=license,
        serial_number=item['sr_no'],
        quantity=item['qty'],
        cif_fc=item['cif_fc'],
        cif_inr=item['cif_inr']
    )
        for item in type_credit_list]
    with transaction.atomic():
        existing_items = LicenseImportItemsModel.objects.filter(
            Q(license=license) &
            Q(serial_number__in=[item.serial_number for item in license_import_list])
        )
        license_sr_dict = {(item.license, item.serial_number): item for item in existing_items}
        new_items = []
        update_items = []
        for item in license_import_list:
            if (item.license, int(item.serial_number)) not in license_sr_dict:
                new_items.append(item)
            else:
                update_item = license_sr_dict.get((item.license, int(item.serial_number)))
                update_item.quantity = item.quantity
                update_item.cif_fc = item.cif_fc
                update_item.cif_inr = item.cif_inr
                update_items.append(update_item)
        LicenseImportItemsModel.objects.bulk_create(new_items)
        LicenseImportItemsModel.objects.bulk_update(update_items, ['quantity', 'cif_fc', 'cif_inr'])
        existing_items = LicenseImportItemsModel.objects.filter(
            Q(license=license) &
            Q(serial_number__in=[item.serial_number for item in license_import_list])
        )
        license_sr_dict = {(item.license, item.serial_number): item for item in existing_items}
        return license_sr_dict




def bulk_get_or_create_boe_details(type_debit_list, existing_ports):
    unique_bill_entries = {}

    # Normalize date format and deduplicate by (be_number, be_date)
    for item in type_debit_list:
        try:
            date_object = datetime.datetime.strptime(item["be_date"], "%Y/%m/%d")
            item["be_date"] = date_object.strftime("%Y-%m-%d")
        except Exception:
            try:
                item["be_date"] = item["be_date"].strftime("%Y-%m-%d")
            except:
                pass
        key = (item["be_number"], item["be_date"],existing_ports[item["port"]])
        unique_bill_entries[key] = item

    fetch_numbers = set((k[0], k[1], k[2].id) for k in unique_bill_entries.keys())

    # Fetch existing (be_number, be_date, port) to skip them
    existing = BillOfEntryModel.objects.filter(
        bill_of_entry_number__in=[k[0] for k in fetch_numbers],
        bill_of_entry_date__in=[k[1] for k in fetch_numbers],
        port_id__in=[k[2] for k in fetch_numbers]
    )

    # Build a set of (be_number, be_date, port_id) already in DB
    existing_set = set(
        (be.bill_of_entry_number, be.bill_of_entry_date.strftime('%Y-%m-%d'), existing_ports[be.port.code])
        for be in existing
    )

    to_create = []
    for (be_number, be_date, port_id), item in unique_bill_entries.items():
        if (be_number, be_date, port_id) not in existing_set:
            to_create.append(
                BillOfEntryModel(
                    bill_of_entry_number=be_number,
                    bill_of_entry_date=be_date,
                    port_id=port_id.id,
                )
            )

    with transaction.atomic():
        BillOfEntryModel.objects.bulk_create(to_create)

    # Return all related entries
    result = BillOfEntryModel.objects.filter(
        bill_of_entry_number__in=[item['be_number'] for item in type_debit_list],
        bill_of_entry_date__in=[item['be_date'] for item in type_debit_list]
    )

    return {
        be.bill_of_entry_number: be
        for be in result
    }


def create_object(data_dict):
    # Try to retrieve existing objects before creating new ones
    company, _ = CompanyModel.objects.get_or_create(iec=data_dict['iec'])
    license, _ = LicenseDetailsModel.objects.update_or_create(
        license_number=data_dict['lic_no'],
        defaults={
            'license_date': datetime.datetime.strptime(data_dict['lic_date'], '%d/%m/%Y').strftime('%Y-%m-%d'),
            'exporter_id': company.pk,
            'notification_number': data_dict['notification'],
            'registration_number': data_dict['registration_no'],
            'registration_date': datetime.datetime.strptime(data_dict['registration_date'], '%d/%m/%Y').strftime(
                '%Y-%m-%d'),
            'port': PortModel.objects.get_or_create(code=data_dict['port'])[0],
            'scheme_code': data_dict['scheme_code'],
            'ledger_date': data_dict['ledger_date'].strftime('%Y-%m-%d')
        }

    )
    exp, _ = LicenseExportItemModel.objects.update_or_create(
        license=license,
        defaults={
            'net_quantity': data_dict['total_quantity'],
            'cif_fc': data_dict['cif_fc'],
            'cif_inr': data_dict['cif_inr'],
        }
    )
    port_infos = {val['port'] for val in data_dict['row'] if val['type'] == 'D'}
    port_infos_with_ledger_date = {data_dict['port']}
    ports_to_be_created = port_infos.union(port_infos_with_ledger_date)
    existing_ports = PortModel.objects.all().in_bulk(ports_to_be_created, field_name='code')
    ports_to_create = [
        PortModel(code=code)
        for code in ports_to_be_created if code not in existing_ports
    ]
    PortModel.objects.bulk_create(ports_to_create)
    existing_ports = PortModel.objects.all().in_bulk(ports_to_be_created, field_name='code')
    type_credit_list = []
    type_debit_list = []

    for data in data_dict.get('row'):
        if data['type'] == 'C':
            type_credit_list.append(data)
        elif data['type'] == 'D':
            type_debit_list.append(data)
    license_sr_dict = bulk_get_or_create_license_items(type_credit_list, license)
    existing_entry_map = bulk_get_or_create_boe_details(type_debit_list, existing_ports)
    data_list = data_dict.get('row')
    credit_row = []
    debit_row = []
    for data in data_list:
        data['licence'] = license_sr_dict.get((license, int(data['sr_no'])))
        if data.get('type') == 'D':
            data['boe'] = existing_entry_map.get(data['be_number'])
            debit_row.append(data)
        else:
            data['boe'] = None
            credit_row.append(data)
    bulk_get_or_create_boe(debit_row)
    bulk_get_or_create_boe(credit_row)
    # Update balances (synchronous for faster response)
    for import_item in license.import_license.all():
        update_balance_values(import_item)
    return license.license_number


def fetch_page_data(data):
    data_dict = parse_file(data)
    licence_number = create_object(data_dict)
    return licence_number


def bulk_get_or_create_boe(boe_row):
    row_details_list = [
        RowDetails(
            bill_of_entry=item['boe'],
            sr_number=item['licence'],
            transaction_type=item['type'],
            cif_inr=item['cif_inr'],
            cif_fc=item['cif_fc'],
            qty=item['qty']
        ) for item in boe_row
    ]
    with transaction.atomic():
        existing_rows = RowDetails.objects.filter(
            Q(bill_of_entry__in=[row.bill_of_entry for row in row_details_list]),
            Q(sr_number__in=[row.sr_number for row in row_details_list]),
            Q(transaction_type='D'),
        )
        rows_dict = {(row.bill_of_entry, row.sr_number, row.transaction_type): row for
                     row in existing_rows}
        new_rows = []
        update_rows = []
        for row in row_details_list:
            key = (row.bill_of_entry, row.sr_number, row.transaction_type)
            if key not in rows_dict:
                new_rows.append(row)
            else:
                update_row = rows_dict.get(key)
                update_row.cif_inr = row.cif_inr
                update_row.cif_fc = row.cif_fc
                update_row.qty = row.qty
                update_rows.append(update_row)
        RowDetails.objects.bulk_create(new_rows)
        RowDetails.objects.bulk_update(update_rows, ['cif_inr', 'cif_fc', 'qty'])
