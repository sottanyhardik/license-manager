import xlsxwriter

from license.models import LicenseDetailsModel


def get_license_table(license):
    license = LicenseDetailsModel.objects.get(license_number=license)
    # Simulate a more complex table read.
    if license.exporter and license.exporter.name:
        exporter = license.exporter.name
    else:
        exporter = ""
    if license.license_expiry_date:
        date = license.license_expiry_date.strftime('%d-%m-%Y')
    else:
        date = ""
    if license.license_expiry_date:
        license_expiry_date = license.license_expiry_date.strftime('%d-%m-%Y')
    else:
        license_expiry_date = ""
    data_list = [
        ["License Number", "License Date", "License Expiry", "File Number"],
        [license.license_number, date, license_expiry_date, license.file_number],
        [],
        ["Notification", "Scheme Code", "Exporter", "Port", ],
        [license.get_notification_number_display(), license.scheme_code, exporter, license.port.code],
        [],
        ["Export Items"],
        [],
        ['Item', 'Total CIF', 'Balance CIF'],
    ]
    for item in license.export_license.all():
        item_list = []
        if item.item and item.item.name:
            item_list.append(item.item.name)
        else:
            item_list.append("")
        item_list.append(item.cif_fc)
        item_list.append(item.balance_cif_fc())
        data_list.append(item_list)
    data_list.append([])
    data_list.append(["Import  Items"])
    data_list.append([])
    data_list.append(["Sr No", "HS Code", "Item", "Quantity", "Balance Quantity", "CIF FC", "Balance CIF FC"])
    for item in license.import_license.all():
        item_list = [item.serial_number]
        if item.hs_code and item.hs_code.hs_code:
            item_list.append(str(item.hs_code.hs_code))
        else:
            item_list.append("")
        if item.item and item.item.name:
            item_list.append(item.item.name)
        else:
            item_list.append("")
        item_list.append(item.quantity)
        item_list.append(item.balance_quantity)
        if item.cif_fc and not item.cif_fc == 0:
            item_list.append(item.cif_fc)
        if item.dbalance_cif_fc:
            item_list.append(item.balance_quantity)
        data_list.append(item_list)
    return data_list
