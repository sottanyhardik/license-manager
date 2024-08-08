import csv
from django.db.models import Sum
from core.management.commands.report_fetch import fetch_total, fetch_debited
from license.models import LicenseDetailsModel
from django.db.models import Q


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
                data_dict['BAL CIF'] = float(dfia.get_balance_cif)
                data_dict['10% of CIF'] = int(dfia.opening_balance * .1)
                data_dict['10% of CIF Balance'] = dfia.get_per_cif()
                data_dict['Is Individual'] = dfia.is_individual
                if dfia.export_license.all().first().old_quantity != 0.0 or dfia.notification_number == '098/2009':
                    data_dict['10% of CIF Utilized'] = 0
                    data_dict['10% of CIF Balance'] = 0
                    data_dict['10% of CIF'] = 0
                    if dfia.export_license.all().first().old_quantity != 0.0:
                        data_dict['Is Conversion'] = True
                else:
                    data_dict['10% of CIF Utilized'] = int(dfia.opening_balance * .1) - data_dict['10% of CIF Balance']
                import_item = dfia.import_license.filter(item__head__name__icontains='wheat')
                if import_item.exists():
                    data_dict['HSN G'] = "'" + import_item[0].hs_code.hs_code
                    total = 0
                    data_dict['BAL GLUTEN QTY'] = fetch_total(import_item)
                    data_dict['OLD GLUTEN Qty'] = import_item.aggregate(Sum('old_quantity'))['old_quantity__sum']
                    data_dict['Total GLUTEN Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(item__head__name__icontains='Palmolein')
                if import_item.exists():
                    data_dict['HSN P'] = "'" + import_item[0].hs_code.hs_code
                    total = 0
                    data_dict['BAL RBD QTY'] = fetch_total(import_item)
                    data_dict['Total RBD Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(item__head__name__icontains='dietary fibre')
                if import_item.exists():
                    data_dict['HSN DF'] = "'" + import_item[0].hs_code.hs_code
                    total = 0
                    data_dict['BAL DF QTY'] = fetch_total(import_item)
                    data_dict['Utilized DF Qty'] = fetch_debited(import_item)
                    data_dict['OLD DF Qty'] = import_item.aggregate(Sum('old_quantity'))['old_quantity__sum']
                    data_dict['Total DF Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(item__head__name__icontains='food flavour')
                if import_item.exists():
                    data_dict['HSN FF'] = "'" + import_item[0].hs_code.hs_code
                    data_dict['BAL FF QTY'] = fetch_total(import_item)
                    data_dict['Utilized FF Qty'] = fetch_debited(import_item)
                    data_dict['OLD FF Qty'] = import_item.aggregate(Sum('old_quantity'))['old_quantity__sum']
                    data_dict['Total FF Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(item__head__name__icontains='fruit')
                if import_item.exists():
                    data_dict['HSN Fr'] = "'" + import_item[0].hs_code.hs_code
                    data_dict['BAL FC QTY'] = fetch_total(import_item)
                    data_dict['Utilized FC Qty'] = fetch_debited(import_item)
                    data_dict['OLD FC Qty'] = import_item.aggregate(Sum('old_quantity'))['old_quantity__sum']
                    data_dict['Total FC Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(hs_code__hs_code__icontains='3502')
                if import_item.exists():
                    data_dict['HSN WPC'] = "'" + import_item[0].hs_code.hs_code
                    data_dict['BAL WPC QTY'] = fetch_total(import_item)
                    data_dict['Total WPC Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(hs_code__hs_code__icontains='04041020').exclude(
                    hs_code__hs_code__icontains='3502')
                if import_item.exists():
                    data_dict['HSN SWP'] = "'" + import_item[0].hs_code.hs_code
                    data_dict['BAL SWP QTY'] = fetch_total(import_item)
                    data_dict['Total SWP Qty'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(
                    Q(item__head__name__icontains='Skimmed') | Q(item__head__name__icontains='milk')).exclude(
                    Q(hs_code__hs_code__icontains='3502') | Q(hs_code__hs_code__icontains='04041020'))
                if import_item.exists():
                    total = 0
                    data_dict['BAL M&M Oth QTY'] = fetch_total(import_item)
                    data_dict['Total M&M Oth QTY'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(description__icontains='starch')
                if import_item.exists():
                    total = 0
                    data_dict['BAL Sugar QTY'] = fetch_total(import_item)
                    data_dict['Total Sugar QTY'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(item__head__name__icontains='Leavening Agent')
                if import_item.exists():
                    data_dict['BAL Leavening Agent QTY'] = fetch_total(import_item)
                    data_dict['Total Leavening Agent QTY'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(item__head__name__icontains='pp')
                if import_item.exists():
                    data_dict['HSN PP'] = "'" + import_item[0].hs_code.hs_code
                    data_dict['BAL PP QTY'] = fetch_total(import_item)
                    data_dict['Total PP QTY'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
                import_item = dfia.import_license.filter(item__head__name__icontains='paper & paper board')
                if import_item.exists():
                    data_dict['HSN PAP'] = "'" + import_item[0].hs_code.hs_code
                    data_dict['BAL PAP QTY'] = fetch_total(import_item)
                    data_dict['Total PAP QTY'] = import_item.aggregate(Sum('quantity'))['quantity__sum']
        except Exception as e:
            print(e)
            print(a)
        conf_list.append(data_dict)
    return conf_list


def generate_excel(data_list):
    with open('bisc.csv', 'w', newline='') as csvfile:
        fieldnames = ['DFIA No', 'DFIA Dt', 'DFIA Exp', 'Exporter', 'PORT', 'Notf No', 'Ledger Date', 'TOTAL CIF',
                      'BAL CIF',
                      'HSN G', 'Total GLUTEN Qty', 'OLD GLUTEN Qty', 'BAL GLUTEN QTY',
                      'HSN P', 'Total RBD Qty', 'BAL RBD QTY',
                      'HSN DF', 'Total DF Qty', 'OLD DF Qty', 'Utilized DF Qty', 'BAL DF QTY',
                      'HSN FF', 'Total FF Qty', 'OLD FF Qty', 'Utilized FF Qty', 'BAL FF QTY',
                      'HSN Fr', 'BAL FC QTY', 'OLD FC Qty', 'Utilized FC Qty', 'Total FC Qty',
                      '10% of CIF', '10% of CIF Utilized', '10% of CIF Balance',
                      'HSN WPC', 'Total WPC Qty', 'BAL WPC QTY',
                      'HSN SWP', 'Total SWP Qty', 'BAL SWP QTY',
                      'Total M&M Oth QTY', 'BAL M&M Oth QTY',
                      'Total Sugar QTY', 'BAL Sugar QTY',
                      'Total Leavening Agent QTY', 'BAL Leavening Agent QTY',
                      'HSN PP', 'Total PP QTY', 'BAL PP QTY',
                      'HSN PAP', 'Total PAP QTY', 'BAL PAP QTY',
                      'Is Individual', 'Is Conversion']

        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for data_dict in data_list:
            writer.writerow(data_dict)


def split_list():
    abc = """1110028747
3010083908
3010088740
5610000025
5610000026
5610000757
5610000774
5610005397
5611000372
5611000373
5611000374
5611000700
5611000702
5611000902
5611000903
0310597347
0310649566
0310651203
0310662205
0310662211
0310662228
0310662263
0310662916
0310663434
0310663738
0310663741
0310664331
0310680954
0310681422
0310681621
0310682293
0310683014
0310689065
0310694983
0310696108
0310701844
0310702495
0310704333
0310705160
0310709650
0310713518
0310714016
0310721806
0310721821
0310727816
0310729479
0310729706
0310729712
0310732431
0310732679
0310732837
0310733663
0310734213
0310734251
0310736178
0310736179
0310736630
0310736633
0310736634
0310736635
0310736637
0310736838
0310736955
0310736957
0310736984
0310737816
0310737818
0310737859
0310737945
0310738215
0310738501
0310738503
0310739944
0310740492
0310740498
0310740542
0310740546
0310740591
0310740606
0310740883
0310740886
0310740937
0310741378
0310741591
0310742587
0310743303
0310763644
0310776850
0310776851
0310776854
0310818080
0310818438
0310821169
0310823762
0310825085
0310826316
0310826693
0310827015
0310827361
0310827442
0310827509
0310827783
0310828159
0310828173
0310828188
0310829658
0310829956
0310829966
0310829982
0310830074
0310830107
0310830441
0310830480
0310831147
0310831148
0310831149
0310831828
0310831843
0310831990
0310831992
0310832269
0310832494
0310832880
0310832983
0310832985
0310833197
0310833198
0310833199
0310833589
0310833591
0310833729
0310833822
0310833846
0310834150
0310834152
0310834612
0310834800
0310834824
0310834907
0310834927
0310834966
0310834974
0310834976
0310835121
0310835188
0310835189
0310835296
0310835340
0310835514
0310835517
0310835559
0310836033
0310836589
0310837232
0310837233
0310837902
0310837960
0310837994
0310837998
0310838098
0310838101
0310838340
0310838342
0310838698
0310838864
0310838902
0310838914
0310838915
0310838967
0310838970
0310839157
0310839189
0310839549
0311001615
0311001859
0311002062
0311002421
0311004131
0311004132
0311004252
0311004313
0311004327
0311004329
0311004330
0311004337
0311004339
0311004351
0311004362
0311004535
0311004570
0311004571
0311004618
0311004626
0311004780
0311004927
0311004966
0311005134
0311005275
0311005312
0311005336
0311005427
0311005442
0311005485
0311005488
0311005616
0311005696
0311005927
0311006011
0311006037
0311006039
0311006070
0311006106
0311006234
0311006347
0311006527
0311006591
0311006746
0311006833
0311007217
0311007633
0311008157
0311008159
0311008561
0311008585
0311008749
0311009007
0311009354
0311009735
0311009988
0311010273
0311010402
0311010658
0311010790
0311010834
0311010857
0311010861
0311011367
0311011594
0311011837
0311012292
0311013560
0311013659
0311013896
0311014196
0311014723
0510336995
0810145922
0810145989
0910052275
0910052935
0910052936
0910054101
0910054277
0910054797
0910054971
0910055369
0910055370
0910055710
0910055749
0910055750
0910055752
0910055753
0910055754
0910055812
0910056125
0910056126
0910057477
0910057492
0910058234
0910058236
0910059714
0910059715
0910059760
0910059761
0910060696
0910060902
0910061030
0910061031
0910061490
0910061491
0910061780
0910061781
0910061782"""
    return abc.split()
