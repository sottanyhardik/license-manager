from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from license.models import LicenseDetailsModel


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def add_arguments(self, parser):
        parser.add_argument('status')

    def handle(self, *args, **options):
        status = options['status']
        d = []
        bisc = []
        conc_list = []
        not_found = []
        steel_other = []
        found_other = []
        import csv
        biscuit_list = []
        import datetime
        today = datetime.datetime.now()
        date = today-datetime.timedelta(days=120)
        if status == 'expired':
            list_exclude = LicenseDetailsModel.objects.filter(license_expiry_date__lt=date)
        else:
            list_exclude = LicenseDetailsModel.objects.filter(license_expiry_date__gte=date)
        biscuit_list, bisc, conc_list, steel_other, found_other, not_found = fetch_data(list_exclude, biscuit_list, bisc, conc_list, steel_other, found_other, not_found)
        with open('biscuits_{}.csv'.format(status), 'w') as csvfile:
            fieldnames = ['DFIA', 'DFIA DT', 'DFIA EXP', 'Exporter', 'Notf No', 'TOTAL CIF', 'BAL CIF', 'SUGAR QTY',
                          'RBD QTY', 'HSN P', 'DF QTY', 'HSN D', 'FF QTY', 'HSN F', 'VAL 10%', 'VAL 10% Utilized',
                          'VAL 10% Balance', 'WPC QTY', 'HSN WPC', 'SWP QTY', 'HSN SWP', 'M&M O QTY', 'HSN M&M O',
                          'GLUTEN QTY', 'HSN G', 'Fruit Cocoa QTY', 'HSN Fr', 'Leavening Agent QTY', 'PP QTY',
                          'Paper & Paper Board', 'HSN PAP', 'Is Individual','Is Conversion']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for dict_data in biscuit_list:
                writer.writerow(dict_data)
        with open('assorted_{}.csv'.format(status), 'w') as csvfile:
            fieldnames = ['DFIA', 'DFIA DT', 'DFIA EXP', 'Notf No', 'Exporter', 'TOTAL CIF', 'BAL CIF', 'SUGAR QTY',
                          'HSN SU', 'FF QTY', 'HSN F', 'JUICE Qty', 'HSN Juice', 'TARTARIC Qty', 'HSN TARTARIC',
                          'ESSENTIAL OIL QTY', 'HSN E', 'VAL 5%', 'VAL 5% Utilized', 'VAL 5% Balance', 'EMULSIFIER QTY',
                          'HSN EM', 'VAL 3%', 'VAL 3% Utilized', 'VAL 3% Balance', 'Other Qty', 'Other', 'VAL 2%',
                          'VAL 2% Utilized', 'VAL 2% Balance', 'PP QTY', 'HSN PP', 'Paper & Paper Board', 'HSN PAP',
                          'Is Individual','Is Conversion']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for dict_data in conc_list:
                writer.writerow(dict_data)
        with open('not_found_{}.csv'.format(status), 'w') as csvfile:
            fieldnames = ['DFIA']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for dict_data in not_found:
                writer.writerow(dict_data)
        with open('found_other_{}.csv'.format(status), 'w') as csvfile:
            fieldnames = ['DFIA', 'DFIA DT', 'DFIA EXP', 'DFIA File No', 'Notf No', 'Exporter', 'BAL CIF']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for dict_data in found_other:
                writer.writerow(dict_data)
        with open('steel_{}.csv'.format(status), 'w') as csvfile:
            fieldnames = ['DFIA', 'DFIA DT', 'DFIA EXP', 'Notf No', 'Exporter', 'TOTAL CIF', 'BAL CIF', 'Bearing QTY',
                          'IC QTY', 'Valves QTY', 'Alloy Steel QTY', 'Relevant Hot Rolled/ Cold Rolled Steel QTY',
                          'Is Individual']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for dict_data in steel_other:
                writer.writerow(dict_data)
        self.stdout.write(self.style.SUCCESS('Report Generated for  "%s"' % status))


