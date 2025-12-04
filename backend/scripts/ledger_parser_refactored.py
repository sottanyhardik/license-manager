"""
Refactored ledger parser with improved error handling and maintainability.
Consolidates parse_file and parse_license_data into a single, robust parser.
"""
import io
import csv
import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

from django.db import transaction
from django.db.models import Q

from bill_of_entry.models import BillOfEntryModel, RowDetails
from bill_of_entry.tasks import update_balance_values_task
from core.models import CompanyModel, PortModel
from license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseExportItemModel


class DateParser:
    """Utility class for parsing dates in multiple formats."""

    DATE_FORMATS = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y/%m/%d",
        "%Y-%m-%d",
    ]

    @classmethod
    def parse(cls, date_str: str) -> Optional[datetime.date]:
        """Parse date string in multiple formats."""
        if not date_str:
            return None

        date_str = date_str.strip()

        for fmt in cls.DATE_FORMATS:
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except (ValueError, TypeError):
                continue

        return None

    @classmethod
    def parse_or_today(cls, date_str: str) -> datetime.date:
        """Parse date or return today's date if parsing fails."""
        result = cls.parse(date_str)
        return result if result else datetime.date.today()


class LedgerParser:
    """Main parser for DFIA ledger files (CSV or text format)."""

    def __init__(self, file_content: str):
        """
        Initialize parser with file content.

        Args:
            file_content: Raw text content of ledger file
        """
        self.content = file_content.replace('\xa0', '').replace('Â', '')
        self.licenses = []

    def parse_csv(self, rows: List[List[str]]) -> List[Dict]:
        """
        Parse CSV rows into structured license data.

        Args:
            rows: List of CSV rows

        Returns:
            List of license dictionaries
        """
        dict_list = []
        current = None

        for row in rows:
            # Skip empty rows
            if not any(cell.strip() for cell in row):
                continue

            if len(row) < 2:
                continue

            # Start of new license block
            if row[0] == "Regn.No.":
                if current:
                    dict_list.append(current)

                # Normalize license number (ensure 10 digits)
                lic_no = row[5].strip() if len(row) > 5 else ""
                if len(lic_no) == 9:
                    lic_no = "0" + lic_no

                current = {
                    "ledger_date": datetime.date.today(),
                    "registration_no": row[1].strip() if len(row) > 1 else "",
                    "registration_date": row[3].strip() if len(row) > 3 else "",
                    "lic_no": lic_no,
                    "lic_date": row[7].strip() if len(row) > 7 else "",
                    "row": []
                }

            elif current and row[0] == "RANo.":
                current["port"] = row[5].strip() if len(row) > 5 else ""

            elif current and row[0] == "IEC":
                # Normalize IEC (ensure 10 digits)
                iec = row[1].strip() if len(row) > 1 else ""
                if len(iec) == 9:
                    iec = "0" + iec

                current["iec"] = iec
                current["scheme_code"] = row[3].strip() if len(row) > 3 else ""
                current["notification"] = row[5].strip() if len(row) > 5 else ""
                current["foregin_currency"] = row[7].strip() if len(row) > 7 else "USD"

            elif current and row[0].lower() == "tot.duty":
                current["cif_inr"] = self._parse_decimal(row[3]) if len(row) > 3 else Decimal('0')
                current["total_quantity"] = self._parse_decimal(row[5]) if len(row) > 5 else Decimal('0')
                current["cif_fc"] = self._parse_decimal(row[7]) if len(row) > 7 else Decimal('0')

            elif current and row[0].lower() in ["credit-", "debit-"]:
                txn = self._parse_transaction(row)
                if txn:
                    current["row"].append(txn)

        # Add last license
        if current:
            dict_list.append(current)

        return dict_list

    def _parse_transaction(self, row: List[str]) -> Optional[Dict]:
        """Parse credit or debit transaction row."""
        if len(row) < 6:
            return None

        txn_type = 'C' if row[0].lower() == 'credit-' else 'D'

        txn = {
            "type": txn_type,
            "sr_no": int(row[1]) if row[1].strip().isdigit() else None,
            "cif_inr": self._parse_decimal(row[3]) if len(row) > 3 else Decimal('0'),
            "cif_fc": self._parse_decimal(row[4]) if len(row) > 4 else Decimal('0'),
            "qty": self._parse_decimal(row[5]) if len(row) > 5 else Decimal('0'),
        }

        # Debit transactions have BE details
        if txn_type == 'D':
            txn["be_number"] = row[7].strip() if len(row) > 7 else None
            txn["be_date"] = DateParser.parse(row[8]) if len(row) > 8 else None
            txn["port"] = row[9].strip() if len(row) > 9 else None
        else:
            txn["be_number"] = None
            txn["be_date"] = None
            txn["port"] = None

        return txn

    @staticmethod
    def _parse_decimal(value: str) -> Decimal:
        """Safely parse string to Decimal."""
        try:
            return Decimal(str(value).strip()) if value else Decimal('0')
        except:
            return Decimal('0')


