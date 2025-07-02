import csv
from django.db.models import Sum
from core.management.commands.report_fetch import fetch_total
from license.models import LicenseDetailsModel


def fetch_data(list1):
    conf_list = []
    for a in list1:
        data_dict = {
            'DFIA No': "'" + a
        }

        try:
            dfia = LicenseDetailsModel.objects.get(license_number=a)

            if dfia.license_date:
                data_dict['DFIA Dt'] = dfia.license_date.strftime('%d/%m/%Y')
            if dfia.license_expiry_date:
                data_dict['DFIA Exp'] = dfia.license_expiry_date.strftime('%d/%m/%Y')
            if dfia.exporter:
                data_dict['Exporter'] = str(dfia.exporter)
            if dfia.port:
                data_dict['PORT'] = str(dfia.port)
            if dfia.ledger_date:
                data_dict['Ledger Date'] = dfia.ledger_date.strftime('%d/%m/%Y')

            data_dict['Notf No'] = dfia.notification_number
            data_dict['TOTAL CIF'] = float(dfia.opening_balance)
            data_dict['BAL CIF'] = float(dfia.get_balance_cif)

            two_percent = int(dfia.opening_balance * 0.02)
            five_percent = int(dfia.opening_balance * 0.05)
            data_dict['2% of CIF'] = two_percent
            data_dict['2% of CIF Balance'] = dfia.get_per_cif.get('twoRestriction')
            data_dict['5% of CIF'] = five_percent
            data_dict['5% of CIF Balance'] = dfia.get_per_cif.get('fiveRestriction')
            data_dict['Is Individual'] = dfia.is_individual
            data_dict['Is Conversion'] = ""

            if dfia.export_license.all().first().old_quantity != 0.0 or dfia.notification_number == '098/2009':
                data_dict.update({
                    '2% of CIF Utilized': 0,
                    '2% of CIF Balance': 0,
                    '5% of CIF Utilized': 0,
                    '5% of CIF Balance': 0,
                    '2% of CIF': 0,
                    '5% of CIF': 0
                })
                if dfia.export_license.all().first().old_quantity != 0.0:
                    data_dict['Is Conversion'] = True
            else:
                data_dict['2% of CIF Utilized'] = two_percent - data_dict['2% of CIF Balance']
                data_dict['5% of CIF Utilized'] = five_percent - data_dict['5% of CIF Balance']

            # Helper function to populate import item fields
            def add_import_data(key_prefix, import_item):
                data_dict[f'HSN {key_prefix}'] = "'" + import_item.get('hs_code__hs_code')
                data_dict[f'BAL {key_prefix} Qty'] = import_item.get('available_quantity_sum')
                data_dict[f'Total {key_prefix} Qty'] = import_item.get('quantity_sum')

            add_import_data("Juice", dfia.get_juice)
            add_import_data("Other", dfia.get_other_confectionery)
            add_import_data("TARTARIC", dfia.get_tartaric_acid)
            add_import_data("ESSENTIAL OIL", dfia.get_essential_oil)
            add_import_data("PP", dfia.get_pp)
            add_import_data("Aluminium Foil", dfia.get_aluminium)
            add_import_data("Paper", dfia.get_paper_and_paper)

        except Exception as e:
            print(f"Error processing DFIA {a}: {e}")

        conf_list.append(data_dict)
    return conf_list


def generate_excel(conf_list):
    with open('conf.csv', 'w', newline='') as csvfile:
        fieldnames = [
            'DFIA No', 'DFIA Dt', 'DFIA Exp', 'Exporter', 'PORT', 'Notf No', 'Ledger Date', 'TOTAL CIF',
            'BAL CIF', 'HSN Juice', 'Total Juice Qty', 'BAL Juice Qty',
            'HSN Other', 'Total Other Qty', 'BAL Other Qty',
            '2% of CIF', '2% of CIF Utilized', '2% of CIF Balance',
            'HSN TARTARIC', 'Total TARTARIC Qty', 'BAL TARTARIC Qty',
            'HSN ESSENTIAL OIL', 'Total ESSENTIAL OIL Qty', 'BAL ESSENTIAL OIL Qty',
            '5% of CIF', '5% of CIF Utilized', '5% of CIF Balance',
            'HSN PP', 'Total PP Qty', 'BAL PP Qty',
            'HSN Aluminium Foil', 'Total Aluminium Foil Qty', 'BAL Aluminium Foil Qty',
            'HSN Paper', 'Total Paper Qty', 'BAL Paper Qty',
            'Is Individual', 'Is Conversion'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for data_dict in conf_list:
            writer.writerow(data_dict)


def split_list():
    abc = """1310049493
    1310049613
    ...
    0910051341"""
    return abc.split()