def fetch_data(list_exclude, biscuit_list,bisc, conc_list,steel_other,found_other, not_found):
    for dfia in list_exclude:
        if dfia.get_balance_cif() > 0:
            try:
                if dfia.get_norm_class == 'E5':
                    dict_data = {
                        'DFIA': "'" + dfia.license_number,
                        'DFIA DT': str(dfia.license_date),
                        'DFIA EXP': str(dfia.license_expiry_date),
                        'Exporter': dfia.exporter.name[:15],
                        'Notf No': dfia.notification_number,
                        'TOTAL CIF': float(dfia.opening_balance),
                        'BAL CIF': float(dfia.get_balance_cif()),
                        'SUGAR QTY': "",
                        'RBD QTY': "",
                        'DF QTY': "",
                        'FF QTY': "",
                        'WPC QTY': "",
                        'HSN WPC': "",
                        'SWP QTY': "",
                        'HSN SWP': "",
                        'M&M O QTY': "",
                        'HSN M&M O': "",
                        'VAL 10%': int(dfia.opening_balance * .1),
                        'VAL 10% Balance': dfia.get_per_cif(),
                        'Is Individual': dfia.is_individual
                    }
                    if dict_data['VAL 10% Balance'] < 0:
                        dict_data['VAL 10% Balance'] = 0
                    dict_data['VAL 10% Utilized'] = dict_data['VAL 10%'] - dict_data['VAL 10% Balance']
                    if dfia.export_license.all().first().old_quantity != 0.0:
                        dict_data['VAL 10% Utilized'] = 0
                        dict_data['VAL 10%'] - 0
                        dict_data['VAL 10% Balance'] = 0
                        dict_data['Is Conversion'] = True
                    bisc.append(dfia.license_number)
                    import_item = dfia.import_license.filter(item__head__name__icontains='wheat')
                    if import_item.exists():
                        dict_data['HSN G'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['GLUTEN QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='Palmolein')
                    if import_item.exists():
                        dict_data['HSN P'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['RBD QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='dietary fibre')
                    if import_item.exists():
                        dict_data['HSN D'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['DF QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='food flavour')
                    if import_item.exists():
                        dict_data['HSN F'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['FF QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='fruit')
                    if import_item.exists():
                        dict_data['HSN Fr'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['Fruit Cocoa QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(hs_code__hs_code__icontains='3502')
                    if import_item.exists():
                        dict_data['HSN WPC'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['WPC QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(hs_code__hs_code__icontains='04041020').exclude(
                        hs_code__hs_code__icontains='3502')
                    if import_item.exists():
                        dict_data['HSN SWP'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['SWP QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(
                        Q(item__head__name__icontains='Skimmed') | Q(item__head__name__icontains='milk')).exclude(
                        Q(hs_code__hs_code__icontains='3502') | Q(hs_code__hs_code__icontains='04041020'))
                    if import_item.exists():
                        total = 0
                        dict_data['HSN M&M O'] = "'" + import_item[0].hs_code.hs_code
                        dict_data['M&M O QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='sugar')
                    if import_item.exists():
                        total = 0
                        dict_data['SUGAR QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='Leavening Agent')
                    if import_item.exists():
                        total = 0
                        dict_data['Leavening Agent QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='pp')
                    if import_item.exists():
                        total = 0
                        dict_data['PP QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='paper & paper board')
                    if import_item.exists():
                        dict_data['HSN PAP'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['Paper & Paper Board'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    biscuit_list.append(dict_data)
                elif dfia.get_norm_class == 'E1':
                    dict_data = {
                        'DFIA': "'" + dfia.license_number,
                        'DFIA DT': str(dfia.license_date),
                        'DFIA EXP': str(dfia.license_expiry_date),
                        'Notf No': dfia.notification_number,
                        'Exporter': dfia.exporter.name[:15],
                        'TOTAL CIF': float(dfia.opening_balance),
                        'BAL CIF': float(dfia.get_balance_cif()),
                        'SUGAR QTY': "",
                        'FF QTY': "",
                        'VAL 2%': int(dfia.opening_balance * .02),
                        'VAL 2% Balance': dfia.get_per_cif(),
                        'VAL 5%': int(dfia.opening_balance * .05),
                        'VAL 5% Balance': dfia.get_per_essential_oil(),
                        'VAL 3%': int(dfia.opening_balance * .03),
                        'VAL 3% Balance': dfia.get_per_emulsifier(),
                        'Is Individual': dfia.is_individual
                    }
                    dict_data['VAL 2% Utilized'] = dict_data['VAL 2%'] - dict_data['VAL 2% Balance']
                    dict_data['VAL 5% Utilized'] = dict_data['VAL 5%'] - dict_data['VAL 5% Balance']
                    print(dict_data['VAL 3% Balance'])
                    dict_data['VAL 3% Utilized'] = dict_data['VAL 3%'] - dict_data['VAL 3% Balance']
                    if dfia.export_license.all().first().old_quantity != 0.0:
                        dict_data['VAL 2% Utilized'] = 0
                        dict_data['VAL 2%'] - 0
                        dict_data['VAL 2% Balance'] = 0
                        dict_data['VAL 5% Utilized'] = 0
                        dict_data['VAL 5%'] - 0
                        dict_data['VAL 5% Balance'] = 0
                        dict_data['VAL 3% Utilized'] = 0
                        dict_data['VAL 3%'] - 0
                        dict_data['VAL 3% Balance'] = 0
                        dict_data['Is Conversion'] = True
                    import_item = dfia.import_license.filter(item__head__name__icontains='food flavour')
                    if import_item.exists():
                        dict_data['HSN F'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['FF QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='juice')
                    if import_item.exists():
                        dict_data['HSN Juice'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['JUICE Qty'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='other')
                    if import_item.exists():
                        dict_data['Other'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['Other Qty'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='sugar')
                    if import_item.exists():
                        dict_data['HSN SU'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['SUGAR QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='citric acid')
                    if import_item.exists():
                        dict_data['HSN TARTARIC'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['TARTARIC Qty'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__head__name__icontains='essential oil')
                    if import_item.exists():
                        total = 0
                        dict_data['ESSENTIAL OIL QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                        dict_data['HSN E'] = "'" + import_item[0].hs_code.hs_code
                    import_item = dfia.import_license.filter(item__head__name__icontains='emulsifier')
                    if import_item.exists():
                        total = 0
                        dict_data['EMULSIFIER QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                        dict_data['HSN EM'] = "'" + import_item[0].hs_code.hs_code
                    import_item = dfia.import_license.filter(item__head__name__icontains='pp')
                    if import_item.exists():
                        total = 0
                        dict_data['PP QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                        dict_data['HSN PP'] = "'" + import_item[0].hs_code.hs_code
                    import_item = dfia.import_license.filter(item__head__name__icontains='paper & paper board')
                    if import_item.exists():
                        total = 0
                        dict_data['Paper & Paper Board'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                        dict_data['HSN PAP'] = "'" + import_item[0].hs_code.hs_code
                    conc_list.append(dict_data)
                elif dfia.get_norm_class == 'C969':
                    dict_data = {
                        'DFIA': "'" + dfia.license_number,
                        'DFIA DT': str(dfia.license_date),
                        'DFIA EXP': str(dfia.license_expiry_date),
                        'Notf No': dfia.notification_number,
                        'Exporter': dfia.exporter.name[:15],
                        'TOTAL CIF': float(dfia.opening_balance),
                        'BAL CIF': float(dfia.get_balance_cif()),
                        'Bearing QTY': "",
                        'IC QTY': "",
                        'Valves QTY': "",
                        'Alloy Steel QTY': "",
                        'Relevant Hot Rolled/ Cold Rolled Steel QTY': "",
                        'Is Individual': dfia.is_individual,
                    }
                    import_item = dfia.import_license.filter(item__name__icontains='Bearing')
                    if import_item.exists():
                        total = 0
                        dict_data['Bearing QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__name__icontains='Internal Combustion')
                    if import_item.exists():
                        total = 0
                        dict_data['IC QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__name__icontains='Valves')
                    if import_item.exists():
                        total = 0
                        dict_data['Valves QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__name__icontains='Relevant Alloy Steel')
                    if import_item.exists():
                        total = 0
                        dict_data['Alloy Steel QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    import_item = dfia.import_license.filter(item__name__icontains='Relevant Hot Rolled')
                    if import_item.exists():
                        total = 0
                        dict_data['Relevant Hot Rolled/ Cold Rolled Steel QTY'] = sum(
                            [total := total + import_item.balance_quantity for import_item in import_item])
                    steel_other.append(dict_data)
                else:
                    dict_data = {
                        'DFIA': "'" + dfia.license_number,
                        'DFIA DT': str(dfia.license_date),
                        'DFIA EXP': str(dfia.license_expiry_date),
                        'DFIA File No': str(dfia.file_number),
                        'Notf No': dfia.notification_number,
                        'Exporter': dfia.exporter.name[:15],
                        'BAL CIF': float(dfia.get_balance_cif()),
                    }
                    found_other.append(dict_data)
            except Exception as e:
                print(e)
                dict_data = {
                    'DFIA': "'" + str(dfia),
                }
                not_found.append(dict_data)
    return biscuit_list, bisc, conc_list, steel_other, found_other, not_found
