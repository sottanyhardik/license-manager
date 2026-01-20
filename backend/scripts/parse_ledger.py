import datetime
from django.db import transaction
from django.db.models import Q

from bill_of_entry.models import BillOfEntryModel, RowDetails
from core.models import CompanyModel, PortModel
from core.scripts.calculate_balance import update_balance_values
from license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseExportItemModel


def parse_date(date_str):
    from datetime import datetime
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


def parse_license_data(rows):
    """
    Parses a list of rows (from CSV or OCR extraction) into structured dict_list based on license groupings.
    Each new 'Regn.No' row marks the beginning of a new license section.
    """
    dict_list = []
    current = None

    for row in rows:
        # Skip completely empty rows
        if not any(cell.strip() for cell in row):
            continue

        if len(row) < 2:
            continue

        # Detect start of new license block
        if row[0] == "Regn.No.":
            if current:
                dict_list.append(current)
            if len(row[5]) == 9:
                row[5] = "0" + row[5]
            current = {
                "ledger_date": datetime.datetime.now().date(),
                "registration_no": row[1],
                "registration_date": row[3],
                "lic_no": row[5],
                "lic_date": row[7],
                "row": []
            }
        elif row[0] == "RANo.":
            current["port"] = row[5]
        elif row[0] == "IEC":
            if len(row[1]) == 9:
                row[1] = "0" + row[1]
            current["iec"] = row[1]
            current["scheme_code"] = row[3]
            current["notification"] = row[5]
            current["foregin_currency"] = row[7]

        elif row[0].lower() == "tot.duty":
            current["cif_inr"] = float(row[3]) if row[3] else 0
            current["total_quantity"] = float(row[5]) if row[5] else 0
            current["cif_fc"] = float(row[7]) if row[7] else 0

        elif row[0] and row[0].lower() in ["credit-", "debit-"]:
            if row[0].lower() == 'credit-':
                txn = {
                    "type": 'C',
                    "sr_no": int(row[1]) if row[1] else None,
                    "cif_inr": float(row[3]) if row[3] else 0,
                    "cif_fc": float(row[4]) if row[4] else 0,
                    "qty": float(row[5]) if row[5] else 0,
                    "be_number": row[7] if len(row) > 5 else None,
                    "be_date": row[8] if len(row) > 6 else None,
                    "port": row[9] if len(row) > 7 else None
                }

            else:
                txn = {
                    "type": 'D',
                    "sr_no": int(row[1]) if row[1] else None,
                    "cif_inr": float(row[3]) if row[3] else 0,
                    "cif_fc": float(row[4]) if row[4] else 0,
                    "qty": float(row[5]) if row[5] else 0,
                    "be_number": row[7] if len(row) > 5 else None,
                    "be_date": parse_date(row[8]) if len(row) > 8 else None,
                    "port": row[9] if len(row) > 7 else None
                }
            current["row"].append(txn)

    if current:
        dict_list.append(current)

    return dict_list


def bulk_get_or_create_license_items(type_credit_list, license, skip_signals=False):
    """
    Bulk create or update license import items.

    Args:
        type_credit_list: List of credit transactions
        license: License object
        skip_signals: If True, temporarily disable post_save signals during bulk operations
    """
    from django.db.models.signals import post_save, post_delete
    from license.models import update_balance
    from license.signals import update_license_on_import_item_change, update_license_on_import_item_delete

    license_import_list = [
        LicenseImportItemsModel(
            license=license,
            serial_number=item['sr_no'],
            quantity=item['qty'],
            cif_fc=item['cif_fc'],
            cif_inr=item['cif_inr']
        )
        for item in type_credit_list
    ]

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

        # Disable signals if requested (for bulk ledger upload)
        if skip_signals:
            post_save.disconnect(update_balance, sender=LicenseImportItemsModel)
            post_save.disconnect(update_license_on_import_item_change, sender=LicenseImportItemsModel)
            post_delete.disconnect(update_license_on_import_item_delete, sender=LicenseImportItemsModel)

        try:
            LicenseImportItemsModel.objects.bulk_create(new_items)
            LicenseImportItemsModel.objects.bulk_update(update_items, ['quantity', 'cif_fc', 'cif_inr'])
        finally:
            # Re-enable signals
            if skip_signals:
                post_save.connect(update_balance, sender=LicenseImportItemsModel)
                post_save.connect(update_license_on_import_item_change, sender=LicenseImportItemsModel)
                post_delete.connect(update_license_on_import_item_delete, sender=LicenseImportItemsModel)

        existing_items = LicenseImportItemsModel.objects.filter(
            Q(license=license) &
            Q(serial_number__in=[item.serial_number for item in license_import_list])
        )
        license_sr_dict = {(item.license, item.serial_number): item for item in existing_items}
        return license_sr_dict