class LedgerProcessor:
    """Processes parsed ledger data into database objects."""

    @staticmethod
    def process_license(data_dict: Dict) -> str:
        """
        Create or update license and all related objects from parsed data.

        Args:
            data_dict: Parsed license dictionary

        Returns:
            License number
        """
        # Get or create company
        company, _ = CompanyModel.objects.get_or_create(
            iec=data_dict['iec'],
            defaults={'name': f"IEC {data_dict['iec']}"}
        )

        # Parse dates
        lic_date = DateParser.parse_or_today(data_dict['lic_date'])
        reg_date = DateParser.parse_or_today(data_dict['registration_date'])
        ledger_date = data_dict.get('ledger_date', datetime.date.today())

        # Get or create port
        port, _ = PortModel.objects.get_or_create(code=data_dict['port'])

        # Create or update license
        license, _ = LicenseDetailsModel.objects.update_or_create(
            license_number=data_dict['lic_no'],
            defaults={
                'license_date': lic_date,
                'exporter_id': company.pk,
                'notification_number': data_dict.get('notification', ''),
                'registration_number': data_dict.get('registration_no', ''),
                'registration_date': reg_date,
                'port': port,
                'scheme_code': data_dict.get('scheme_code', ''),
                'ledger_date': ledger_date
            }
        )

        # Create or update export item
        LicenseExportItemModel.objects.update_or_create(
            license=license,
            defaults={
                'net_quantity': data_dict.get('total_quantity', 0),
                'cif_fc': data_dict.get('cif_fc', 0),
                'cif_inr': data_dict.get('cif_inr', 0),
            }
        )

        # Separate credit and debit transactions
        credit_txns = [t for t in data_dict.get('row', []) if t['type'] == 'C']
        debit_txns = [t for t in data_dict.get('row', []) if t['type'] == 'D']

        # Process credits (import items)
        license_items = LedgerProcessor._process_import_items(license, credit_txns)

        # Process debits (BOE items)
        if debit_txns:
            LedgerProcessor._process_boe_items(license, debit_txns, license_items)

        # Update balances
        for import_item in license.import_license.all():
            update_balance_values_task.delay(import_item.id)

        return license.license_number

    @staticmethod
    def _process_import_items(license, credit_txns: List[Dict]) -> Dict[int, LicenseImportItemsModel]:
        """Create or update license import items from credit transactions."""
        items_to_create = []
        items_to_update = []

        # Get existing items
        serial_numbers = [t['sr_no'] for t in credit_txns if t.get('sr_no')]
        existing_items = LicenseImportItemsModel.objects.filter(
            license=license,
            serial_number__in=serial_numbers
        )
        existing_map = {item.serial_number: item for item in existing_items}

        # Prepare create/update lists
        for txn in credit_txns:
            sr_no = txn.get('sr_no')
            if not sr_no:
                continue

            if sr_no in existing_map:
                item = existing_map[sr_no]
                item.quantity = txn.get('qty', 0)
                item.cif_fc = txn.get('cif_fc', 0)
                item.cif_inr = txn.get('cif_inr', 0)
                items_to_update.append(item)
            else:
                items_to_create.append(LicenseImportItemsModel(
                    license=license,
                    serial_number=sr_no,
                    quantity=txn.get('qty', 0),
                    cif_fc=txn.get('cif_fc', 0),
                    cif_inr=txn.get('cif_inr', 0)
                ))

        # Bulk operations
        with transaction.atomic():
            if items_to_create:
                LicenseImportItemsModel.objects.bulk_create(items_to_create)
            if items_to_update:
                LicenseImportItemsModel.objects.bulk_update(
                    items_to_update,
                    ['quantity', 'cif_fc', 'cif_inr']
                )

        # Return updated map
        all_items = LicenseImportItemsModel.objects.filter(
            license=license,
            serial_number__in=serial_numbers
        )
        return {item.serial_number: item for item in all_items}

    @staticmethod
    def _process_boe_items(license, debit_txns: List[Dict], license_items: Dict):
        """Create or update BOE items from debit transactions."""
        # Ensure all ports exist
        ports_needed = {t['port'] for t in debit_txns if t.get('port')}
        existing_ports = PortModel.objects.filter(code__in=ports_needed)
        existing_port_codes = {p.code for p in existing_ports}

        ports_to_create = [
            PortModel(code=code)
            for code in ports_needed if code not in existing_port_codes
        ]
        if ports_to_create:
            PortModel.objects.bulk_create(ports_to_create)

        # Get all ports
        all_ports = PortModel.objects.filter(code__in=ports_needed)
        port_map = {p.code: p for p in all_ports}

        # Create BOEs
        boe_keys = set()
        boes_to_create = []

        for txn in debit_txns:
            be_num = txn.get('be_number')
            be_date = txn.get('be_date')
            port_code = txn.get('port')

            if not all([be_num, be_date, port_code]):
                continue

            key = (be_num, be_date, port_code)
            boe_keys.add(key)

        # Check existing BOEs
        existing_boes = BillOfEntryModel.objects.filter(
            bill_of_entry_number__in=[k[0] for k in boe_keys],
            bill_of_entry_date__in=[k[1] for k in boe_keys]
        )
        existing_boe_keys = {
            (b.bill_of_entry_number, b.bill_of_entry_date, b.port.code)
            for b in existing_boes
        }

        # Create missing BOEs
        for be_num, be_date, port_code in boe_keys:
            if (be_num, be_date, port_code) not in existing_boe_keys:
                boes_to_create.append(BillOfEntryModel(
                    bill_of_entry_number=be_num,
                    bill_of_entry_date=be_date,
                    port=port_map[port_code]
                ))

        if boes_to_create:
            with transaction.atomic():
                BillOfEntryModel.objects.bulk_create(boes_to_create)

        # Get all BOEs
        all_boes = BillOfEntryModel.objects.filter(
            bill_of_entry_number__in=[k[0] for k in boe_keys],
            bill_of_entry_date__in=[k[1] for k in boe_keys]
        )
        boe_map = {
            (b.bill_of_entry_number, b.bill_of_entry_date, b.port.code): b
            for b in all_boes
        }

        # Create row details
        rows_to_create = []
        rows_to_update = []

        for txn in debit_txns:
            sr_no = txn.get('sr_no')
            be_num = txn.get('be_number')
            be_date = txn.get('be_date')
            port_code = txn.get('port')

            if not all([sr_no, be_num, be_date, port_code]):
                continue

            license_item = license_items.get(sr_no)
            boe = boe_map.get((be_num, be_date, port_code))

            if not (license_item and boe):
                continue

            # Check if row detail exists
            existing_row = RowDetails.objects.filter(
                bill_of_entry=boe,
                sr_number=license_item,
                transaction_type='D'
            ).first()

            if existing_row:
                existing_row.cif_inr = txn.get('cif_inr', 0)
                existing_row.cif_fc = txn.get('cif_fc', 0)
                existing_row.qty = txn.get('qty', 0)
                rows_to_update.append(existing_row)
            else:
                rows_to_create.append(RowDetails(
                    bill_of_entry=boe,
                    sr_number=license_item,
                    transaction_type='D',
                    cif_inr=txn.get('cif_inr', 0),
                    cif_fc=txn.get('cif_fc', 0),
                    qty=txn.get('qty', 0)
                ))

        # Bulk operations
        with transaction.atomic():
            if rows_to_create:
                RowDetails.objects.bulk_create(rows_to_create)
            if rows_to_update:
                RowDetails.objects.bulk_update(
                    rows_to_update,
                    ['cif_inr', 'cif_fc', 'qty']
                )


def process_ledger_file(file_content: str, is_csv: bool = True) -> List[str]:
    """
    Main entry point for processing ledger files.

    Args:
        file_content: Raw file content (CSV or text)
        is_csv: Whether the file is CSV format

    Returns:
        List of created/updated license numbers
    """
    parser = LedgerParser(file_content)

    if is_csv:
        # Parse CSV
        csvfile = io.StringIO(file_content)
        reader = csv.reader(csvfile)
        rows = [row for row in reader if any(field.strip() for field in row)]
        licenses_data = parser.parse_csv(rows)
    else:
        # TODO: Implement text parsing if needed
        raise NotImplementedError("Text format parsing not yet implemented")

    # Process each license
    created_licenses = []
    for data_dict in licenses_data:
        try:
            lic_no = LedgerProcessor.process_license(data_dict)
            created_licenses.append(lic_no)
        except Exception as e:
            print(f"Error processing license {data_dict.get('lic_no', 'Unknown')}: {e}")
            raise

    return created_licenses
