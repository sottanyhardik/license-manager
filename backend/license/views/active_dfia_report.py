# license/views/active_dfia_report.py
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Sum, Q
from rest_framework.decorators import action
from rest_framework.response import Response


def add_active_dfia_report_action(viewset_class):
    """
    Decorator to add Active DFIA report functionality to LicenseDetailsViewSet.
    Generates Excel-like report grouped by SION norm, then by notification within each norm.
    """

    @action(detail=False, methods=['get'], url_path='active-dfia-report')
    def active_dfia_report(self, request):
        """
        Generate Active DFIA report with all Excel columns, grouped by SION norm class.

        URL: /api/licenses/active-dfia-report/

        Query params:
            - exporter: filter by exporter ID (optional, defaults to Parle companies)
            - is_expired: filter by expiry status (optional, default: False)
            - is_null: filter by null status (optional, default: False)
            - sion_norm: filter by specific SION norm class (optional)
            - notification: filter by specific notification number (optional)
        """
        from core.models import CompanyModel

        # Get filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Filter for Parle companies if not specified
        exporter_id = request.query_params.get('exporter')
        if not exporter_id:
            # Get all Parle companies
            parle_companies = CompanyModel.objects.filter(
                Q(name__icontains='PARLE')
            ).values_list('id', flat=True)
            queryset = queryset.filter(exporter_id__in=parle_companies)

        # Filter by SION norm if specified
        sion_norm = request.query_params.get('sion_norm')
        if sion_norm:
            queryset = queryset.filter(export_license__norm_class__norm_class=sion_norm).distinct()

        # Filter by notification number if specified
        notification = request.query_params.get('notification')
        if notification:
            queryset = queryset.filter(notification_number=notification)

        # Apply is_expired filter - default to False (active only)
        is_expired = request.query_params.get('is_expired', 'False')
        if is_expired == 'False' or is_expired == 'false':
            today = date.today()
            queryset = queryset.filter(
                Q(license_expiry_date__gte=today) | Q(license_expiry_date__isnull=True)
            )
        elif is_expired == 'True' or is_expired == 'true':
            queryset = queryset.filter(license_expiry_date__lt=date.today())

        # Apply is_null filter - default to False (balance >= 200)
        is_null = request.query_params.get('is_null', 'False')
        if is_null == 'False' or is_null == 'false':
            queryset = queryset.filter(balance_cif__gte=200)
        elif is_null == 'True' or is_null == 'true':
            queryset = queryset.filter(balance_cif__lt=200)

        # Prefetch related data for performance
        queryset = queryset.select_related(
            'exporter', 'port', 'current_owner'
        ).prefetch_related(
            'export_license', 'export_license__norm_class',
            'import_license', 'import_license__items', 'import_license__hs_code'
        ).order_by('-license_date')

        # Group licenses by SION norm class, then by notification
        # Structure: {sion_norm: {notification: [licenses]}}
        grouped_data = defaultdict(lambda: defaultdict(list))

        for license_obj in queryset:
            # Get SION norm class (CSV of all norm classes)
            norm_class = license_obj.get_norm_class or 'Unknown'
            # For grouping, use the first norm class if multiple
            primary_norm = norm_class.split(',')[0].strip() if norm_class else 'Unknown'

            notification_num = license_obj.notification_number or 'Unknown'

            # Basic license info
            license_data = {
                'id': license_obj.id,
                'license_number': license_obj.license_number,
                'license_date': license_obj.license_date,
                'license_expiry_date': license_obj.license_expiry_date,
                'exporter_name': license_obj.exporter.name if license_obj.exporter else '',
                'notification_number': notification_num,
                'sion_norm': primary_norm,
            }

            # Calculate total CIF from export license items
            total_cif = license_obj.export_license.aggregate(
                total=Sum('cif_fc')
            )['total'] or Decimal('0')
            license_data['total_cif'] = float(total_cif)
            license_data['balance_cif'] = float(license_obj.balance_cif) if license_obj.balance_cif else 0.0

            # Calculate total debits (total_cif - balance_cif)
            total_debits = total_cif - (license_obj.balance_cif or Decimal('0'))
            license_data['total_debits'] = float(total_debits)

            # Helper to get item data by name (case-insensitive)
            def get_item_by_name(name):
                """Get item quantity and CIF by matching item name"""
                item = license_obj.get_item_data(name)
                # Use available_quantity_sum to show remaining/unused quantities
                qty = item.get('available_quantity_sum', Decimal('0'))
                # Get debited quantity (total - available = debited)
                total_qty = item.get('available_quantity_sum', Decimal('0'))
                debited_qty = total_qty - qty
                # Calculate CIF based on quantity and unit price
                unit_price = item.get('items__unit_price', Decimal('0'))
                cif = qty * unit_price if qty and unit_price else Decimal('0')
                return {
                    'qty': float(qty),
                    'cif': float(cif),
                    'hs_code': item.get('hs_code__hs_code', ''),
                    'description': item.get('description', ''),
                    'debited_qty': float(debited_qty)
                }

            # Helper to get item data by head name
            def get_item_by_head(head_name):
                """Get total quantity and description for items under a head"""
                head_data = license_obj.get_item_head_data(head_name)
                # Use available_quantity_sum to show remaining/unused quantities
                qty = head_data.get('available_quantity_sum', Decimal('0'))
                # Get total allocated quantity (not available)
                total_qty = head_data.get('available_quantity_sum', Decimal('0'))
                debited_qty = total_qty - qty
                return {
                    'qty': float(qty),
                    'total_qty': float(total_qty),  # Add total allocated quantity
                    'hs_code': head_data.get('hs_code__hs_code', ''),
                    'description': head_data.get('description', ''),
                    'debited_qty': float(debited_qty)
                }

            # Vegetable Oil breakdown
            veg_oil_data = get_item_by_head('VEGETABLE OIL')
            rbd_data = get_item_by_name('RBD PALMOLEIN OIL')
            pko_data = get_item_by_name('PALM KERNEL OIL')
            olive_data = get_item_by_name('OLIVE OIL')
            pomace_data = get_item_by_name('POMACE OIL')

            license_data['vegetable_oil'] = {
                'hsn_code': veg_oil_data['hs_code'] or '15132110',
                'description': veg_oil_data[
                                   'description'] or 'Fats - Edible Vegetable Oil /Palmolein Oil / Palm Kernel Oil /Cocoa Butter',
                'total_qty': veg_oil_data['total_qty'],  # Use total_qty (allocated) not available
                'total_debited_qty': veg_oil_data['debited_qty'],
                'rbd_qty': rbd_data['qty'],
                'rbd_cif': rbd_data['cif'],
                'rbd_debited_qty': rbd_data['debited_qty'],
                'pko_qty': pko_data['qty'],
                'pko_cif': pko_data['cif'],
                'pko_debited_qty': pko_data['debited_qty'],
                'olive_qty': olive_data['qty'],
                'olive_cif': olive_data['cif'],
                'olive_debited_qty': olive_data['debited_qty'],
                'pomace_qty': pomace_data['qty'],
                'pomace_cif': pomace_data['cif'],
                'pomace_debited_qty': pomace_data['debited_qty'],
            }

            # 10% Balance (restriction)
            per_cif = license_obj.get_per_cif or {}
            ten_restriction = per_cif.get('tenRestriction', Decimal('0'))
            license_data['ten_percent_balance'] = float(ten_restriction)

            # Juice and Food Flavour both in HEAD "FOOD FLAVOUR"
            food_flavour_head_data = get_item_by_head('FOOD FLAVOUR')

            # Juice
            biscuit_juice = license_obj.get_biscuit_juice
            juice_qty = biscuit_juice.get('available_quantity_sum', Decimal('0'))
            juice_total_qty = biscuit_juice.get('quantity_sum', Decimal('0'))
            juice_debited_qty = juice_total_qty - juice_qty
            juice_unit_price = biscuit_juice.get('items__unit_price', Decimal('0'))
            juice_cif = juice_qty * juice_unit_price if juice_qty and juice_unit_price else Decimal('0')

            license_data['juice'] = {
                'hsn_code': food_flavour_head_data['hs_code'] or '08023100',
                'description': food_flavour_head_data['description'] or 'RELEVANT FLAVOUR IMPROVERS - FRUIT FLAVOUR',
                'qty': float(juice_qty),
                'cif': float(juice_cif),
                'debited_qty': float(juice_debited_qty),
            }

            # Food Flavour
            ff_data = get_item_by_name('FOOD FLAVOUR BISCUITS')
            df_data = get_item_by_name('DIETARY FIBRE')
            license_data['food_flavour'] = {
                'hsn_code': food_flavour_head_data['hs_code'],
                'description': food_flavour_head_data['description'],
                'ff_qty': ff_data['qty'],
                'ff_debited_qty': ff_data['debited_qty'],
                'df_qty': df_data['qty'],
                'df_debited_qty': df_data['debited_qty'],
            }

            # Fruit/Cocoa
            fruit_data = get_item_by_name('FRUIT/COCOA')
            license_data['fruit_cocoa'] = {
                'hsn_code': fruit_data['hs_code'] or '',
                'description': fruit_data['description'] or '',
                'qty': fruit_data['qty'],
                'cif': fruit_data['cif'],
                'debited_qty': fruit_data['debited_qty'],
            }

            # Leavening Agent
            leavening_data = get_item_by_name('LEAVENING AGENT')
            license_data['leavening_agent'] = {
                'hsn_code': leavening_data['hs_code'] or '',
                'description': leavening_data['description'] or '',
                'qty': leavening_data['qty'],
                'debited_qty': leavening_data['debited_qty'],
            }

            # Starch 1108
            starch_1108_data = get_item_by_name('STARCH 1108')
            license_data['starch_1108'] = {
                'hsn_code': starch_1108_data['hs_code'] or '',
                'description': starch_1108_data['description'] or '',
                'qty': starch_1108_data['qty'],
                'cif': starch_1108_data['cif'],
                'debited_qty': starch_1108_data['debited_qty'],
            }

            # Starch 3505
            starch_3505_data = get_item_by_name('STARCH 3505')
            license_data['starch_3505'] = {
                'hsn_code': starch_3505_data['hs_code'] or '',
                'description': starch_3505_data['description'] or '',
                'qty': starch_3505_data['qty'],
                'debited_qty': starch_3505_data['debited_qty'],
            }

            # Milk & Milk Products
            mnm_data = get_item_by_head('MILK & MILK Product')
            cheese_data = get_item_by_name('CHEESE')
            swp_data = get_item_by_name('SWP')
            wpc_data = get_item_by_name('WPC')

            # Use biscuits calculation for milk products CIF
            biscuits_calc = license_obj.cif_value_balance_biscuits

            license_data['milk_and_milk'] = {
                'hsn_code': mnm_data['hs_code'],
                'description': mnm_data['description'] or 'Milk & Milk Products / Milk Solids',
                'total_qty': mnm_data['total_qty'],  # Use total_qty (allocated) not available
                'total_debited_qty': mnm_data['debited_qty'],
                'cheese_qty': cheese_data['qty'],
                'cheese_cif': float(biscuits_calc.get('cif_cheese', Decimal('0'))),
                'cheese_debited_qty': cheese_data['debited_qty'],
                'swp_qty': swp_data['qty'],
                'swp_cif': float(biscuits_calc.get('cif_swp', Decimal('0'))),
                'swp_debited_qty': swp_data['debited_qty'],
                'wpc_qty': wpc_data['qty'],
                'wpc_cif': float(biscuits_calc.get('cif_wpc', Decimal('0'))),
                'wpc_debited_qty': wpc_data['debited_qty'],
            }

            # PP and Aluminium Foil both in HEAD "PACKING MATERIAL"
            packing_material_head_data = get_item_by_head('PACKING MATERIAL')

            # PP (Packing Material)
            pp_data = get_item_by_name('PP')
            license_data['pp'] = {
                'hsn_code': packing_material_head_data['hs_code'] or '39021000',
                'description': packing_material_head_data['description'] or 'Packing Material - PP',
                'qty': pp_data['qty'],
                'debited_qty': pp_data['debited_qty'],
            }

            # Aluminium Foil
            aluminium_data = get_item_by_name('ALUMINIUM FOIL')
            license_data['aluminium_foil'] = {
                'hsn_code': packing_material_head_data['hs_code'],
                'description': packing_material_head_data['description'],
                'qty': aluminium_data['qty'],
                'debited_qty': aluminium_data['debited_qty'],
            }

            # Wastage CIF (10% of balance)
            wastage_cif = float(license_obj.balance_cif) * 0.10 if license_obj.balance_cif else 0.0
            license_data['wastage_cif'] = wastage_cif

            # Add to grouped structure
            grouped_data[primary_norm][notification_num].append(license_data)

        # Calculate totals for each notification within each SION norm
        result_by_sion = []

        for sion_norm in sorted(grouped_data.keys()):
            notifications_data = []

            for notification in sorted(grouped_data[sion_norm].keys()):
                licenses = grouped_data[sion_norm][notification]

                # Calculate totals for this notification
                notification_totals = calculate_totals(licenses)

                notifications_data.append({
                    'notification_number': notification,
                    'license_count': len(licenses),
                    'licenses': licenses,
                    'totals': notification_totals,
                })

            # Calculate totals for entire SION norm (all notifications combined)
            all_licenses_in_norm = []
            for notification in grouped_data[sion_norm].values():
                all_licenses_in_norm.extend(notification)

            sion_totals = calculate_totals(all_licenses_in_norm)

            result_by_sion.append({
                'sion_norm': sion_norm,
                'notifications': notifications_data,
                'totals': sion_totals,
                'license_count': len(all_licenses_in_norm),
            })

        # Calculate grand totals across all SION norms
        all_licenses = []
        for sion_group in grouped_data.values():
            for notification_group in sion_group.values():
                all_licenses.extend(notification_group)

        grand_totals = calculate_totals(all_licenses)

        return Response({
            'groups': result_by_sion,
            'grand_totals': grand_totals,
            'summary': {
                'total_licenses': len(all_licenses),
                'total_sion_norms': len(grouped_data),
                'total_cif': grand_totals['total_cif'],
                'balance_cif': grand_totals['balance_cif'],
            }
        })

    def calculate_totals(licenses_list):
        """Helper function to calculate totals for a list of licenses"""
        if not licenses_list:
            return {}

        return {
            'total_cif': sum(lic['total_cif'] for lic in licenses_list),
            'balance_cif': sum(lic['balance_cif'] for lic in licenses_list),
            'total_debits': sum(lic['total_debits'] for lic in licenses_list),
            'veg_oil_total_qty': sum(lic['vegetable_oil']['total_qty'] for lic in licenses_list),
            'veg_oil_total_debited_qty': sum(lic['vegetable_oil']['total_debited_qty'] for lic in licenses_list),
            'rbd_qty': sum(lic['vegetable_oil']['rbd_qty'] for lic in licenses_list),
            'rbd_cif': sum(lic['vegetable_oil']['rbd_cif'] for lic in licenses_list),
            'rbd_debited_qty': sum(lic['vegetable_oil']['rbd_debited_qty'] for lic in licenses_list),
            'pko_qty': sum(lic['vegetable_oil']['pko_qty'] for lic in licenses_list),
            'pko_cif': sum(lic['vegetable_oil']['pko_cif'] for lic in licenses_list),
            'pko_debited_qty': sum(lic['vegetable_oil']['pko_debited_qty'] for lic in licenses_list),
            'olive_qty': sum(lic['vegetable_oil']['olive_qty'] for lic in licenses_list),
            'olive_cif': sum(lic['vegetable_oil']['olive_cif'] for lic in licenses_list),
            'olive_debited_qty': sum(lic['vegetable_oil']['olive_debited_qty'] for lic in licenses_list),
            'pomace_qty': sum(lic['vegetable_oil']['pomace_qty'] for lic in licenses_list),
            'pomace_cif': sum(lic['vegetable_oil']['pomace_cif'] for lic in licenses_list),
            'pomace_debited_qty': sum(lic['vegetable_oil']['pomace_debited_qty'] for lic in licenses_list),
            'ten_percent_balance': sum(lic['ten_percent_balance'] for lic in licenses_list),
            'juice_qty': sum(lic['juice']['qty'] for lic in licenses_list),
            'juice_cif': sum(lic['juice']['cif'] for lic in licenses_list),
            'juice_debited_qty': sum(lic['juice']['debited_qty'] for lic in licenses_list),
            'ff_qty': sum(lic['food_flavour']['ff_qty'] for lic in licenses_list),
            'ff_debited_qty': sum(lic['food_flavour']['ff_debited_qty'] for lic in licenses_list),
            'df_qty': sum(lic['food_flavour']['df_qty'] for lic in licenses_list),
            'df_debited_qty': sum(lic['food_flavour']['df_debited_qty'] for lic in licenses_list),
            'fruit_cocoa_qty': sum(lic['fruit_cocoa']['qty'] for lic in licenses_list),
            'fruit_cocoa_cif': sum(lic['fruit_cocoa']['cif'] for lic in licenses_list),
            'fruit_cocoa_debited_qty': sum(lic['fruit_cocoa']['debited_qty'] for lic in licenses_list),
            'leavening_agent_qty': sum(lic['leavening_agent']['qty'] for lic in licenses_list),
            'leavening_agent_debited_qty': sum(lic['leavening_agent']['debited_qty'] for lic in licenses_list),
            'starch_1108_qty': sum(lic['starch_1108']['qty'] for lic in licenses_list),
            'starch_1108_cif': sum(lic['starch_1108']['cif'] for lic in licenses_list),
            'starch_1108_debited_qty': sum(lic['starch_1108']['debited_qty'] for lic in licenses_list),
            'starch_3505_qty': sum(lic['starch_3505']['qty'] for lic in licenses_list),
            'starch_3505_debited_qty': sum(lic['starch_3505']['debited_qty'] for lic in licenses_list),
            'milk_total_qty': sum(lic['milk_and_milk']['total_qty'] for lic in licenses_list),
            'milk_total_debited_qty': sum(lic['milk_and_milk']['total_debited_qty'] for lic in licenses_list),
            'cheese_qty': sum(lic['milk_and_milk']['cheese_qty'] for lic in licenses_list),
            'cheese_cif': sum(lic['milk_and_milk']['cheese_cif'] for lic in licenses_list),
            'cheese_debited_qty': sum(lic['milk_and_milk']['cheese_debited_qty'] for lic in licenses_list),
            'swp_qty': sum(lic['milk_and_milk']['swp_qty'] for lic in licenses_list),
            'swp_cif': sum(lic['milk_and_milk']['swp_cif'] for lic in licenses_list),
            'swp_debited_qty': sum(lic['milk_and_milk']['swp_debited_qty'] for lic in licenses_list),
            'wpc_qty': sum(lic['milk_and_milk']['wpc_qty'] for lic in licenses_list),
            'wpc_cif': sum(lic['milk_and_milk']['wpc_cif'] for lic in licenses_list),
            'wpc_debited_qty': sum(lic['milk_and_milk']['wpc_debited_qty'] for lic in licenses_list),
            'pp_qty': sum(lic['pp']['qty'] for lic in licenses_list),
            'pp_debited_qty': sum(lic['pp']['debited_qty'] for lic in licenses_list),
            'aluminium_foil_qty': sum(lic['aluminium_foil']['qty'] for lic in licenses_list),
            'aluminium_foil_debited_qty': sum(lic['aluminium_foil']['debited_qty'] for lic in licenses_list),
            'wastage_cif': sum(lic['wastage_cif'] for lic in licenses_list),
        }

    # Add the method to the viewset class
    viewset_class.active_dfia_report = active_dfia_report

    return viewset_class
