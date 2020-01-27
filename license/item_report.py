import datetime

from django.db.models import Q, Sum

from . import models as license
from .models import N2009, N2015
from .tables import LicenseItemReportTable


def sugar_query():
    total_quantity = 0
    tables = []
    try:
        expirty_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, item__head__name__icontains='sugar').order_by('license__license_expiry_date')
        confectionery_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E1',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, item__head__name__icontains='sugar').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        for object in confectionery_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        confectionery_queryset = confectionery_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Confectinery 098/2019 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI Other Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Other Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Biscuits Remaning 019/2015 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})

        filter_query = confectionery_queryset.filter(license__export_license__old_quantity=0,
                                                     license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Other Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = confectionery_queryset.filter(license__export_license__old_quantity=0,
                                                     license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Other Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})

        filter_query = confectionery_queryset.filter(license__export_license__old_quantity=0,
                                                     license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Confectinery Remaning 019/2015 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        return tables
    except Exception as e:
        return False


def rbd_query():
    total_quantity = 0
    tables = []
    try:
        expirty_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, item__head__name__icontains='RBD Palmolein Oil').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Old Notifications', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI Other Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Other Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Biscuits Remaning 019/2015 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        return tables
    except Exception as e:
        return False


def milk_query():
    tables = []
    try:
        expirty_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, item__head__name__icontains='milk & milk products').exclude(item__name__icontains='skim').exclude(item__head__name__icontains='skimmed').exclude(hs_code__hs_code__startswith='35').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Old Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI Other Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Other Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Biscuits Remaning 019/2015 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        return tables
    except Exception as e:
        return False


def skimmed_milk_query():
    tables = []
    try:
        expirty_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, item__name__icontains='skimmed').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Old Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI Other Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Other Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Biscuits Remaning 019/2015 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        return tables
    except Exception as e:
        return False


def wpc_query():
    tables = []
    try:
        expirty_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, hs_code__hs_code__startswith='35', item__head__name__icontains='milk').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI Other Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Other Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = biscuits_queryset.filter(license__export_license__old_quantity=0,
                                                license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Biscuits Remaning 019/2015 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        return tables
    except Exception as e:
        return False


def dietary_query():
    tables = []
    try:
        expirty_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, item__head__name__icontains='dietary fibre').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'OLD NOTIFICATION', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        return tables
    except Exception as e:
        return False


def food_query():
    tables = []
    try:
        expirty_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, item__head__name__icontains='food flavour').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'OLD NOTIFICATION', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Biscuits', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        return tables
    except Exception as e:
        return False


def juice_query():
    tables = []
    try:
        expirty_limit = datetime.datetime.today()
        confectionery_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E1',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, item__head__name__icontains='juice').order_by('license__license_expiry_date')
        for object in confectionery_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        confectionery_queryset = confectionery_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Confectinery 098/2019 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        return tables
    except Exception as e:
        return False


def packing_query():
    tables = []
    try:
        expirty_limit = datetime.datetime.today()
        confectionery_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E1',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, item__head__name__icontains='packing material (PP)').order_by('license__license_expiry_date')
        for object in confectionery_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        confectionery_queryset = confectionery_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Confectinery 098/2019 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = confectionery_queryset.filter(license__export_license__old_quantity=0,
                                                     license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Other Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = confectionery_queryset.filter(license__export_license__old_quantity=0,
                                                     license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Other Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})

        filter_query = confectionery_queryset.filter(license__export_license__old_quantity=0,
                                                     license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(license__exporter__name__icontains='parle')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Confectinery Remaning 019/2015 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        return tables
    except Exception as e:
        return False


def oci_query():
    tables = []
    try:
        expirty_limit = datetime.datetime.today()
        confectionery_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E1',
            license__license_expiry_date__gte=expirty_limit,
            license__is_self=True, item__head__name__icontains='other confectionery').order_by('license__license_expiry_date')
        for object in confectionery_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        confectionery_queryset = confectionery_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).filter(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RAMA RANI VANNILA Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).filter(
            license__exporter__name__icontains='parle').exclude(
            license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Parle Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2009).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Confectinery 098/2019 Notification', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = confectionery_queryset.filter(license__notification_number=N2015).exclude(
            Q(license__exporter__name__icontains='rama') | Q(license__exporter__name__icontains='rani') | Q(
                license__exporter__name__icontains='vanila') | Q(
                license__exporter__name__icontains='parle')).exclude(license__export_license__old_quantity=0).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Viva, V A global, Vipul Kumar Confectinery', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum',
                                                                                      0.0)})
        return tables
    except Exception as e:
        return False


