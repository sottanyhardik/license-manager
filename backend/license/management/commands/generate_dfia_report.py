import csv
from django.core.management.base import BaseCommand
from django.db.models import Sum, Q
from license.models import LicenseDetailsModel
from core.management.commands.report_fetch import fetch_total, fetch_debited


def add(dfia, label,record):
    qs = dfia.import_license.filter(item__name__icontains=label)
    if qs.exists():
        i = qs.first()
        record[f"HSN {label}"] = "'" + i.hs_code.hs_code
        record[f"PD {label}"] = "'" + i.description
        record[f"Total {label} Qty"] = qs.aggregate(Sum("quantity"))["quantity__sum"]
        record[f"BAL {label} QTY"] = fetch_total(qs)
        record[f"Utilized {label} Qty"] = fetch_debited(qs)
    else:
        record[f"HSN {label}"] = "'"
        record[f"PD {label}"] = "'"
        record[f"Total {label} Qty"] = "'"
        record[f"BAL {label} QTY"] = "'"
        record[f"Utilized {label} Qty"] = "'"
    return record


class Command(BaseCommand):
    help = "Generate both DFIA 10% and Confectionery (2%/5%) reports in one go."

    def handle(self, *args, **kwargs):
        license_list = self.get_license_list()

        # Run both reports
        dfia_data = self.fetch_biscuit_report(license_list)
        self.write_to_csv(dfia_data, "dfia_biscuit.csv")
        dfia_data = self.fetch_confectionery_report(license_list)
        self.write_to_csv(dfia_data, "dfia_confectionery.csv")
        self.stdout.write(self.style.SUCCESS("✅ Both reports generated."))

    def get_license_list(self):
        abc = """1310049708
    0310838098
    1310049730
    1310049493
    1310049731
    1310049729
    3010105354
    0310831148
    0310831149
    0310831147
    0310839564
    0310837902
    0310832494
    0310838342
    0310831880
    0310834896
    0310834967
    0310831843
    0310837998
    0310831831
    0310833305
    0310833286
    0310835514
    0310835559
    0310839189
    0310832432
    0310832433
    0310832430
    0310832398
    0310833793
    0310833141
    0310833589
    0310833591"""
        return abc.split()

    def fetch_biscuit_report(self, license_numbers):
        data_list = []
        template = {
            'DFIA No': '', 'DFIA Dt': '', 'DFIA Exp': '', 'Exporter': '', 'PORT': '', 'Ledger Date': '',
            'Notf No': '', 'TOTAL CIF': 0, 'BAL CIF': 0, 'Is Individual': False, 'Is Conversion': '',
            '10% of CIF Utilized': 0,

            'HSN WHEAT GLUTEN': '', 'PD WHEAT GLUTEN': '', 'Total WHEAT GLUTEN Qty': 0, 'BAL WHEAT GLUTEN QTY': 0, 'Utilized WHEAT GLUTEN Qty': 0,
            'HSN RBD PALMOLEIN OIL': '', 'PD RBD PALMOLEIN OIL': '', 'Total RBD PALMOLEIN OIL Qty': 0, 'BAL RBD PALMOLEIN OIL QTY': 0, 'Utilized RBD PALMOLEIN OIL Qty': 0,
            'HSN EDIBLE VEGETABLE OIL': '', 'PD EDIBLE VEGETABLE OIL': '', 'Total EDIBLE VEGETABLE OIL Qty': 0,
            'BAL EDIBLE VEGETABLE OIL QTY': 0, 'Utilized EDIBLE VEGETABLE OIL Qty': 0,
            'HSN PALM KERNEL OIL': '', 'PD PALM KERNEL OIL': '', 'Total PALM KERNEL OIL Qty': 0,
            'BAL PALM KERNEL OIL QTY': 0, 'Utilized PALM KERNEL OIL Qty': 0,

            '10% of CIF': 0, '10% of CIF Balance': 0,

            'HSN JUICE': '', 'PD JUICE': '', 'Total JUICE Qty': 0, 'BAL JUICE QTY': 0, 'Utilized JUICE Qty': 0,
            'HSN FOOD FLAVOUR BISCUITS': '', 'PD FOOD FLAVOUR BISCUITS': '', 'Total FOOD FLAVOUR BISCUITS Qty': 0, 'BAL FOOD FLAVOUR BISCUITS QTY': 0,
            'Utilized FOOD FLAVOUR BISCUITS Qty': 0,
            'HSN DIETARY FIBRE': '', 'PD DIETARY FIBRE': '', 'Total DIETARY FIBRE Qty': 0, 'BAL DIETARY FIBRE QTY': 0,
            'Utilized DIETARY FIBRE Qty': 0,
            'HSN FRUIT/COCOA': '', 'PD FRUIT/COCOA': '', 'Total FRUIT/COCOA Qty': 0, 'BAL FRUIT/COCOA QTY': 0,
            'Utilized FRUIT/COCOA Qty': 0,
            'HSN STARCH 1108': '', 'PD STARCH 1108': '', 'Total STARCH 1108 Qty': 0, 'BAL STARCH 1108 QTY': 0,
            'Utilized STARCH 1108 Qty': 0,
            'HSN STARCH 3505': '', 'PD STARCH 3505': '', 'Total STARCH 3505 Qty': 0, 'BAL STARCH 3505 QTY': 0,
            'Utilized STARCH 3505 Qty': 0,
            'HSN CHEESE': '', 'PD CHEESE': '', 'Total CHEESE Qty': 0, 'BAL CHEESE QTY': 0, 'Utilized CHEESE Qty': 0,
            'HSN WPC': '', 'PD WPC': '', 'Total WPC Qty': 0, 'BAL WPC QTY': 0, 'Utilized WPC Qty': 0,
            'HSN SWP': '', 'PD SWP': '', 'Total SWP Qty': 0, 'BAL SWP QTY': 0, 'Utilized SWP Qty': 0,
            'HSN PP': '', 'PD PP': '', 'Total PP Qty': 0, 'BAL PP QTY': 0, 'Utilized PP Qty': 0,
            'HSN HDPE': '', 'PD HDPE': '', 'Total HDPE Qty': 0, 'BAL HDPE QTY': 0, 'Utilized HDPE Qty': 0,
            'HSN PAPER & PAPER': '', 'PD PAPER & PAPER': '', 'Total PAPER & PAPER Qty': 0, 'BAL PAPER & PAPER QTY': 0,
            'Utilized PAPER & PAPER Qty': 0,
            'HSN PAPER BOARD': '', 'PD PAPER BOARD': '', 'Total PAPER BOARD Qty': 0, 'BAL PAPER BOARD QTY': 0,
            'Utilized PAPER BOARD Qty': 0,
            'HSN ALUMINIUM FOIL': '', 'PD ALUMINIUM FOIL': '', 'Total ALUMINIUM FOIL Qty': 0,
            'BAL ALUMINIUM FOIL QTY': 0, 'Utilized ALUMINIUM FOIL Qty': 0
        }

        for license_no in license_numbers:
            record = template.copy()
            record["DFIA No"] = "'" + license_no
            try:
                dfia = LicenseDetailsModel.objects.get(license_number=license_no)
                if dfia.get_norm_class == 'E5':
                    record.update({
                        "DFIA Dt": dfia.license_date.strftime('%d/%m/%Y') if dfia.license_date else "",
                        "DFIA Exp": dfia.license_expiry_date.strftime('%d/%m/%Y') if dfia.license_expiry_date else "",
                        "Exporter": str(dfia.exporter) if dfia.exporter else "",
                        "PORT": str(dfia.port) if dfia.port else "",
                        "Ledger Date": dfia.ledger_date.strftime('%d/%m/%Y') if dfia.ledger_date else "",
                        "Notf No": dfia.notification_number,
                        "TOTAL CIF": float(dfia.opening_balance),
                        "BAL CIF": float(dfia.get_balance_cif),
                        "10% of CIF": int(dfia.opening_balance * 0.10),
                        "10% of CIF Balance": dfia.get_per_cif.get('tenRestriction') if dfia.get_per_cif else 0,
                        "Is Individual": dfia.is_individual,
                        "Is Conversion": ""
                    })

                    if dfia.export_license.exists() and dfia.export_license.first().old_quantity != 0.0 or dfia.notification_number == "098/2009":
                        record.update({
                            "10% of CIF Utilized": 0,
                            "10% of CIF Balance": 0,
                            "10% of CIF": 0,
                            "Is Conversion": True
                        })
                    else:
                        record["10% of CIF Utilized"] = record["10% of CIF"] - record["10% of CIF Balance"]
                    record = add(dfia, 'WHEAT GLUTEN',record)
                    record = add(dfia, 'RBD PALMOLEIN OIL', record)
                    record = add(dfia, 'EDIBLE VEGETABLE OIL', record)
                    record = add(dfia, 'PALM KERNEL OIL', record)
                    record = add(dfia, 'FOOD FLAVOUR BISCUITS', record)
                    record = add(dfia, 'JUICE', record)
                    record = add(dfia, 'DIETARY FIBRE', record)
                    record = add(dfia, 'FRUIT/COCOA', record)
                    record = add(dfia, 'STARCH 1108', record)
                    record = add(dfia, 'STARCH 3505', record)
                    record = add(dfia, 'CHEESE', record)
                    record = add(dfia, 'WPC', record)
                    record = add(dfia, 'SWP', record)
                    record = add(dfia, 'PP', record)
                    record = add(dfia, 'HDPE', record)
                    record = add(dfia, 'PAPER & PAPER', record)
                    record = add(dfia, 'PAPER BOARD', record)
                    record = add(dfia, 'ALUMINIUM FOIL', record)
            except Exception as e:
                print(f"[ERROR] {license_no}: {e}")
            data_list.append(record)
        return data_list

    def fetch_confectionery_report(self, license_numbers):
        data_list = []
        template_dict = {
            'DFIA No': '', 'DFIA Dt': '', 'DFIA Exp': '', 'Exporter': '', 'PORT': '', 'Ledger Date': '',
            'Notf No': '', 'TOTAL CIF': 0, 'BAL CIF': 0,'Is Individual': False, 'Is Conversion': '',

            'HSN Sugar': '', 'PD Sugar': '', 'Total Sugar Qty': 0, 'BAL Sugar QTY': 0, 'Utilized Sugar Qty': 0,
            'HSN FRUIT JUICE': '', 'PD FRUIT JUICE': '', 'Total FRUIT JUICE Qty': 0, 'BAL FRUIT JUICE QTY': 0,
            'Utilized FRUIT JUICE Qty': 0,
            '5% of CIF': 0, '5% of CIF Utilized': 0, '5% of CIF Balance': 0,
            'HSN FOOD FLAVOUR CONFECTIONERY': '', 'PD FOOD FLAVOUR CONFECTIONERY': '',
            'Total FOOD FLAVOUR CONFECTIONERY Qty': 0, 'BAL FOOD FLAVOUR CONFECTIONERY QTY': 0,
            'Utilized FOOD FLAVOUR CONFECTIONERY Qty': 0,
            'HSN ESSENTIAL OIL': '', 'PD ESSENTIAL OIL': '', 'Total ESSENTIAL OIL Qty': 0, 'BAL ESSENTIAL OIL QTY': 0,
            'Utilized ESSENTIAL OIL Qty': 0,
            'HSN EMULSIFIER': '', 'PD EMULSIFIER': '', 'Total EMULSIFIER Qty': 0, 'BAL EMULSIFIER QTY': 0,
            'Utilized EMULSIFIER Qty': 0,
            '2% of CIF': 0, '2% of CIF Utilized': 0, '2% of CIF Balance': 0,
            'HSN OTHER CONFECTIONERY INGREDIENTS': '', 'PD OTHER CONFECTIONERY INGREDIENTS': '',
            'Total OTHER CONFECTIONERY INGREDIENTS Qty': 0, 'BAL OTHER CONFECTIONERY INGREDIENTS QTY': 0,
            'Utilized OTHER CONFECTIONERY INGREDIENTS Qty': 0,
            'HSN PP': '', 'PD PP': '', 'Total PP Qty': 0, 'BAL PP QTY': 0, 'Utilized PP Qty': 0,
            'HSN HDPE': '', 'PD HDPE': '', 'Total HDPE Qty': 0, 'BAL HDPE QTY': 0, 'Utilized HDPE Qty': 0,
            'HSN PAPER & PAPER': '', 'PD PAPER & PAPER': '', 'Total PAPER & PAPER Qty': 0, 'BAL PAPER & PAPER QTY': 0,
            'Utilized PAPER & PAPER Qty': 0,
            'HSN PAPER BOARD': '', 'PD PAPER BOARD': '', 'Total PAPER BOARD Qty': 0, 'BAL PAPER BOARD QTY': 0,
            'Utilized PAPER BOARD Qty': 0,
            'HSN ALUMINIUM FOIL': '', 'PD ALUMINIUM FOIL': '', 'Total ALUMINIUM FOIL Qty': 0,
            'BAL ALUMINIUM FOIL QTY': 0, 'Utilized ALUMINIUM FOIL Qty': 0
        }

        for a in license_numbers:
            record = template_dict.copy()
            record['DFIA No'] = "'" + a
            try:
                dfia = LicenseDetailsModel.objects.get(license_number=a)
                if dfia.get_norm_class == 'E1':
                    if dfia.license_date:
                        record['DFIA Dt'] = dfia.license_date.strftime('%d/%m/%Y')
                    if dfia.license_expiry_date:
                        record['DFIA Exp'] = dfia.license_expiry_date.strftime('%d/%m/%Y')
                    if dfia.exporter:
                        record['Exporter'] = str(dfia.exporter)
                    if dfia.port:
                        record['PORT'] = str(dfia.port)
                    if dfia.ledger_date:
                        record['Ledger Date'] = dfia.ledger_date.strftime('%d/%m/%Y')

                    record['Notf No'] = dfia.notification_number
                    record['TOTAL CIF'] = float(dfia.opening_balance)
                    record['BAL CIF'] = float(dfia.get_balance_cif)

                    two = int(dfia.opening_balance * 0.02)
                    five = int(dfia.opening_balance * 0.05)

                    record['2% of CIF'] = two
                    record['2% of CIF Balance'] = dfia.get_per_cif.get('twoRestriction')
                    record['5% of CIF'] = five
                    record['5% of CIF Balance'] = dfia.get_per_cif.get('fiveRestriction')
                    record['Is Individual'] = dfia.is_individual
                    record['Is Conversion'] = ""

                    if dfia.export_license.all().first().old_quantity != 0.0 or dfia.notification_number == '098/2009':
                        record.update({
                            '2% of CIF Utilized': 0,
                            '2% of CIF Balance': 0,
                            '5% of CIF Utilized': 0,
                            '5% of CIF Balance': 0,
                            '2% of CIF': 0,
                            '5% of CIF': 0
                        })
                        if dfia.export_license.all().first().old_quantity != 0.0:
                            record['Is Conversion'] = True
                    else:
                        record['2% of CIF Utilized'] = two - record['2% of CIF Balance']
                        record['5% of CIF Utilized'] = five - record['5% of CIF Balance']

                    record = add(dfia, 'Sugar', record)
                    record = add(dfia, 'FRUIT JUICE', record)
                    record = add(dfia, 'FOOD FLAVOUR CONFECTIONERY', record)
                    record = add(dfia, 'ESSENTIAL OIL', record)
                    record = add(dfia, 'EMULSIFIER', record)
                    record = add(dfia, 'OTHER CONFECTIONERY INGREDIENTS', record)
                    record = add(dfia, 'PP', record)
                    record = add(dfia, 'HDPE', record)
                    record = add(dfia, 'PAPER & PAPER', record)
                    record = add(dfia, 'PAPER BOARD', record)
                    record = add(dfia, 'ALUMINIUM FOIL', record)
            except Exception as e:
                print(f"[ERROR] {a}: {e}")
            data_list.append(record)
        return data_list

    def write_to_csv(self, data_list, file_path):
        if not data_list:
            print(f"⚠️ No data to write for {file_path}")
            return
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=list(data_list[0].keys()))
            writer.writeheader()
            writer.writerows(data_list)
        print(f"✅ File saved: {file_path}")
