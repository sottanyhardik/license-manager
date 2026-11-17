"""Group BOEs for the grouped exports (moved verbatim from api/views_export.py)."""
from collections import defaultdict
from decimal import Decimal

from apps.bill_of_entry.api.serializers import BillOfEntrySerializer

from .common import _decimal_or_default


def group_boe(queryset):
    """Group bill of entries by company → license_serial_number → product_name → port"""
    # Structure: {company: {license_serial: {product_name: {port: [boe_list]}}}}
    grouped_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))

    for boe in queryset:
        # Totals from the prefetched rows (identical Decimals, no per-BOE SUM queries).
        BillOfEntrySerializer._seed_totals_from_prefetch(boe)
        company_name = boe.company.name if boe.company else "Unknown"
        port_code = boe.port.code if boe.port else "Unknown Port"
        # Normalize product name: uppercase, strip spaces for grouping
        raw_product_name = boe.product_name or "Unknown Product"
        product_name = raw_product_name.strip().upper()

        # Get first license serial number from item details
        item_details = list(boe.item_details.all())
        first_item = item_details[0] if item_details else None
        license_serial = "Unknown License"
        if first_item and first_item.sr_number:
            license_obj = first_item.sr_number.license if first_item.sr_number else None
            if license_obj:
                license_serial = f"{license_obj.license_number} (Sr. {first_item.sr_number.serial_number})"

        # Collect license details for this BOE
        license_details = []
        for detail in item_details:
            license_obj = detail.sr_number.license if detail.sr_number else None

            # Store exporter name and license number separately
            if license_obj:
                exporter_name = license_obj.exporter.name if license_obj.exporter else '--'
                license_number = license_obj.license_number
            else:
                exporter_name = '--'
                license_number = '--'

            license_details.append({
                'exporter_name': exporter_name,
                'license_no': license_number,
                'license_port': license_obj.port.code if (license_obj and license_obj.port) else '--',
                'license_date': (
                    license_obj.license_date.strftime('%d-%m-%Y')
                    if license_obj and license_obj.license_date
                    else '--'
                ),
                'item_sr_no': str(detail.sr_number.serial_number) if detail.sr_number else '--',
                'qty': _decimal_or_default(detail.qty),
                'cif_fc': _decimal_or_default(detail.cif_fc),
                'cif_inr': _decimal_or_default(detail.cif_inr),
            })

        # Calculate exchange rate: use boe.exchange_rate if exists, otherwise calculate from total_inr / total_fc
        total_fc = _decimal_or_default(boe.get_total_fc)
        total_inr = _decimal_or_default(boe.get_total_inr)

        boe_exchange_rate = _decimal_or_default(boe.exchange_rate)
        if boe_exchange_rate > 0:
            exchange_rate = boe_exchange_rate
        elif total_fc > 0:
            exchange_rate = total_inr / total_fc
        else:
            exchange_rate = Decimal('0')

        boe_data = {
            'boe_number': boe.bill_of_entry_number or '--',
            'boe_date': boe.bill_of_entry_date.strftime('%d-%m-%Y') if boe.bill_of_entry_date else '--',
            'port': port_code,
            'product_name': product_name,
            'invoice_no': boe.invoice_no or '--',
            'total_quantity': _decimal_or_default(boe.get_total_quantity),
            'total_fc': total_fc,
            'total_inr': total_inr,
            'exchange_rate': exchange_rate,  # Add exchange rate
            'license_details': license_details,  # List of license entries
        }

        grouped_data[company_name][license_serial][product_name][port_code].append(boe_data)

    return grouped_data
