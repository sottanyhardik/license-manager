from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from license.models import LicenseDetailsModel


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def add_arguments(self, parser):
        parser.add_argument('status')

    def handle(self, *args, **options):
        status = options['status']
        d = ['0310837893', '0310835522', '0310825235', '0310835516', '0310833996', '0310833846', '3011000356', '0310829977', '0310833304', '0310836033', '0310837232', '0310835296', '0311005481', '0311006856', '0310839558', '0310839625', '0310837138', '0310825251', '0311008763', '0310817639', '0310825276', '0311004927', '0311004570', '0310838758', '1310049729', '0311008874', '0310839650', '1310049731', '0310838205', '1310049708', '0310838475', '0311005034', '0310732839', '0310829056', '0310839125', '0310838869', '0310832769', '0310837441', '0310833591', '0311008621', '0810145959', '0310833701', '0310839541', '0310825596', '0310834614', '0310834613', '0310834960', '0310826316', '0310834979', '0310839062', '0310838414', '0310717723', '0310835311', '0310834962', '0310835515', '0310839542', '0310838034', '0310827444', '0310823762', '0311004902', '0310838697', '0310839139', '0310839116', '0310838036', '1310049730', '0310838320', '0310838326', '0310837230', '0310839069', '0310838966', '1310049615', '0310824203', '0310838037', '0310835198', '0310837960', '1310049614', '0310838039', '0310831827', '0310830479', '0310834980', '0311001739', '0310828188', '0310835231', '0310834825', '0310835562', '0310835310', '0310831149', '0310838322', '0310689110', '0310834976', '0310828054', '0310829058', '0311002408', '0310828182', '0310838176', '0310838478', '0310831148', '0311004535', '1310049493', '0310828013', '0310828053', '0310835340', '0310834611', '0310830463', '0310831829', '0310827783', '0310834966', '0310729488', '0310831147', '0310828052', '0310834974', '0310837231', '0310828186', '0310832148', '0310831830', '0310837958', '0310833704', '0311004700', '0310827015', '0310827361', '0310837961', '0310838967', '0310830088', '0311006923', '0310834907', '0310837898', '0310829957', '0310829979', '0310831825', '0310837902', '0310839460', '0310830434', '0310831843', '0310829894', '0310833589', '0310828181', '0310829991', '0310837994', '0310838099', '0311004986', '0310721806', '0311002880', '0310837955', '0310729706', '0310831828', '0311005544', '0310837555', '0310838862', '0311004194', '0310681621', '0310763644', '0310732679', '1310049613', '0310838914', '0310834927', '0310838902', '0310838098', '0310838340', '0310838101', '0311009007', '0310839157', '0310838864', '0311006527', '0310838970', '0310824205', '0310826413', '0310834296', '0310821169', '0310831630', '0310837568']
        bisc = []
        conc_list = []
        not_found = []
        steel_other = []
        found_other = []
        import csv
        namkeen_other = []
        biscuit_list = []
        import datetime
        today = datetime.datetime.now()
        date = datetime.datetime.strptime('1 1 2010', '%d %m %Y')
        if d:
            if status == 'expired':
                list_exclude = LicenseDetailsModel.objects.filter(license_expiry_date__lt=today)
            else:
                list_exclude = LicenseDetailsModel.objects.filter(license_expiry_date__gte=date)
        else:
            if status == 'expired':
                list_exclude = LicenseDetailsModel.objects.filter(license_expiry_date__lt=today)
            else:
                list_exclude = LicenseDetailsModel.objects.filter(license_expiry_date__gte=date)
        biscuit_list, bisc, conc_list, steel_other, namkeen_other, found_other, not_found = fetch_data(list_exclude,
                                                                                                       biscuit_list,
                                                                                                       bisc, conc_list,
                                                                                                       steel_other,
                                                                                                       namkeen_other,
                                                                                                       found_other,
                                                                                                       not_found)
        with open('biscuits_{}.csv'.format(status), 'w') as csvfile:
            fieldnames = ['DFIA', 'DFIA DT', 'DFIA EXP', 'Exporter', 'Notf No', 'TOTAL CIF', 'BAL CIF', 'SUGAR QTY',
                          'RBD QTY', 'HSN P', 'DF QTY', 'HSN D', 'FF QTY', 'HSN F', 'VAL 10%', 'VAL 10% Utilized',
                          'VAL 10% Balance', 'WPC QTY', 'HSN WPC', 'SWP QTY', 'HSN SWP', 'M&M O QTY', 'HSN M&M O',
                          'GLUTEN QTY', 'HSN G', 'Fruit Cocoa QTY', 'HSN Fr', 'Leavening Agent QTY','Starch QTY', 'PP QTY',
                          'Paper & Paper Board', 'HSN PAP', 'Is Individual', 'Is Conversion']
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
                          'Is Individual', 'Is Conversion']
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
        with open('namkeen_{}.csv'.format(status), 'w') as csvfile:
            fieldnames = ['DFIA', 'DFIA DT', 'DFIA EXP', 'Notf No', 'Exporter', 'TOTAL CIF', 'BAL CIF', 'Chickpeas QTY',
                          'Editable QTY', 'Relevant Additives QTY', 'Relevant Flavour QTY', 'Packing Material QTY',
                          'Is Individual']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for dict_data in namkeen_other:
                writer.writerow(dict_data)
        with open('found_other_{}.csv'.format(status), 'w') as csvfile:
            fieldnames = ['DFIA', 'DFIA DT', 'DFIA EXP', 'DFIA File No', 'Notf No', 'Exporter', 'BAL CIF']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for dict_data in found_other:
                writer.writerow(dict_data)
        with open('steel_{}.csv'.format(status), 'w') as csvfile:
            fieldnames = ['DFIA', 'DFIA DT', 'DFIA EXP', 'Notf No', 'Exporter', 'TOTAL CIF', 'BAL CIF', 'Battery QTY',
                          'Bearing QTY',
                          'IC QTY', 'Valves QTY', 'Alloy Steel QTY', 'Relevant Hot Rolled/ Cold Rolled Steel QTY',
                          'Is Individual']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for dict_data in steel_other:
                writer.writerow(dict_data)
        self.stdout.write(self.style.SUCCESS('Report Generated for  "%s"' % status))


