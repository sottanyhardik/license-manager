import datetime

from django.db.models import Q, Sum

from . import models as license
from .models import N2009, N2015
from .tables import LicenseItemReportTable


def sugar_query():
    total_quantity = 0
    tables = []
    try:
        expiry_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__license_expiry_date__gte=expiry_limit,
            license__is_self=True, license__is_au=False, item__head__name__icontains='sugar').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'License List', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        return tables
    except Exception as e:
        return False


def rbd_query():
    total_quantity = 0
    tables = []
    try:
        expiry_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expiry_limit,
            license__is_self=True, license__is_au=False, item__head__name__icontains='RBD Palmolein Oil').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.filter(hs_code__hs_code__icontains='15119020').distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RBD Palmolein Oil', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter(hs_code__hs_code__icontains='15119010').distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'RBD Palm Oil', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.exclude(Q(hs_code__hs_code__icontains='15119010')|Q(hs_code__hs_code__icontains='15119020')).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Need Amendment', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        return tables
    except Exception as e:
        return False


def milk_query():
    tables = []
    try:
        expiry_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expiry_limit,
            license__is_self=True, license__is_au=False, item__head__name__icontains='milk & milk products').filter(hs_code__hs_code__icontains='04041020').exclude(hs_code__hs_code__startswith='35').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'License Lists', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        return tables
    except Exception as e:
        return False


def skimmed_milk_query():
    tables = []
    try:
        expiry_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expiry_limit,
            license__is_self=True, license__is_au=False).filter(Q(item__name__icontains='skim')|Q(item__name__icontains='skimmed')).order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'License List', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        return tables
    except Exception as e:
        return False


def wpc_query():
    tables = []
    try:
        expiry_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expiry_limit,
            license__is_self=True, license__is_au=False, hs_code__hs_code__startswith='35', item__head__name__icontains='milk').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'License Lists', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        return tables
    except Exception as e:
        return False


def dietary_query():
    tables = []
    try:
        expiry_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expiry_limit,
            license__is_self=True, license__is_au=False, item__head__name__icontains='dietary fibre').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.filter((Q(license__export_license__old_quantity__gt=1)&Q(license__notification_number=N2015))|Q(license__notification_number=N2009)).filter(hs_code__hs_code__startswith='08').distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'License Lists', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = biscuits_queryset.filter((Q(license__export_license__old_quantity__gt=1)&Q(license__notification_number=N2015))|Q(license__notification_number=N2009)).exclude(hs_code__hs_code__startswith='08').distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Need Amendment', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        return tables
    except Exception as e:
        return False


def food_query():
    tables = []
    try:
        expiry_limit = datetime.datetime.today()
        biscuits_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E5',
            license__license_expiry_date__gte=expiry_limit,
            license__is_self=True, license__is_au=False, item__head__name__icontains='food flavour').order_by('license__license_expiry_date')
        for object in biscuits_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        biscuits_queryset = biscuits_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = biscuits_queryset.filter((Q(license__export_license__old_quantity__gt=1)&Q(license__notification_number=N2015))|Q(license__notification_number=N2009)).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'License List', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        return tables
    except Exception as e:
        return False


def juice_query():
    tables = []
    try:
        expiry_limit = datetime.datetime.today()
        confectionery_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E1',
            license__license_expiry_date__gte=expiry_limit,
            license__is_self=True, license__is_au=False, item__head__name__icontains='juice').order_by('license__license_expiry_date')
        for object in confectionery_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        confectionery_queryset = confectionery_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = confectionery_queryset.filter((Q(license__export_license__old_quantity__gt=1)&Q(license__notification_number=N2015))|Q(license__notification_number=N2009)).filter(hs_code__hs_code__startswith='2009').distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'License Lists', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        filter_query = confectionery_queryset.filter((Q(license__export_license__old_quantity__gt=1)&Q(license__notification_number=N2015))|Q(license__notification_number=N2009)).exclude(hs_code__hs_code__startswith='2009').distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'Amendment Needed', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        return tables
    except Exception as e:
        return False


def packing_query():
    tables = []
    try:
        expiry_limit = datetime.datetime.today()
        confectionery_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E1',
            license__license_expiry_date__gte=expiry_limit,
            license__is_self=True, license__is_au=False, item__head__name__icontains='packing material (PP)').order_by('license__license_expiry_date')
        for object in confectionery_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        confectionery_queryset = confectionery_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = confectionery_queryset.distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'License List', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        return tables
    except Exception as e:
        return False


def oci_query():
    tables = []
    try:
        expiry_limit = datetime.datetime.today()
        confectionery_queryset = license.LicenseImportItemsModel.objects.filter(
            license__export_license__norm_class__norm_class='E1',
            license__license_expiry_date__gte=expiry_limit,
            license__is_self=True, license__is_au=False, item__head__name__icontains='other confectionery').order_by('license__license_expiry_date')
        for object in confectionery_queryset:
            object.available_quantity = object.balance_quantity
            object.available_value = object.balance_cif_fc
            object.save()
        confectionery_queryset = confectionery_queryset.filter(Q(available_quantity__gte=1000))
        filter_query = confectionery_queryset.filter((Q(license__export_license__old_quantity__gt=1)&Q(license__notification_number=N2015))|Q(license__notification_number=N2009)).distinct()
        table = LicenseItemReportTable(filter_query)
        tables.append({'label': 'License List', 'table': table,
                       'total': filter_query.aggregate(Sum('available_quantity')).get('available_quantity__sum', 0.0)})
        return tables
    except Exception as e:
        return False


