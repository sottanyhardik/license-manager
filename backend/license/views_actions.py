# license/views_actions.py
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from core.models import CompanyModel
from license.ledger_pdf import generate_license_ledger_pdf
from license.models import LicenseDetailsModel, LicenseTransferModel


class LicenseActionViewSet(ViewSet):
    """
    ViewSet for license actions like downloading ledger
    """

    @action(detail=True, methods=['get'], url_path='download-ledger')
    def download_ledger(self, request, pk=None):
        """
        Download detailed ledger PDF for a license.
        Groups items by head and shows:
        - Import items with quantities and CIF
        - Allotments (pending BOE)
        - Bill of Entry (debited)
        - Available balance
        """
        license_obj = get_object_or_404(
            LicenseDetailsModel.objects.prefetch_related(
                'import_license__items__group',
                'import_license__items__sion_norm_class',
                'import_license__allotment_details__allotment__company',
                'import_license__hs_code'
            ).select_related(
                'exporter',
                'port'
            ),
            pk=pk
        )

        try:
            # Generate PDF grouped by item
            pdf_content = generate_license_ledger_pdf(license_obj)

            # Create response
            response = HttpResponse(pdf_content, content_type='application/pdf')
            filename = f"License_Ledger_{license_obj.license_number}.pdf"
            response['Content-Disposition'] = f'inline; filename="{filename}"'

            return response

        except Exception as e:
            return Response(
                {'error': f'Failed to generate PDF: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='fetch-ledger')
    def fetch_ledger(self, request, pk=None):
        """
        Fetch ledger details from DGFT API and update database.
        Retrieves latest transaction data for the license.
        """
        license_obj = get_object_or_404(LicenseDetailsModel, pk=pk)

        try:
            # TODO: Implement DGFT API call
            # For now, return a placeholder response
            # The actual implementation will require:
            # 1. DGFT API endpoint URL
            # 2. Authentication credentials/tokens
            # 3. API request parameters (license number, etc.)
            # 4. Response parsing logic
            # 5. Database update logic using ledger_parser_refactored

            return Response({
                'success': False,
                'message': 'DGFT API integration pending - endpoint and credentials required',
                'license_number': license_obj.license_number
            }, status=status.HTTP_501_NOT_IMPLEMENTED)

        except Exception as e:
            return Response(
                {'error': f'Failed to fetch ledger: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='update-license-transfer', permission_classes=[AllowAny])
    def update_license_transfer(self, request):
        """
        Update license ownership and transfer information.
        Called by the update_license_ownership management command.

        Expected payload:
        {
            "license_number": "3010090273",
            "license_date": "2024-01-15",
            "exporter_iec": "0305000123",
            "current_owner": {
                "iec": "0305000456",
                "name": "Company Name"
            },
            "transfers": [...]
        }
        """
        try:
            data = request.data
            license_number = data.get('license_number')
            current_owner_data = data.get('current_owner')

            if not license_number:
                return Response(
                    {'error': 'license_number is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Find the license
            try:
                license_obj = LicenseDetailsModel.objects.get(license_number=license_number)
            except LicenseDetailsModel.DoesNotExist:
                return Response(
                    {'error': f'License {license_number} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Update current owner if provided
            if current_owner_data and current_owner_data.get('iec'):
                owner_iec = current_owner_data.get('iec')

                # Try to find company by IEC
                try:
                    owner_company = CompanyModel.objects.get(iec=owner_iec)
                    license_obj.current_owner = owner_company
                    license_obj.save(update_fields=['current_owner'])
                except CompanyModel.DoesNotExist:
                    # Log but don't fail - we might want to create the company later
                    pass

            # Store transfer data in LicenseTransferModel
            transfers = data.get('transfers', [])
            transfers_created = 0

            if transfers:
                from datetime import datetime

                for transfer_data in transfers:
                    # Parse transfer_date if it's a string
                    transfer_date = transfer_data.get('transfer_date')
                    if transfer_date and isinstance(transfer_date, str):
                        try:
                            # Try parsing date format DD/MM/YYYY or YYYY-MM-DD
                            if '/' in transfer_date:
                                transfer_date = datetime.strptime(transfer_date, '%d/%m/%Y').date()
                            else:
                                transfer_date = datetime.strptime(transfer_date, '%Y-%m-%d').date()
                        except:
                            transfer_date = None

                    # Parse datetime fields
                    def parse_datetime(date_str):
                        if not date_str:
                            return None
                        try:
                            if 'T' in date_str:
                                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            return datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')
                        except:
                            return None

                    # Find or create from_company
                    from_company = None
                    from_iec = transfer_data.get('from_iec')
                    if from_iec:
                        from_company, _ = CompanyModel.objects.get_or_create(
                            iec=from_iec,
                            defaults={'name': transfer_data.get('from_iec_entity_name', from_iec)}
                        )

                    # Find or create to_company
                    to_company = None
                    to_iec = transfer_data.get('to_iec')
                    if to_iec:
                        to_company, _ = CompanyModel.objects.get_or_create(
                            iec=to_iec,
                            defaults={'name': transfer_data.get('to_iec_entity_name', to_iec)}
                        )

                    # Create or update transfer record
                    LicenseTransferModel.objects.update_or_create(
                        license=license_obj,
                        transfer_date=transfer_date,
                        from_company=from_company,
                        to_company=to_company,
                        defaults={
                            'transfer_status': transfer_data.get('transfer_status', ''),
                            'transfer_initiation_date': parse_datetime(transfer_data.get('transfer_initiation_date')),
                            'transfer_acceptance_date': parse_datetime(transfer_data.get('transfer_acceptance_date')),
                            'cbic_status': transfer_data.get('cbic_status'),
                            'cbic_response_date': parse_datetime(transfer_data.get('cbic_response_date')),
                            'user_id_transfer_initiation': transfer_data.get('user_id_transfer_initiation'),
                            'user_id_acceptance': transfer_data.get('user_id_acceptance'),
                        }
                    )
                    transfers_created += 1

            return Response({
                'success': True,
                'license_number': license_number,
                'current_owner_updated': current_owner_data is not None,
                'transfers_count': transfers_created
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to update license transfer: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='bulk-update-license-transfer', permission_classes=[AllowAny])
    def bulk_update_license_transfer(self, request):
        """
        Bulk update license ownership and transfer information for multiple licenses.

        Expected payload:
        {
            "licenses": [
                {
                    "license_number": "3010090273",
                    "license_date": "2024-01-15",
                    "exporter_iec": "0305000123",
                    "current_owner": {
                        "iec": "0305000456",
                        "name": "Company Name"
                    },
                    "transfers": [...]
                },
                ...
            ]
        }
        """
        try:
            licenses_data = request.data.get('licenses', [])

            if not licenses_data:
                return Response(
                    {'error': 'licenses array is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            success_count = 0
            failed_count = 0
            errors = []

            for license_data in licenses_data:
                try:
                    license_number = license_data.get('license_number')
                    current_owner_data = license_data.get('current_owner')

                    if not license_number:
                        errors.append(f"Missing license_number in payload")
                        failed_count += 1
                        continue

                    # Find the license
                    try:
                        license_obj = LicenseDetailsModel.objects.get(license_number=license_number)
                    except LicenseDetailsModel.DoesNotExist:
                        errors.append(f"License {license_number} not found")
                        failed_count += 1
                        continue

                    # Update current owner if provided
                    if current_owner_data and current_owner_data.get('iec'):
                        owner_iec = current_owner_data.get('iec')
                        owner_name = current_owner_data.get('name')

                        # Find or create company by IEC
                        owner_company, _ = CompanyModel.objects.get_or_create(
                            iec=owner_iec,
                            defaults={'name': owner_name or f"Company {owner_iec}"}
                        )
                        license_obj.current_owner = owner_company
                        license_obj.save(update_fields=['current_owner'])

                    # Store transfer data in LicenseTransferModel
                    transfers = license_data.get('transfers', [])

                    if transfers:
                        from datetime import datetime
                        from django.utils import timezone

                        for transfer_data in transfers:
                            # Parse transfer_date if it's a string
                            transfer_date = transfer_data.get('transfer_date')
                            if transfer_date and isinstance(transfer_date, str):
                                try:
                                    if '/' in transfer_date:
                                        transfer_date = datetime.strptime(transfer_date, '%d/%m/%Y').date()
                                    else:
                                        transfer_date = datetime.strptime(transfer_date, '%Y-%m-%d').date()
                                except:
                                    transfer_date = None

                            # Parse datetime fields
                            def parse_datetime(date_str):
                                if not date_str:
                                    return None
                                try:
                                    if 'T' in date_str:
                                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                    else:
                                        dt = datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')

                                    # Make timezone-aware if naive
                                    if timezone.is_naive(dt):
                                        dt = timezone.make_aware(dt)
                                    return dt
                                except:
                                    return None

                            # Find or create from_company
                            from_company = None
                            from_iec = transfer_data.get('from_iec')
                            if from_iec:
                                from_company, _ = CompanyModel.objects.get_or_create(
                                    iec=from_iec,
                                    defaults={'name': transfer_data.get('from_iec_entity_name', from_iec)}
                                )

                            # Find or create to_company
                            to_company = None
                            to_iec = transfer_data.get('to_iec')
                            if to_iec:
                                to_company, _ = CompanyModel.objects.get_or_create(
                                    iec=to_iec,
                                    defaults={'name': transfer_data.get('to_iec_entity_name', to_iec)}
                                )

                            # Use transfer_initiation_date as unique key
                            transfer_init_date = parse_datetime(transfer_data.get('transfer_initiation_date'))
                            if transfer_init_date:
                                LicenseTransferModel.objects.update_or_create(
                                    license=license_obj,
                                    transfer_initiation_date=transfer_init_date,
                                    defaults={
                                        'from_company': from_company,
                                        'to_company': to_company,
                                        'transfer_status': transfer_data.get('transfer_status', ''),
                                        'transfer_date': transfer_date,
                                        'transfer_acceptance_date': parse_datetime(transfer_data.get('transfer_acceptance_date')),
                                        'cbic_status': transfer_data.get('cbic_status'),
                                        'cbic_response_date': parse_datetime(transfer_data.get('cbic_response_date')),
                                        'user_id_transfer_initiation': transfer_data.get('user_id_transfer_initiation'),
                                        'user_id_acceptance': transfer_data.get('user_id_acceptance'),
                                    }
                                )

                    success_count += 1

                except Exception as e:
                    errors.append(f"License {license_data.get('license_number', 'unknown')}: {str(e)}")
                    failed_count += 1

            return Response({
                'success': success_count,
                'failed': failed_count,
                'total': len(licenses_data),
                'errors': errors
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to bulk update license transfers: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
