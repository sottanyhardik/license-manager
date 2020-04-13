import datetime
from license.models import N2015, N2009


def convert(query, name):
    import csv
    with open(name, 'w', newline='') as csvfile:
        total_dict = {}
        counter = 1
        for license in query:
            fieldnames = ['sr_no', 'license_number','license_date', 'license_expiry', 'exporter', 'value_balance', 'hs_code',
                          'import_item','quantity_balance','port']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            number = license.license_number
            expiry = license.license_expiry_date.strftime('%d/%m/%Y')
            date = license.license_date.strftime('%d/%m/%Y')
            exporter = license.exporter
            value_balance = license.export_license.all()[0].balance_cif_fc()
            import_datas = license.import_license.all()
            dict_data = {
                'sr_no': counter,
                'license_number': str(number),
                'license_date': str(date),
                'license_expiry': str(expiry),
                'exporter': str(exporter),
                'value_balance': str(value_balance),
                'hs_code': "",
                'import_item': "",
                'quantity_balance': "",
                'port': str(license.port.code),
            }
            file = False
            counter = counter + 1
            for import_data in import_datas:
                if import_data.item.head:
                    dict_data['import_item'] = str(import_data.item.head.name)
                else:
                    dict_data['import_item'] = str(import_data.item.name)
                dict_data['hs_code'] = "'" + import_data.hs_code.hs_code
                dict_data['quantity_balance'] = int(import_data.balance_quantity)
                if not license.is_null and not int(import_data.balance_quantity) < 1000:
                    if import_data.item.name in list(total_dict.keys()):
                        total_dict[import_data.item.name] = int(import_data.balance_quantity) + total_dict[
                            import_data.item.name]
                    else:
                        total_dict[import_data.item.name] = int(import_data.balance_quantity)
                writer.writerow(dict_data)
                if file:
                    dict_data = {
                        'sr_no': '',
                        'license_number': '',
                        'license_date': '',
                        'license_expiry': '',
                        'exporter': '',
                        'value_balance': '',
                        'hs_code': "",
                        'import_item': "",
                        'quantity_balance': "",
                        'port':""
                    }
                else:
                    dict_data = {
                        'sr_no': '',
                        'license_number': license.file_number,
                        'license_date': '',
                        'license_expiry': '',
                        'exporter': '',
                        'value_balance': '',
                        'hs_code': "",
                        'import_item': "",
                        'quantity_balance': "",
                        'port': ""
                    }
                    file = True
            writer.writerow(dict_data)
        dict_data = {
            'sr_no': '',
            'license_number': 'Total',
            'license_date': '',
            'license_expiry': '',
            'exporter': '',
            'value_balance': '',
            'hs_code': "",
            'import_item': "",
            'quantity_balance': "",
            'port': ""
        }
        for key in list(total_dict.keys()):
            dict_data['import_item'] = str(key)
            dict_data['quantity_balance'] = int(total_dict[key])
            writer.writerow(dict_data)
            dict_data = {
                'license_number': '',
                'license_date': '',
                'license_expiry': '',
                'exporter': '',
                'value_balance': '',
                'hs_code': "",
                'import_item': "",
                'quantity_balance': "",
                'port': ""
            }


def fetch():
    from license.models import LicenseDetailsModel
    from _datetime import datetime, timedelta
    expiry_limit = datetime.today() - timedelta(days=30)
    query = LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E1', notification_number=N2015,
                                               is_null=False).filter(license_expiry_date__gt=expiry_limit).order_by('license_expiry_date')
    convert(query, 'Confectionery_19_2015.csv')
    query = LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E1', notification_number=N2009,
                                               is_null=False).filter(license_expiry_date__gt=expiry_limit).order_by('license_expiry_date')
    convert(query, 'Confectionery_98_2009.csv')
    query = LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5', notification_number=N2015,
                                               is_null=False).filter(license_expiry_date__gt=expiry_limit).order_by('license_expiry_date')
    convert(query, 'Biscuits_19_2015.csv')
    query = LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5', notification_number=N2009,
                                               is_null=False).filter(license_expiry_date__gt=expiry_limit).order_by('license_expiry_date')
    convert(query, 'Biscuits_98_2009.csv')
    # query = LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E1', notification_number=N2015,
    #                                           is_null=True).filter(license_expiry_date__gt=expiry_limit)
    # convert(query, 'Confectionery_19_2015_null.csv')
    # query = LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E1', notification_number=2,
    #                                           is_null=True).filter(license_expiry_date__gt=expiry_limit)
    # convert(query, 'Confectionery_98_2009_null.csv')
    # query = LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5', notification_number=N2015,
    #                                           is_null=True).filter(license_expiry_date__gt=expiry_limit)
    # convert(query, 'Biscuits_19_2015_null.csv')
    # query = LicenseDetailsModel.objects.filter(export_license__norm_class__norm_class='E5', notification_number=N2015,
    #                                           is_null=True).filter(license_expiry_date__gt=expiry_limit)
    # convert(query, 'Biscuits_98_2009_null.csv')
