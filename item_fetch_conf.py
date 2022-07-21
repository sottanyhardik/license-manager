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
            if dfia:
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
                data_dict['BAL CIF'] = float(dfia.get_balance_cif())
                data_dict['2% of CIF'] = int(dfia.opening_balance * .02)
                data_dict['2% of CIF Balance'] = dfia.get_per_cif()
                data_dict['5% of CIF'] = int(dfia.opening_balance * .05)
                data_dict['5% of CIF Balance'] = dfia.get_per_essential_oil()
                data_dict['Is Individual'] = dfia.is_individual
                data_dict['Is Conversion'] = ""
                if dfia.export_license.all().first().old_quantity != 0.0 or dfia.notification_number == '098/2009':
                    data_dict['2% of CIF Utilized'] = 0
                    data_dict['2% of CIF Balance'] = 0
                    data_dict['5% of CIF Utilized'] = 0
                    data_dict['5% of CIF Balance'] = 0
                    data_dict['2% of CIF'] = 0
                    data_dict['5% of CIF'] = 0
                    if dfia.export_license.all().first().old_quantity != 0.0:
                        data_dict['Is Conversion'] = True
                else:
                    data_dict['2% of CIF Utilized'] = int(dfia.opening_balance * .02) - data_dict['2% of CIF Balance']
                    data_dict['5% of CIF Utilized'] = data_dict['5% of CIF'] - data_dict['5% of CIF Balance']
                import_item = dfia.import_license.filter(item__head__name__icontains='juice')
                if import_item.exists():
                    data_dict['HSN Juice'] = "'" + import_item[0].hs_code.hs_code
                    total = 0
                    data_dict['BAL JUICE Qty'] = fetch_total(import_item)
                    data_dict['OLD JUICE Qty'] = import_item.aggregate(Sum('old_quantity'))['old_quantity__sum']
                    data_dict['Total JUICE Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(item__head__name__icontains='other')
                if import_item.exists():
                    data_dict['Other'] = "'" + import_item[0].hs_code.hs_code
                    total = 0
                    data_dict['BAL Other Qty'] = fetch_total(import_item)
                    data_dict['OLD Other Qty'] = import_item.aggregate(Sum('old_quantity'))['old_quantity__sum']
                    data_dict['Total Other Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(item__head__name__icontains='citric acid')
                if import_item.exists():
                    data_dict['HSN TARTARIC'] = "'" + import_item[0].hs_code.hs_code
                    total = 0
                    data_dict['BAL TARTARIC Qty'] = fetch_total(import_item)
                    data_dict['OLD TARTARIC Qty'] = import_item.aggregate(Sum('old_quantity'))['old_quantity__sum']
                    data_dict['Total TARTARIC Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(item__head__name__icontains='essential oil')
                if import_item.exists():
                    total = 0
                    data_dict['BAL ESSENTIAL OIL QTY'] = fetch_total(import_item)
                    data_dict['HSN E'] = "'" + import_item[0].hs_code.hs_code
                    data_dict['OLD ESSENTIAL OIL Qty'] = import_item.aggregate(Sum('old_quantity'))['old_quantity__sum']
                    data_dict['Total ESSENTIAL OIL Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']

                import_item = dfia.import_license.filter(item__head__name__icontains='pp')
                if import_item.exists():
                    total = 0
                    data_dict['PP QTY'] = fetch_total(import_item)
                    data_dict['HSN PP'] = "'" + import_item[0].hs_code.hs_code
                import_item = dfia.import_license.filter(item__head__name__icontains='paper & paper board')
                if import_item.exists():
                    total = 0
                    data_dict['Paper & Paper Board'] = fetch_total(import_item)
                    data_dict['HSN PAP'] = "'" + import_item[0].hs_code.hs_code
                else:
                    data_dict['Paper & Paper Board'] = 0
                    data_dict['HSN PAP'] = ''
        except Exception as e:
            print(e)
        conf_list.append(data_dict)
    return conf_list


def generate_excel(conf_list):
    with open('conf.csv', 'w', newline='') as csvfile:
        fieldnames = ['DFIA No', 'DFIA Dt', 'DFIA Exp', 'Exporter', 'PORT', 'Notf No', 'Ledger Date', 'TOTAL CIF',
                      'BAL CIF', 'HSN Juice', 'Total JUICE Qty', 'OLD JUICE Qty', 'BAL JUICE Qty', 'Other',
                      'Total Other Qty', 'OLD Other Qty', 'BAL Other Qty',
                      '2% of CIF', '2% of CIF Utilized', '2% of CIF Balance', 'HSN TARTARIC','Total TARTARIC Qty','OLD TARTARIC Qty', 'BAL TARTARIC Qty',
                      'HSN E',
                      'Total ESSENTIAL OIL Qty','OLD ESSENTIAL OIL Qty','BAL ESSENTIAL OIL QTY', '5% of CIF', '5% of CIF Utilized', '5% of CIF Balance', 'HSN PP',
                      'PP QTY',
                      'HSN PAP', 'Paper & Paper Board', 'Is Individual', 'Is Conversion']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for data_dict in conf_list:
            writer.writerow(data_dict)


def split_list():
    abc = """1310049493
    1310049613
    1310049614
    1310049615
    1310049729
    1310049730
    1310049731
    5610000027
    5610000028
    0310597347
    0310597349
    0310630708
    0310630718
    0310630728
    0310633029
    0310636056
    0310636655
    0310636663
    0310636907
    0310637421
    0310641460
    0310641469
    0310644611
    0310646062
    0310647752
    0310647753
    0310647815
    0310647817
    0310650508
    0310650527
    0310661583
    0310662034
    0310662039
    0310662215
    0310662266
    0310662899
    0310664328
    0310664391
    0310664984
    0310664990
    0310664996
    0310666396
    0310666397
    0310666615
    0310668480
    0310668515
    0310670519
    0310672125
    0310680626
    0310680666
    0310681169
    0310681423
    0310681614
    0310682293
    0310683006
    0310688679
    0310688738
    0310689110
    0310695781
    0310701906
    0310702191
    0310704333
    0310705160
    0310708920
    0310709467
    0310710902
    0310710939
    0310717723
    0310719625
    0310720147
    0310720614
    0310725206
    0310727810
    0310729488
    0310732839
    0310734181
    0310734213
    0310736181
    0310736639
    0310736984
    0310737004
    0310737558
    0310737866
    0310738219
    0310738224
    0310738485
    0310738493
    0310739005
    0310739236
    0310740474
    0310740548
    0310741126
    0310741140
    0310741319
    0310741379
    0310741564
    0310742675
    0310757968
    0310766935
    0310776850
    0310776851
    0310776854
    0310782452
    0310791395
    0310793650
    0310817639
    0310824203
    0310824205
    0310825235
    0310825251
    0310825276
    0310825596
    0310826413
    0310827444
    0310828013
    0310828052
    0310828053
    0310828054
    0310828181
    0310828182
    0310828186
    0310829056
    0310829058
    0310829894
    0310829957
    0310829977
    0310829979
    0310829991
    0310830033
    0310830036
    0310830088
    0310830434
    0310830463
    0310830479
    0310831630
    0310831825
    0310831827
    0310831829
    0310831830
    0310831831
    0310831880
    0310832148
    0310832398
    0310832430
    0310832432
    0310832433
    0310832464
    0310832769
    0310833047
    0310833141
    0310833286
    0310833303
    0310833304
    0310833305
    0310833310
    0310833321
    0310833322
    0310833701
    0310833704
    0310833793
    0310833996
    0310834151
    0310834153
    0310834296
    0310834611
    0310834613
    0310834614
    0310834746
    0310834825
    0310834894
    0310834896
    0310834960
    0310834962
    0310834967
    0310834979
    0310834980
    0310835112
    0310835198
    0310835231
    0310835310
    0310835311
    0310835515
    0310835516
    0310835522
    0310835561
    0310835562
    0310835584
    0310837138
    0310837230
    0310837231
    0310837441
    0310837555
    0310837898
    0310837955
    0310837958
    0310837961
    0310838034
    0310838036
    0310838037
    0310838039
    0310838099
    0310838176
    0310838205
    0310838320
    0310838322
    0310838326
    0310838414
    0310838475
    0310838478
    0310838697
    0310838758
    0310838862
    0310838869
    0310838966
    0310839062
    0310839069
    0310839116
    0310839125
    0310839139
    0310839460
    0310839541
    0310839542
    0310839558
    0310839625
    0310839650
    0311001739
    0311002880
    0311004194
    0311004700
    0311004734
    0311004896
    0311004899
    0311004902
    0311004904
    0311004986
    0311005000
    0311005034
    0311005265
    0311005292
    0311005308
    0311005309
    0311005358
    0311005359
    0311005481
    0311005544
    0311006172
    0311006367
    0311006570
    0311006580
    0311006745
    0311006753
    0311006789
    0311006856
    0311006923
    0311007010
    0311007151
    0311007211
    0311008153
    0311008454
    0311008507
    0311008560
    0311008660
    0311008763
    0311009149
    0311009150
    0311009211
    0311009709
    0311009882
    0311009883
    0311009992
    0311010038
    0311010062
    0311011361
    0810145959
    0910051255
    0910051341"""
    return abc.split()
