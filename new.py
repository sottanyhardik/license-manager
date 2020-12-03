import csv
license = LicenseDetailsModel.objects.all()
with open('confectionery.csv', 'w') as csvfile:
    fieldnames = ['DFIA', 'DFIA DT', 'DFIA EXP', 'DFIA File No', 'Exporter', 'BAL CIF', 'User Comment', 'Juice', 'OCI', 'Milk','Flavour']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for dfia in license:
        if dfia.get_norm_class == 'E1':
            try:
                dict_data = {
                    'DFIA':dfia.license_number,
                    'DFIA DT':str(dfia.license_date),
                    'DFIA EXP':str(dfia.license_expiry_date),
                    'DFIA File No':str(dfia.file_number),
                    'Exporter':dfia.exporter.name[:15],
                    'BAL CIF': float(dfia.balance_cif),
                    'User Comment':str(dfia.user_comment),
                    'Juice':"",
                    'OCI':"",
                    'Milk':"",
                    'Flavour':"",
                }
                import_item = dfia.import_license.filter(item__head__name__icontains='juice')
                if import_item.exists():
                    dict_data['Juice'] = import_item[0].balance_quantity
                import_item = dfia.import_license.filter(item__head__name__icontains='milk')
                if import_item.exists():
                    dict_data['Milk'] = import_item[0].balance_quantity
                import_item = dfia.import_license.filter(item__head__name__icontains='flavour')
                if import_item.exists():
                    dict_data['Flavour'] = import_item[0].balance_quantity
                import_item = dfia.import_license.filter(item__head__name__icontains='other confectionery')
                if import_item.exists():
                    dict_data['OCI'] = import_item[0].balance_quantity
                writer.writerow(dict_data)
            except Exception as e:
                print(e)


