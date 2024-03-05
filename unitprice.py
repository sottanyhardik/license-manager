import datetime
start = datetime.datetime.now()
fl = LicenseImportItemsModel.objects.filter(license__export_license__norm_class__norm_class='E1',license__license_expiry_date__gte=start,item__name__icontains='Flavour')

for f in fl:
    f.cif_fc = f.quantity*6.22
    flavour = LicenseImportItemsModel.objects.filter(license__export_license__norm_class__norm_class='E1',license__license_expiry_date__gte=start,item__name__icontains='Flavour', license=f.license).aggregate(Sum('cif_fc')).get('cif_fc__sum')
    val = f.license.get_per_essential_oil - flavour
    LicenseImportItemsModel.objects.filter(license__export_license__norm_class__norm_class='E1',license__license_expiry_date__gte=start,item__name__icontains='ESSENTIAL', license=f.license).update(cif_fc=val)
    f.save()
