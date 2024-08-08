import datetime


def convert(query, name):
    import csv
    with open(name, 'w', newline='') as csvfile:
        total_dict = {}
        counter = 1
        for license in query:
            fieldnames = ['sr_no', 'license_number', 'license_expiry', 'exporter', 'value_balance', 'import_item',
                          'quantity_balance']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            number = license.license_number
            expiry = license.license_expiry_date
            exporter = license.exporter
            value_balance = license.export_license.all()[0].balance_cif_fc()
            import_datas = license.import_license.all()
            dict_data = {
                'sr_no': counter,
                'license_number': number,
                'license_expiry': str(expiry),
                'exporter': str(exporter),
                'value_balance': str(value_balance),
                'import_item': "",
                'quantity_balance': "",
            }
            file = False
            counter = counter + 1
            for import_data in import_datas:
                dict_data['import_item'] = str(import_data.description)
                dict_data['quantity_balance'] = int(import_data.balance_quantity)
                if not license.is_null and not int(import_data.balance_quantity) < 1000:
                    if import_data.description in list(total_dict.keys()):
                        total_dict[import_data.description] = int(import_data.balance_quantity) + total_dict[
                            import_data.description]
                    else:
                        total_dict[import_data.description] = int(import_data.balance_quantity)
                writer.writerow(dict_data)
                if file:
                    dict_data = {
                        'sr_no': '',
                        'license_number': '',
                        'license_expiry': '',
                        'exporter': '',
                        'value_balance': '',
                        'import_item': "",
                        'quantity_balance': "",
                    }
                else:
                    dict_data = {
                        'sr_no': '',
                        'license_number': license.file_no,
                        'license_expiry': '',
                        'exporter': '',
                        'value_balance': '',
                        'import_item': "",
                        'quantity_balance': "",
                    }
                    file = True
            writer.writerow(dict_data)
        dict_data = {
            'sr_no': '',
            'license_number': 'Total',
            'license_expiry': '',
            'exporter': '',
            'value_balance': '',
            'import_item': "",
            'quantity_balance': "",
        }
        for key in list(total_dict.keys()):
            dict_data['import_item'] = str(key)
            dict_data['quantity_balance'] = int(total_dict[key])
            writer.writerow(dict_data)
            dict_data = {
                'license_number': '',
                'license_expiry': '',
                'exporter': '',
                'value_balance': '',
                'import_item': "",
                'quantity_balance': "",
            }


def fetch():
    from license.models import LicenseDetailModel
    from core.scripts.license_script import convert
    import datetime
    query = LicenseDetailModel.objects.filter(export_license__norm_class__norm_class='E1', notification_number=1,
                                              approve=True, is_null=False).filter(license_expiry_date__gt=datetime.datetime.now())
    convert(query, 'Confectionery_19_2015.csv')
    query = LicenseDetailModel.objects.filter(export_license__norm_class__norm_class='E1', notification_number=2,
                                              approve=True, is_null=False).filter(license_expiry_date__gt=datetime.datetime.now())
    convert(query, 'Confectionery_98_2009.csv')
    query = LicenseDetailModel.objects.filter(export_license__norm_class__norm_class='E5', notification_number=1,
                                              approve=True, is_null=False).filter(license_expiry_date__gt=datetime.datetime.now())
    convert(query, 'Biscuits_19_2015.csv')
    query = LicenseDetailModel.objects.filter(export_license__norm_class__norm_class='E5', notification_number=2,
                                              approve=True, is_null=False).filter(license_expiry_date__gt=datetime.datetime.now())
    convert(query, 'Biscuits_98_2009.csv')
    query = LicenseDetailModel.objects.filter(export_license__norm_class__norm_class='E1', notification_number=1,
                                              approve=True, is_null=True)
    convert(query, 'Confectionery_19_2015_null.csv')
    query = LicenseDetailModel.objects.filter(export_license__norm_class__norm_class='E1', notification_number=2,
                                              approve=True, is_null=True)
    convert(query, 'Confectionery_98_2009_null.csv')
    query = LicenseDetailModel.objects.filter(export_license__norm_class__norm_class='E5', notification_number=1,
                                              approve=True, is_null=True)
    convert(query, 'Biscuits_19_2015_null.csv')
    query = LicenseDetailModel.objects.filter(export_license__norm_class__norm_class='E5', notification_number=2,
                                              approve=True, is_null=True)
    convert(query, 'Biscuits_98_2009_null.csv')