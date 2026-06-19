import datetime
import logging

from django.db import transaction
from django.db.models import Q

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.models import CompanyModel, NotificationNumber, PortModel, SchemeCode
from apps.core.scripts.calculate_balance import update_balance_values
from apps.license.models import (
    LicenseBalance,
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
)

logger = logging.getLogger(__name__)


def parse_date(date_str):
    from datetime import datetime
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


_PAGE_HEADER_PREFIXES = (
    "pageno:", "indiancustoms", "itemwiseledger", "jnch,", "icdb",
    "description", "[e]->", "[p]->", "dated", "no.of", "totalpages",
)


def _is_page_header(row):
    """Return True for ICEGATE pagination/footer rows that should be skipped."""
    if not row or not row[0]:
        return False
    r0 = row[0].lower()
    return any(r0.startswith(p) for p in _PAGE_HEADER_PREFIXES)


def parse_license_data(rows):
    """
    Parses a list of rows (from CSV or OCR extraction) into structured dict_list based on license groupings.
    Each new 'Regn.No' row marks the beginning of a new license section.
    Multi-page ICEGATE continuation pages (Page No:-N, Indian Customs headers, etc.)
    are silently skipped while the active license context is preserved.
    """
    dict_list = []
    current = None

    for row in rows:
        if not any(cell.strip() for cell in row):
            continue

        if len(row) < 2:
            continue

        if _is_page_header(row):
            continue

        # Detect start of new license block
        # Strip UTF-8 BOM (\ufeff) that Excel/Windows adds to the first cell
        if row[0].lstrip('\ufeff') == "Regn.No.":
            if current:
                dict_list.append(current)
            lic_no = row[5] if len(row) > 5 else ""
            if len(lic_no) == 9:
                lic_no = "0" + lic_no
            current = {
                "ledger_date": datetime.datetime.now().date(),
                "registration_no": row[1],
                "registration_date": row[3],
                "lic_no": lic_no,
                "lic_date": row[7] if len(row) > 7 else "",
                "row": []
            }

        elif current is None:
            # No license context yet — skip metadata rows before first Regn.No.
            continue

        elif row[0] == "RANo.":
            current["port"] = row[5] if len(row) > 5 else ""

        elif row[0] == "IEC":
            iec = row[1] if len(row) > 1 else ""
            if len(iec) == 9:
                iec = "0" + iec
            current["iec"] = iec
            current["scheme_code"] = row[3] if len(row) > 3 else ""
            current["notification"] = row[5] if len(row) > 5 else ""
            current["foregin_currency"] = row[7] if len(row) > 7 else ""

        elif row[0].lower() == "tot.duty":
            current["cif_inr"] = float(row[3]) if len(row) > 3 and row[3] else 0
            current["total_quantity"] = float(row[5]) if len(row) > 5 and row[5] else 0
            current["cif_fc"] = float(row[7]) if len(row) > 7 and row[7] else 0

        elif row[0].lower() in ("credit-", "debit-"):
            sr_no = int(row[1]) if len(row) > 1 and row[1] else None
            if sr_no is None:
                continue
            is_credit = row[0].lower() == "credit-"
            txn = {
                "type": "C" if is_credit else "D",
                "sr_no": sr_no,
                "cif_inr": float(row[3]) if len(row) > 3 and row[3] else 0,
                "cif_fc": float(row[4]) if len(row) > 4 and row[4] else 0,
                "qty": float(row[5]) if len(row) > 5 and row[5] else 0,
                "be_number": row[7] if len(row) > 7 else None,
                "be_date": None if is_credit else (parse_date(row[8]) if len(row) > 8 else None),
                "port": row[9] if len(row) > 9 else None,
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
    from apps.license.models import update_balance
    from apps.license.signals import update_license_on_import_item_change, update_license_on_import_item_delete

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
    """Bulk create Bill of Entry records.

    Dedup is by (bill_of_entry_number, bill_of_entry_date) — matching the unique
    constraint on the model. If a BOE with the same number+date already exists
    with a different port, the existing record wins; we do not create a duplicate.
    """
    # Skip debit rows with missing be_number or port — can't create/find a BOE without them
    type_debit_list = [
        item for item in type_debit_list
        if item.get("be_number") and item.get("port") and item["port"] in existing_ports
    ]
    if not type_debit_list:
        return {}

    unique_bill_entries = {}

    for item in type_debit_list:
        try:
            date_object = datetime.datetime.strptime(item["be_date"], "%Y/%m/%d")
            item["be_date"] = date_object.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            try:
                item["be_date"] = item["be_date"].strftime("%Y-%m-%d")
            except AttributeError:
                pass
        key = (item["be_number"], item["be_date"])
        unique_bill_entries[key] = item

    existing = BillOfEntryModel.objects.filter(
        bill_of_entry_number__in=[k[0] for k in unique_bill_entries.keys()],
        bill_of_entry_date__in=[k[1] for k in unique_bill_entries.keys()],
    )

    existing_set = set(
        (be.bill_of_entry_number, be.bill_of_entry_date.strftime('%Y-%m-%d'))
        for be in existing
    )

    to_create = []
    for (be_number, be_date), item in unique_bill_entries.items():
        if (be_number, be_date) not in existing_set:
            port_model = existing_ports[item["port"]]
            to_create.append(
                BillOfEntryModel(
                    bill_of_entry_number=be_number,
                    bill_of_entry_date=be_date,
                    port_id=port_model.id,
                )
            )

    with transaction.atomic():
        BillOfEntryModel.objects.bulk_create(to_create)

    result = BillOfEntryModel.objects.filter(
        bill_of_entry_number__in=[k[0] for k in unique_bill_entries.keys()],
        bill_of_entry_date__in=[k[1] for k in unique_bill_entries.keys()],
    )

    return {
        be.bill_of_entry_number: be
        for be in result
    }


def delete_stale_boe_rows(license, new_debit_row, skip_signals=False):
    """
    Flag debit RowDetails for this license that no longer appear in the
    freshly uploaded ledger CSV as dispute (is_dispute=True) instead of
    deleting them, so they can be reviewed and resolved manually.

    Also clears the dispute flag on rows that ARE present in the new upload
    (re-upload of the same ledger resolves the dispute).

    Returns a tuple: (flagged_count, resolved_count).
    """
    # Build the set of (boe_id, sr_number_id) present in the new upload
    new_row_keys = set()
    for data in new_debit_row:
        boe = data.get('boe')
        licence = data.get('licence')
        if boe and licence:
            new_row_keys.add((boe.id, licence.id))

    # Fetch all existing debit RowDetails for this license
    existing_rows = list(
        RowDetails.objects.filter(
            sr_number__license=license,
            transaction_type='D'
        ).select_related('bill_of_entry', 'sr_number')
    )

    stale_ids   = []
    present_ids = []
    for rd in existing_rows:
        key = (rd.bill_of_entry_id, rd.sr_number_id)
        if key not in new_row_keys:
            stale_ids.append(rd.id)
        else:
            present_ids.append(rd.id)

    # Flag stale rows as dispute
    flagged_count = 0
    if stale_ids:
        flagged_count = RowDetails.objects.filter(
            id__in=stale_ids, is_dispute=False
        ).update(is_dispute=True)

    # Clear dispute flag on rows that appear in the new upload
    resolved_count = 0
    if present_ids:
        resolved_count = RowDetails.objects.filter(
            id__in=present_ids, is_dispute=True
        ).update(is_dispute=False)

    return flagged_count, resolved_count


def bulk_get_or_create_boe(boe_row, skip_signals=False):
    """
    Bulk create or update BOE row details.

    Args:
        boe_row: List of row data to process
        skip_signals: If True, temporarily disable post_save signals during bulk operations
    """
    from django.db.models.signals import post_save, post_delete
    from apps.bill_of_entry.models import update_stock, delete_stock

    # Skip rows that are missing licence (import item) — can't create RowDetails without it
    valid_items = [item for item in boe_row if item.get('licence') is not None]
    if not valid_items:
        return

    row_details_list = [
        RowDetails(
            bill_of_entry=item['boe'],
            sr_number=item['licence'],
            transaction_type=item['type'],
            cif_inr=item['cif_inr'],
            cif_fc=item['cif_fc'],
            qty=item['qty'],
            is_frozen=True,  # Rows from ledger upload are frozen — cannot be edited from frontend
        ) for item in valid_items
    ]

    # Sort by (bill_of_entry_id, sr_number_id) so the FK share-locks Postgres
    # takes on parent BOE/LicenseImportItem rows are acquired in a deterministic
    # global order — prevents deadlocks between concurrent uploads that share BOEs.
    row_details_list.sort(key=lambda r: (
        r.bill_of_entry_id or 0,
        r.sr_number_id or 0,
        r.transaction_type,
    ))

    with transaction.atomic():
        # Build the existence query correctly for both credit (null BOE) and debit rows.
        # Django's bill_of_entry__in=[None] does NOT find NULL FK rows in PostgreSQL,
        # so we must use bill_of_entry__isnull=True for credit rows explicitly.
        credit_sr_numbers = [
            row.sr_number for row in row_details_list if row.bill_of_entry is None
        ]
        debit_rows = [row for row in row_details_list if row.bill_of_entry is not None]

        query = Q()
        if credit_sr_numbers:
            query |= Q(
                bill_of_entry__isnull=True,
                sr_number__in=credit_sr_numbers,
                transaction_type='C',
            )
        if debit_rows:
            query |= Q(
                bill_of_entry__in=[row.bill_of_entry for row in debit_rows],
                sr_number__in=[row.sr_number for row in debit_rows],
                transaction_type='D',
            )

        existing_rows = RowDetails.objects.filter(query) if query else RowDetails.objects.none()
        rows_dict = {
            (row.bill_of_entry_id, row.sr_number_id, row.transaction_type): row
            for row in existing_rows
        }
        new_rows = []
        update_rows = []
        for row in row_details_list:
            # Use PK-based key to avoid ORM object identity issues
            boe_id = row.bill_of_entry_id if row.bill_of_entry else None
            sr_id = row.sr_number_id if row.sr_number else None
            key = (boe_id, sr_id, row.transaction_type)
            if key not in rows_dict:
                new_rows.append(row)
            else:
                update_row = rows_dict[key]
                update_row.cif_inr = row.cif_inr
                update_row.cif_fc = row.cif_fc
                update_row.qty = row.qty
                update_row.is_frozen = True
                update_rows.append(update_row)

        if skip_signals:
            post_save.disconnect(update_stock, sender=RowDetails, dispatch_uid="update_stock_on_save")
            post_delete.disconnect(delete_stock, sender=RowDetails)

        try:
            RowDetails.objects.bulk_create(new_rows, ignore_conflicts=False)
            RowDetails.objects.bulk_update(update_rows, ['cif_inr', 'cif_fc', 'qty', 'is_frozen'])
        finally:
            if skip_signals:
                post_save.connect(update_stock, sender=RowDetails, dispatch_uid="update_stock_on_save")
                post_delete.connect(delete_stock, sender=RowDetails)


def _recalculate_boe_exchange_rates_for_rows(debit_row):
    """After bulk_create (which skips signals), force-recalculate exchange_rate for
    each unique BOE in the debit rows. force=True always writes the computed rate,
    overriding whatever was stored before (ledger is the authoritative source).

    BOE PKs are sorted before iteration so concurrent uploads acquire row locks in
    the same global order, preventing deadlocks on overlapping BOEs.
    """
    from apps.bill_of_entry.models import _recalculate_boe_exchange_rate
    boe_pks = sorted({
        data['boe'].pk for data in debit_row
        if data.get('boe') and data['boe'].pk
    })
    for pk in boe_pks:
        _recalculate_boe_exchange_rate(pk, force=True)


def create_object(data_dict):
    """
    Create or update license and related objects from parsed ledger data.
    Returns the license number.
    Wrapped in transaction.atomic() so each license is all-or-nothing.
    """
    with transaction.atomic():
        return _create_object_inner(data_dict)


def _create_object_inner(data_dict):
    # Get or create company
    company, _ = CompanyModel.objects.get_or_create(iec=data_dict['iec'])
    scheme_code = None
    if data_dict.get('scheme_code'):
        scheme_code, _ = SchemeCode.objects.get_or_create(
            code=data_dict['scheme_code'],
            defaults={'label': data_dict['scheme_code']},
        )
    notification_number = None
    if data_dict.get('notification'):
        notification_number, _ = NotificationNumber.objects.get_or_create(
            code=data_dict['notification'],
            defaults={'label': data_dict['notification']},
        )

    # Update or create license
    license, _ = LicenseDetailsModel.objects.update_or_create(
        license_number=data_dict['lic_no'],
        defaults={
            'license_date': datetime.datetime.strptime(data_dict['lic_date'], '%d/%m/%Y').strftime('%Y-%m-%d'),
            'exporter_id': company.pk,
            'notification_number': notification_number,
            'registration_number': data_dict['registration_no'],
            'registration_date': datetime.datetime.strptime(data_dict['registration_date'], '%d/%m/%Y').strftime('%Y-%m-%d'),
            'port': PortModel.objects.get_or_create(code=data_dict['port'])[0],
            'scheme_code': scheme_code,
        }
    )
    LicenseBalance.objects.update_or_create(
        license=license,
        defaults={
            'ledger_date': (
                data_dict['ledger_date'].strftime('%Y-%m-%d')
                if isinstance(data_dict['ledger_date'], datetime.datetime)
                else data_dict['ledger_date']
            )
        },
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

    # Create ports — filter out None ports (rows with missing port data)
    port_infos = {val['port'] for val in data_dict['row'] if val['type'] == 'D' and val.get('port')}
    port_infos_with_ledger_date = {data_dict['port']} if data_dict.get('port') else set()
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

    # Flag debit rows missing from the new CSV as dispute (is_dispute=True).
    # Rows present in the new CSV get their dispute flag cleared automatically.
    flagged, resolved = delete_stale_boe_rows(license, debit_row, skip_signals=True)
    if flagged:
        logger.warning("Ledger upload: %d row(s) not found in ledger — flagged as dispute for %s", flagged, license.license_number)
    if resolved:
        logger.info("Ledger upload: %d dispute(s) resolved for %s", resolved, license.license_number)

    # Recalculate exchange rate for each debit BOE — bulk_create skips signals so
    # the post_save recalc never fires; we must do it explicitly here.
    _recalculate_boe_exchange_rates_for_rows(debit_row)

    # Trigger balance updates ONCE at the end for all items
    for import_item in license.import_license.all():
        update_balance_values(import_item)

    return license.license_number