def fetch_total(import_item):
    total = 0
    for iitem in import_item:
        total = total + iitem.balance_quantity
    return total

def fetch_debited(import_item):
    total = 0
    for iitem in import_item:
        total = total + iitem.debited_quantity
    return total

def fetch_data(list_exclude, biscuit_list, bisc, conc_list, steel_other, namkeen_other, found_other, not_found):
    for dfia in list_exclude:
        if dfia.get_balance_cif() >= 0:
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
                        dict_data['GLUTEN QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='Palmolein')
                    if import_item.exists():
                        dict_data['HSN P'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['RBD QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='dietary fibre')
                    if import_item.exists():
                        dict_data['HSN D'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['DF QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='food flavour')
                    if import_item.exists():
                        dict_data['HSN F'] = "'" + import_item[0].hs_code.hs_code
                        dict_data['FF QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='fruit')
                    if import_item.exists():
                        dict_data['HSN Fr'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['Fruit Cocoa QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(hs_code__hs_code__icontains='3502')
                    if import_item.exists():
                        dict_data['HSN WPC'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['WPC QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(hs_code__hs_code__icontains='04041020').exclude(
                        hs_code__hs_code__icontains='3502')
                    if import_item.exists():
                        dict_data['HSN SWP'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['SWP QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(
                        Q(item__head__name__icontains='Skimmed') | Q(item__head__name__icontains='milk')).exclude(
                        Q(hs_code__hs_code__icontains='3502') | Q(hs_code__hs_code__icontains='04041020'))
                    if import_item.exists():
                        total = 0
                        dict_data['HSN M&M O'] = "'" + import_item[0].hs_code.hs_code
                        dict_data['M&M O QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='sugar')
                    if import_item.exists():
                        total = 0
                        dict_data['SUGAR QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='Leavening Agent')
                    if import_item.exists():
                        total = 0
                        dict_data['Leavening Agent QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='starch')
                    if import_item.exists():
                        total = 0
                        dict_data['Starch QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='pp')
                    if import_item.exists():
                        total = 0
                        dict_data['PP QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='paper & paper board')
                    if import_item.exists():
                        dict_data['HSN PAP'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['Paper & Paper Board'] = fetch_total(import_item)
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
                        dict_data['FF QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='juice')
                    if import_item.exists():
                        dict_data['HSN Juice'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['JUICE Qty'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='other')
                    if import_item.exists():
                        dict_data['Other'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['Other Qty'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='sugar')
                    if import_item.exists():
                        dict_data['HSN SU'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['SUGAR QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='citric acid')
                    if import_item.exists():
                        dict_data['HSN TARTARIC'] = "'" + import_item[0].hs_code.hs_code
                        total = 0
                        dict_data['TARTARIC Qty'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__head__name__icontains='essential oil')
                    if import_item.exists():
                        total = 0
                        dict_data['ESSENTIAL OIL QTY'] = fetch_total(import_item)
                        dict_data['HSN E'] = "'" + import_item[0].hs_code.hs_code
                    import_item = dfia.import_license.filter(item__head__name__icontains='emulsifier')
                    if import_item.exists():
                        total = 0
                        dict_data['EMULSIFIER QTY'] = fetch_total(import_item)
                        dict_data['HSN EM'] = "'" + import_item[0].hs_code.hs_code
                    import_item = dfia.import_license.filter(item__head__name__icontains='pp')
                    if import_item.exists():
                        total = 0
                        dict_data['PP QTY'] = fetch_total(import_item)
                        dict_data['HSN PP'] = "'" + import_item[0].hs_code.hs_code
                    import_item = dfia.import_license.filter(item__head__name__icontains='paper & paper board')
                    if import_item.exists():
                        total = 0
                        dict_data['Paper & Paper Board'] = fetch_total(import_item)
                        dict_data['HSN PAP'] = "'" + import_item[0].hs_code.hs_code
                    conc_list.append(dict_data)
                elif dfia.get_norm_class == 'E132':
                    dict_data = {
                        'DFIA': "'" + dfia.license_number,
                        'DFIA DT': str(dfia.license_date),
                        'DFIA EXP': str(dfia.license_expiry_date),
                        'Notf No': dfia.notification_number,
                        'Exporter': dfia.exporter.name[:15],
                        'TOTAL CIF': float(dfia.opening_balance),
                        'BAL CIF': float(dfia.get_balance_cif()),
                        'Chickpeas QTY': "",
                        'Editable QTY': "",
                        'Relevant Additives QTY': "",
                        'Relevant Flavour QTY': "",
                        'Packing Material QTY': "",
                        'Is Individual': dfia.is_individual,
                    }
                    import_item = dfia.import_license.filter(item__name__icontains='Chickpeas')
                    if import_item.exists():
                        total = 0
                        dict_data['Chickpeas QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__name__icontains='Editable')
                    if import_item.exists():
                        total = 0
                        dict_data['Editable QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__name__icontains='Relevant Food Additives')
                    if import_item.exists():
                        total = 0
                        dict_data['Relevant Additives QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__name__icontains='Relevant Food Flavour')
                    if import_item.exists():
                        total = 0
                        dict_data['Relevant Flavour QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__name__icontains='Packing Material')
                    if import_item.exists():
                        total = 0
                        dict_data['Packing Material QTY'] = fetch_total(import_item)
                    namkeen_other.append(dict_data)
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
                        'Battery QTY': "",
                        'IC QTY': "",
                        'Valves QTY': "",
                        'Alloy Steel QTY': "",
                        'Relevant Hot Rolled/ Cold Rolled Steel QTY': "",
                        'Is Individual': dfia.is_individual,
                    }
                    import_item = dfia.import_license.filter(item__name__icontains='Battery')
                    if import_item.exists():
                        total = 0
                        dict_data['Battery QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__name__icontains='Bearing')
                    if import_item.exists():
                        total = 0
                        dict_data['Bearing QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__name__icontains='Internal Combustion')
                    if import_item.exists():
                        total = 0
                        dict_data['IC QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__name__icontains='Valves')
                    if import_item.exists():
                        total = 0
                        dict_data['Valves QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__name__icontains='Relevant Alloy Steel')
                    if import_item.exists():
                        total = 0
                        dict_data['Alloy Steel QTY'] = fetch_total(import_item)
                    import_item = dfia.import_license.filter(item__name__icontains='Relevant Hot Rolled')
                    if import_item.exists():
                        total = 0
                        dict_data['Relevant Hot Rolled/ Cold Rolled Steel QTY'] = fetch_total(import_item)
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
    return biscuit_list, bisc, conc_list, steel_other, namkeen_other, found_other, not_found