def bulk_get_or_create_boe_details(type_debit_list, existing_ports):
    """Bulk create Bill of Entry records."""
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
        key = (item["be_number"], item["be_date"], existing_ports[item["port"]])
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


def bulk_get_or_create_boe(boe_row, skip_signals=False):
    """
    Bulk create or update BOE row details.

    Args:
        boe_row: List of row data to process
        skip_signals: If True, temporarily disable post_save signals during bulk operations
    """
    from django.db.models.signals import post_save, post_delete
    from bill_of_entry.models import update_stock, delete_stock

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
        rows_dict = {
            (row.bill_of_entry, row.sr_number, row.transaction_type): row
            for row in existing_rows
        }
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

        # Disable signals if requested (for bulk ledger upload)
        if skip_signals:
            post_save.disconnect(update_stock, sender=RowDetails, dispatch_uid="update_stock_on_save")
            post_delete.disconnect(delete_stock, sender=RowDetails)

        try:
            RowDetails.objects.bulk_create(new_rows)
            RowDetails.objects.bulk_update(update_rows, ['cif_inr', 'cif_fc', 'qty'])
        finally:
            # Re-enable signals
            if skip_signals:
                post_save.connect(update_stock, sender=RowDetails, dispatch_uid="update_stock_on_save")
                post_delete.connect(delete_stock, sender=RowDetails)


def create_object(data_dict):
    """
    Create or update license and related objects from parsed ledger data.
    Returns the license number.
    """
    # Get or create company
    company, _ = CompanyModel.objects.get_or_create(iec=data_dict['iec'])

    # Update or create license
    license, _ = LicenseDetailsModel.objects.update_or_create(
        license_number=data_dict['lic_no'],
        defaults={
            'license_date': datetime.datetime.strptime(data_dict['lic_date'], '%d/%m/%Y').strftime('%Y-%m-%d'),
            'exporter_id': company.pk,
            'notification_number': data_dict['notification'],
            'registration_number': data_dict['registration_no'],
            'registration_date': datetime.datetime.strptime(data_dict['registration_date'], '%d/%m/%Y').strftime('%Y-%m-%d'),
            'port': PortModel.objects.get_or_create(code=data_dict['port'])[0],
            'scheme_code': data_dict['scheme_code'],
            'ledger_date': data_dict['ledger_date'].strftime('%Y-%m-%d') if isinstance(data_dict['ledger_date'], datetime.datetime) else data_dict['ledger_date']
        }
    )

    # Update or create export item
    exp, _ = LicenseExportItemModel.objects.update_or_create(
        license=license,
        defaults={
            'net_quantity': data_dict['total_quantity'],
            'cif_fc': data_dict['cif_fc'],
            'cif_inr': data_dict['cif_inr'],
        }
    )

    # Create ports
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

    # Separate credit and debit transactions
    type_credit_list = []
    type_debit_list = []

    for data in data_dict.get('row'):
        if data['type'] == 'C':
            type_credit_list.append(data)
        elif data['type'] == 'D':
            type_debit_list.append(data)

    # Create license items (disable signals during bulk operations)
    license_sr_dict = bulk_get_or_create_license_items(type_credit_list, license, skip_signals=True)
    existing_entry_map = bulk_get_or_create_boe_details(type_debit_list, existing_ports)

    # Create row details
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

    # Disable signals during bulk operations to avoid firing 100+ times
    bulk_get_or_create_boe(debit_row, skip_signals=True)
    bulk_get_or_create_boe(credit_row, skip_signals=True)

    # Trigger balance updates ONCE at the end for all items
    for import_item in license.import_license.all():
        update_balance_values(import_item)

    return license.license_number
