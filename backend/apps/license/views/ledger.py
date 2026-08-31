"""
License Ledger Views - Unified view for DFIA and Incentive license balances
"""
from django.http import FileResponse, Http404
from django.db.models import Q
import hashlib
from io import BytesIO
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from datetime import timedelta
import logging
import re
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LicenseLedgerViewPermission
from apps.license.models import LicenseDetailsModel, IncentiveLicense

logger = logging.getLogger(__name__)

class LicenseLedgerViewSet(viewsets.GenericViewSet):
    """
    Unified ledger view for both DFIA and Incentive licenses.
    Shows available balance for selling licenses.

    Access is role-based.  Ledger users can view the shared ledger regardless
    of whether their account has a company assignment.

    Returns:
    - DFIA licenses: balance_cif (available CIF $ balance)
    - Incentive licenses: balance_value (available INR balance)
    """
    permission_classes = [LicenseLedgerViewPermission]

    # Persistent Download Requests API.  This deliberately uses the original
    # durable job tables so requests accepted before this UI migration remain
    # visible and downloadable.
    @action(detail=False, methods=['get', 'post'], url_path='download-requests')
    def download_requests(self, request):
        from django.conf import settings
        from rest_framework.exceptions import ValidationError
        from apps.license.models import LicenseLedgerPackageJob, LicenseLedgerPackageItem, LicensePackageAuditEvent
        if request.method == 'POST':
            ids = request.data.get('license_ids') if isinstance(request.data, dict) else None
            if not isinstance(ids, list) or not ids:
                raise ValidationError({'license_ids': 'Select at least one licence.'})
            normalized = list(dict.fromkeys(str(v).strip() for v in ids if str(v).strip()))
            if not normalized or len(normalized) > getattr(settings, 'LICENSE_LEDGER_PACKAGE_MAX_LICENSES', 100):
                raise ValidationError({'license_ids': 'Select a valid number of licences.'})
            licences, seen = [], set()
            for value in normalized:
                kind, licence = self._authorized_license(request, value)
                if kind != 'DFIA': raise ValidationError({'license_ids': 'Only DFIA licences are supported.'})
                if licence.pk not in seen: licences.append(licence); seen.add(licence.pk)
            idem = (request.headers.get('Idempotency-Key') or request.data.get('idempotency_key') or '').strip()[:255]
            with transaction.atomic():
                existing = LicenseLedgerPackageJob.objects.select_for_update().filter(requested_by=request.user, idempotency_key=idem).first() if idem else None
                if existing: return Response(self._download_request_payload(existing), status=202)
                key = timezone.now().strftime('%Y%m%d-%H%M%S_') + get_random_string(8, allowed_chars='0123456789abcdef')
                job = LicenseLedgerPackageJob.objects.create(key=key, requested_by=request.user, idempotency_key=idem, requested_ids=[str(x.pk) for x in licences], requested_count=len(licences), queued_count=len(licences), expires_at=timezone.now() + timedelta(days=getattr(settings, 'LICENSE_LEDGER_PACKAGE_RETENTION_DAYS', 7)))
                LicenseLedgerPackageItem.objects.bulk_create([LicenseLedgerPackageItem(job=job, license=licence, licence_number=str(licence.license_number), request_order=index + 1) for index, licence in enumerate(licences)])
                LicensePackageAuditEvent.objects.create(request=job, actor=request.user, event='request_created', detail={'licence_count': len(licences)})
                transaction.on_commit(lambda: self._enqueue_download_request(job.pk))
            return Response(self._download_request_payload(job), status=202)
        query = LicenseLedgerPackageJob.objects.filter(requested_by=request.user).select_related('requested_by').order_by('-created_at')
        term = request.query_params.get('search', '').strip()
        if term: query = query.filter(Q(key__icontains=term) | Q(items__licence_number__icontains=term)).distinct()
        if request.query_params.get('status'): query = query.filter(status=request.query_params['status'])
        page_size, page = min(max(int(request.query_params.get('page_size', 20)), 1), 100), max(int(request.query_params.get('page', 1)), 1)
        total = query.count(); rows = list(query[(page-1)*page_size:page*page_size])
        return Response({'count': total, 'page': page, 'page_size': page_size, 'results': [self._download_request_payload(row) for row in rows]})

    @action(detail=False, methods=['get'], url_path=r'download-requests/(?P<request_id>[^/.]+)')
    def download_request_detail(self, request, request_id=None):
        return Response(self._download_request_payload(self._owned_download_request(request, request_id), detailed=True))

    @action(detail=False, methods=['get'], url_path=r'download-requests/(?P<request_id>[^/.]+)/items')
    def download_request_items(self, request, request_id=None):
        job = self._owned_download_request(request, request_id); query = job.items.select_related('license').order_by('request_order', 'pk')
        term = request.query_params.get('search', '').strip()
        if term: query = query.filter(licence_number__icontains=term)
        status = request.query_params.get('status', '').strip()
        if status == 'ready': query=query.filter(status='server_ready')
        elif status == 'processing': query=query.filter(status__in=['queued','generating','validating_sources','merging'])
        elif status == 'blocked': query=query.filter(status__startswith='blocked_')
        elif status: query=query.filter(status=status)
        page_size, page = min(max(int(request.query_params.get('page_size', 44)), 1), 100), max(int(request.query_params.get('page', 1)), 1); total=query.count(); rows=list(query[(page-1)*page_size:page*page_size])
        return Response({'count': total, 'results': [self._download_item_payload(job, row) for row in rows]})

    @action(detail=False, methods=['get'], url_path=r'download-requests/(?P<request_id>[^/.]+)/licenses/(?P<item_id>[^/.]+)/download')
    def download_request_item(self, request, request_id=None, item_id=None):
        from django.core.files.storage import default_storage
        job=self._owned_download_request(request, request_id); item=job.items.filter(pk=item_id, status='server_ready').first()
        if not item or not item.output_key or not default_storage.exists(item.output_key): raise Http404
        with default_storage.open(item.output_key, 'rb') as source: content=source.read()
        if len(content) != item.output_size or hashlib.sha256(content).hexdigest() != item.output_checksum: raise Http404
        return FileResponse(BytesIO(content), as_attachment=True, filename=f'{item.licence_number}.pdf', content_type='application/pdf')

    @action(detail=False, methods=['get'], url_path=r'download-requests/(?P<request_id>[^/.]+)/licenses/(?P<item_id>[^/.]+)/draft-download')
    def download_request_item_draft(self, request, request_id=None, item_id=None):
        """Authenticated ledger-only draft; never changes verified item state."""
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.services.license_ledger_package import LicenseLedgerPackageService
        job = self._owned_download_request(request, request_id)
        item = job.items.select_related('license').filter(pk=item_id, status__startswith='blocked_').first()
        if not item: raise Http404
        pdf = LicenseLedgerPackageService.build_ledger_only_draft(
            dataset=CanonicalLedgerService.build_canonical_ledger_dataset(item.license_id, 'DFIA'), requested_by=request.user,
        )
        return FileResponse(BytesIO(pdf), as_attachment=True, filename=f'{item.licence_number}-ledger-only-draft.pdf', content_type='application/pdf')

    @action(detail=False, methods=['get'], url_path=r'download-requests/(?P<request_id>[^/.]+)/download-zip')
    def download_request_zip(self, request, request_id=None):
        return self.package_archive_download(request, self._owned_download_request(request, request_id).key)

    @action(detail=False, methods=['post'], url_path=r'download-requests/(?P<request_id>[^/.]+)/retry')
    def download_request_retry(self, request, request_id=None):
        from apps.license.models import LicenseLedgerPackageItem
        from apps.license.services.ledger_package_recovery import licence_readiness
        job=self._owned_download_request(request, request_id)
        # A retry never bypasses missing evidence. It only requeues blockers
        # whose authoritative readiness has become true since the last run.
        requeued = []
        for item in job.items.select_related('license').filter(status__startswith='blocked_'):
            readiness = licence_readiness(item.license)
            if readiness['status'] == 'READY':
                item.status, item.error, item.completed_at = 'queued', '', None
                item.save(update_fields=['status', 'error', 'completed_at'])
                requeued.append(item.pk)
            else:
                item.error = __import__('json').dumps(readiness, sort_keys=True)
                item.save(update_fields=['error'])
        if requeued:
            transaction.on_commit(lambda: self._enqueue_download_request(job.pk))
        return self.package_retry(request, job.key)

    @action(detail=False, methods=['post'], url_path=r'download-requests/(?P<request_id>[^/.]+)/reconcile')
    def download_request_reconcile(self, request, request_id=None):
        job=self._owned_download_request(request, request_id); self._enqueue_download_request(job.pk); return Response(self._download_request_payload(job), status=202)

    def _owned_download_request(self, request, request_id):
        from apps.license.models import LicenseLedgerPackageJob
        job=LicenseLedgerPackageJob.objects.filter(requested_by=request.user).filter(Q(public_id=str(request_id))|Q(key=str(request_id))).first()
        if not job: raise Http404
        return job

    @staticmethod
    def _enqueue_download_request(pk):
        try:
            from apps.license.tasks import enqueue_license_ledger_package_job
            result=enqueue_license_ledger_package_job.delay(pk)
            LicenseLedgerPackageJob.objects.filter(pk=pk).update(root_task_id=result.id)
        except Exception:
            LicenseLedgerPackageJob.objects.filter(pk=pk).update(status='dispatch_failed', error='Dispatch failed; retry is available.')
            logger.exception('Could not publish download request %s', pk)

    def _download_item_payload(self, job, item):
        import json
        manifest=item.section_manifest or {}; counts=manifest.get('document_counts', {})
        try: blocker=json.loads(item.error) if item.error else {}
        except (TypeError, ValueError): blocker={}
        remarks=[]
        if blocker.get('missing_purchase_trade_ids'):
            from apps.trade.models import LicenseTrade
            purchases = LicenseTrade.objects.filter(pk__in=blocker['missing_purchase_trade_ids']).select_related('from_company', 'to_company').order_by('pk')
            labels = [
                '%s%s (Trade %s)' % (
                    '%s → %s' % (getattr(trade.from_company, 'name', '') or 'Unknown supplier', getattr(trade.to_company, 'name', '') or 'Unknown purchaser'),
                    (' — ' + trade.invoice_number) if trade.invoice_number else '', trade.pk,
                ) for trade in purchases
            ]
            remarks.append('Missing purchase document: ' + (', '.join(labels) or 'trade(s) ' + ', '.join(map(str, blocker['missing_purchase_trade_ids']))))
        if blocker.get('unknown_sale_ids'): remarks.append('Unknown sales classification: sale(s) ' + ', '.join(map(str, blocker['unknown_sale_ids'])))
        if blocker.get('missing_final_sale_ids'): remarks.append('Missing final-party invoice: sale(s) ' + ', '.join(map(str, blocker['missing_final_sale_ids'])))
        return {'id': item.pk, 'licence_number': item.licence_number, 'license_id': item.license_id, 'status': item.status, 'purchase_expected_count': int(item.purchase_expected_count or counts.get('expected_purchase_invoices', 0) or 0), 'purchase_included_count': int(item.purchase_included_count or counts.get('included_purchase_invoices', 0) or 0), 'sales_expected_count': int(item.sales_expected_count or counts.get('expected_final_party_sales_invoices', 0) or 0), 'sales_included_count': int(item.sales_included_count or counts.get('included_final_party_sales_invoices', 0) or 0), 'interlinked_sales_excluded_count': int(item.interlinked_sales_excluded_count or counts.get('excluded_interlinked_sales_invoices', 0) or 0), 'page_count': int(item.output_page_count or 0), 'size': int(item.output_size or 0), 'updated_at': item.completed_at or item.started_at, 'error': item.error or None, 'remarks': remarks, 'blocking_reason_codes': item.blocking_reason_codes or [], 'download_url': f'/api/license-ledger/download-requests/{job.public_id}/licenses/{item.pk}/download/' if item.status == 'server_ready' else None, 'draft_download_url': f'/api/license-ledger/download-requests/{job.public_id}/licenses/{item.pk}/draft-download/' if item.status == 'blocked_missing_purchase_document' else None}

    def _download_request_payload(self, job, detailed=False):
        items=list(job.items.all()); total=len(items); ready=sum(i.status=='server_ready' for i in items); blocked=sum(i.status.startswith('blocked_') for i in items); failed=sum(i.status=='failed' for i in items); processing=max(0,total-ready-blocked-failed)
        payload={'id':str(job.public_id), 'request_key':str(job.public_id).split('-')[0], 'status':job.status, 'requested_count':int(total), 'queued_count':sum(i.status=='queued' for i in items), 'processing_count':processing, 'server_ready_count':ready, 'blocked_count':blocked, 'failed_count':failed, 'created_at':job.created_at, 'started_at':job.started_at, 'completed_at':job.completed_at, 'created_by':getattr(job.requested_by,'get_full_name',lambda: '')() or getattr(job.requested_by,'username',''), 'zip_ready':bool(job.status=='server_ready' and job.archive_key), 'zip_download_url':f'/api/license-ledger/download-requests/{job.public_id}/download-zip/' if job.status=='server_ready' and job.archive_key else None}
        if detailed: payload['items']=[self._download_item_payload(job, item) for item in items]
        return payload

    @action(detail=False, methods=['post'], url_path='download-package')
    def download_package(self, request):
        """Accept a durable package job; rendering is always worker-side."""
        from django.conf import settings
        from rest_framework.exceptions import ValidationError
        from apps.license.models import LicenseLedgerPackageJob, LicenseLedgerPackageItem

        license_ids = request.data.get('license_ids') if isinstance(request.data, dict) else None
        if not isinstance(license_ids, list) or not license_ids:
            raise ValidationError({'license_ids': 'Select at least one licence.'})
        limit = getattr(settings, 'LICENSE_LEDGER_PACKAGE_MAX_LICENSES', 100)
        # Preserve input business order but make duplicate clicks/IDs one work item.
        normalized_ids = list(dict.fromkeys(str(value).strip() for value in license_ids if str(value).strip()))
        if not normalized_ids or len(normalized_ids) > limit:
            raise ValidationError({'license_ids': f'Select between 1 and {limit} licences.'})
        resolved = []
        resolved_primary_keys = set()
        for license_id in normalized_ids:
            found_type, license_obj = self._authorized_license(request, str(license_id))
            if found_type != 'DFIA':
                raise ValidationError({'license_ids': 'Package generation currently supports DFIA licences only.'})
            # A primary key and licence number can identify the same row.  It
            # is still exactly one requested licence/job item.
            if license_obj.pk not in resolved_primary_keys:
                resolved_primary_keys.add(license_obj.pk)
                resolved.append(license_obj)
        idem = (request.headers.get('Idempotency-Key') or request.data.get('idempotency_key') or '').strip()[:255]
        with transaction.atomic():
            if idem:
                existing = (LicenseLedgerPackageJob.objects.select_for_update()
                            .filter(requested_by=request.user, idempotency_key=idem)
                            .exclude(status=LicenseLedgerPackageJob.STATUS_FAILED).order_by('-created_at').first())
                if existing:
                    return Response(self._package_job_payload(existing), status=202)
            # The browser creates its writable subdirectory before this POST.
            # Accept only the same opaque, timestamped key shape so that the
            # server job and visible local folder can be audited together.
            client_key = str(request.data.get('client_job_key') or '').strip()
            if client_key and not re.fullmatch(r'\d{8}T\d{6}Z_[0-9a-f]{8}', client_key):
                raise ValidationError({'client_job_key': 'Invalid package job key.'})
            key = client_key or timezone.now().strftime('%Y%m%d-%H%M%S_') + get_random_string(8, allowed_chars='0123456789abcdef')
            job = LicenseLedgerPackageJob.objects.create(
                key=key, requested_by=request.user, idempotency_key=idem,
                requested_ids=[str(licence.pk) for licence in resolved],
                expires_at=timezone.now() + timedelta(days=getattr(settings, 'LICENSE_LEDGER_PACKAGE_RETENTION_DAYS', 7)),
            )
            LicenseLedgerPackageItem.objects.bulk_create([
                LicenseLedgerPackageItem(job=job, license=licence, licence_number=str(licence.license_number))
                for licence in resolved
            ])
            transaction.on_commit(lambda: self._enqueue_package_job(job.pk))
        return Response(self._package_job_payload(job), status=202)

    @action(detail=False, methods=['get'], url_path=r'download-package/(?P<job_id>[^/.]+)')
    def package_status(self, request, job_id=None):
        return Response(self._package_job_payload(self._owned_package_job(request, job_id), detailed=True))

    @action(detail=False, methods=['get'], url_path=r'download-package/(?P<job_id>[^/.]+)/licences/(?P<item_id>[^/.]+)/download')
    def package_item_download(self, request, job_id=None, item_id=None):
        from django.core.files.storage import default_storage
        job = self._owned_package_job(request, job_id)
        item = job.items.filter(pk=item_id, status='server_ready').first()
        if not item or not item.output_key or not default_storage.exists(item.output_key):
            raise Http404
        filename = f'{item.licence_number}.pdf'
        return FileResponse(default_storage.open(item.output_key, 'rb'), as_attachment=True,
                            filename=filename, content_type='application/pdf')

    @action(detail=False, methods=['get'], url_path=r'download-package/(?P<job_id>[^/.]+)/download')
    def package_archive_download(self, request, job_id=None):
        from django.core.files.storage import default_storage
        job = self._owned_package_job(request, job_id)
        if job.status != 'server_ready' or not job.archive_key or not default_storage.exists(job.archive_key):
            raise Http404
        return FileResponse(default_storage.open(job.archive_key, 'rb'), as_attachment=True,
                            filename=f'license-ledger-package-{job.key}.zip', content_type='application/zip')

    @action(detail=False, methods=['post'], url_path=r'download-package/(?P<job_id>[^/.]+)/retry')
    def package_retry(self, request, job_id=None):
        from apps.license.models import LicenseLedgerPackageItem
        job = self._owned_package_job(request, job_id)
        failed = list(job.items.filter(status=LicenseLedgerPackageItem.STATUS_FAILED).values_list('pk', flat=True))
        if failed:
            LicenseLedgerPackageItem.objects.filter(pk__in=failed).update(status='queued', error='', started_at=None, completed_at=None)
            job.status, job.error, job.completed_at = 'queued', '', None
            job.save(update_fields=['status', 'error', 'completed_at', 'updated_at'])
            transaction.on_commit(lambda: self._enqueue_package_job(job.pk, failed))
        return Response(self._package_job_payload(job), status=202)

    @action(detail=False, methods=['get'], url_path=r'download-package/(?P<job_id>[^/.]+)/readiness')
    def package_readiness(self, request, job_id=None):
        """Safe, owner-scoped readiness data for the review screen."""
        from apps.license.services.ledger_package_recovery import licence_readiness, readiness_tabs
        job = self._owned_package_job(request, job_id)
        tabs = readiness_tabs(job)
        base = f'/api/license-ledger/download-package/{job.key}/readiness'
        return Response({'job_id': job.key, 'licences': [
            {'item_id': item.pk, 'licence_id': item.license_id, 'licence_number': item.licence_number,
             **licence_readiness(item.license)} for item in job.items.select_related('license').order_by('pk')
        ], 'tabs': tabs, 'csv_urls': {
            'missing_purchase_documents': base + '/missing-purchase-documents.csv',
            'orphan_recovery_review': base + '/orphan-recovery-review.csv',
            'unknown_sales_classification': base + '/unknown-sales-classification.csv',
            'licence_readiness': base + '/licence-readiness.csv',
        }})

    @action(detail=False, methods=['get'], url_path=r'download-package/(?P<job_id>[^/.]+)/readiness/(?P<report>[^/]+)')
    def package_readiness_csv(self, request, job_id=None, report=None):
        """CSV exports intentionally contain review fields, never storage keys."""
        import csv
        from django.http import HttpResponse
        from apps.license.services.ledger_package_recovery import licence_readiness, readiness_tabs
        job = self._owned_package_job(request, job_id)
        tabs = readiness_tabs(job)
        reports = {
            'missing-purchase-documents.csv': tabs['missing_purchase_documents'],
            'orphan-recovery-review.csv': tabs['orphan_recovery_candidates'],
            'unknown-sales-classification.csv': tabs['unknown_sales_classifications'],
            'licence-readiness.csv': [dict(licence_id=i.license_id, licence_number=i.licence_number, **licence_readiness(i.license)) for i in job.items.select_related('license').order_by('pk')],
        }
        rows = reports.get(report)
        if rows is None:
            raise Http404
        # A header remains useful for empty review exports.
        headers = {
            'missing-purchase-documents.csv': ['licence_id', 'licence_number', 'trade_id', 'supplier', 'purchase_invoice_number', 'invoice_date', 'invoice_amount', 'expected_document', 'current_status'],
            'orphan-recovery-review.csv': ['source_checksum', 'invoice_number', 'supplier', 'invoice_date', 'invoice_amount', 'candidate_trade_id', 'matching_rule', 'status'],
            'unknown-sales-classification.csv': ['sale_id', 'licence_id', 'licence_number', 'invoice_number', 'seller', 'buyer', 'branch_path', 'decision', 'reason'],
            'licence-readiness.csv': ['licence_id', 'licence_number', 'status', 'missing_purchase_trade_ids', 'unknown_sale_ids', 'missing_final_sale_ids'],
        }[report]
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{report}"'
        writer = csv.DictWriter(response, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
        return response

    @action(detail=False, methods=['post'], url_path=r'download-package/(?P<job_id>[^/.]+)/purchase-trades/(?P<trade_id>[^/.]+)/upload')
    def package_purchase_upload(self, request, job_id=None, trade_id=None):
        from rest_framework.exceptions import ValidationError
        from apps.license.services.ledger_package_recovery import upload_purchase_document
        from apps.trade.models import LicenseTrade
        job = self._owned_package_job(request, job_id)
        upload = request.FILES.get('file')
        if not upload:
            raise ValidationError({'file': 'A supplier invoice PDF or image is required.'})
        trade = LicenseTrade.objects.filter(pk=trade_id, direction=LicenseTrade.DIR_PURCHASE).first()
        if not trade or not trade.lines.filter(sr_number__license__ledger_package_items__job=job).exists():
            raise Http404
        content = upload.read()
        try:
            trade = upload_purchase_document(trade_id=int(trade_id), content=content,
                                             filename=upload.name, user=request.user)
        except (ValueError, LicenseTrade.DoesNotExist) as exc:
            raise ValidationError({'file': str(exc)})
        return Response({'trade_id': trade.pk, 'status': 'uploaded'})

    @action(detail=False, methods=['post'], url_path=r'download-package/(?P<job_id>[^/.]+)/purchase-trades/(?P<trade_id>[^/.]+)/recover-orphan')
    def package_recover_orphan(self, request, job_id=None, trade_id=None):
        """Attach an existing storage object only with exact review evidence."""
        from rest_framework.exceptions import ValidationError
        from django.core.files.storage import default_storage
        from apps.trade.models import LicenseTrade
        from apps.license.services.ledger_package_recovery import link_unique_orphan
        job = self._owned_package_job(request, job_id)
        trade = LicenseTrade.objects.filter(pk=trade_id, direction=LicenseTrade.DIR_PURCHASE).first()
        if not trade or not trade.lines.filter(sr_number__license__ledger_package_items__job=job).exists():
            raise Http404
        key, evidence = str(request.data.get('source_storage_key') or ''), request.data.get('evidence')
        if not key or not isinstance(evidence, dict) or not default_storage.exists(key):
            raise ValidationError({'source_storage_key': 'An existing candidate and exact evidence are required.'})
        with default_storage.open(key, 'rb') as candidate:
            content = candidate.read()
        try:
            link_unique_orphan(trade_id=trade.pk, source_key=key, source_bytes=content,
                               evidence=evidence, user=request.user)
        except ValueError as exc:
            raise ValidationError({'source_storage_key': str(exc)})
        return Response({'trade_id': trade.pk, 'status': 'recovered'})

    def _owned_package_job(self, request, key):
        from apps.license.models import LicenseLedgerPackageJob
        job = LicenseLedgerPackageJob.objects.prefetch_related('items').filter(key=key, requested_by=request.user).first()
        if not job:
            raise Http404
        return job

    @staticmethod
    def _enqueue_package_job(job_pk, item_ids=None):
        # Import lazily so the HTTP process does not require worker-only PDF imports.
        try:
            from apps.license.tasks import enqueue_license_ledger_package_job
            enqueue_license_ledger_package_job.delay(job_pk, item_ids)
        except Exception:
            # The committed job remains queued and is recoverable by the
            # worker/periodic dispatcher; never roll back a valid acceptance
            # because the broker briefly cannot be reached.
            logger.exception("Could not publish ledger package job %s", job_pk)

    @staticmethod
    def _package_job_payload(job, detailed=False):
        items = list(job.items.all()) if hasattr(job, 'items') else []
        states = ('queued', 'generating', 'validating_sources', 'merging', 'server_ready', 'failed')
        counts = {state: sum(1 for item in items if item.status == state) for state in states}
        total = len(items)
        payload = {
            'job_id': job.key, 'status': job.status, 'total': total, **counts,
            'percentage': int((counts['server_ready'] + counts['failed']) * 100 / total) if total else 0,
            'started_at': job.started_at, 'completed_at': job.completed_at,
            'status_url': f'/api/license-ledger/download-package/{job.key}/',
            'download_url': f'/api/license-ledger/download-package/{job.key}/download/' if job.status == 'server_ready' else None,
        }
        if detailed:
            payload['licences'] = [{
                # Do not expose output_key: it is an internal storage address,
                # not an authorization capability.  The URL below remains
                # owner-scoped through package_item_download.
                'id': item.license_id, 'license_id': item.license_id,
                'licence_number': item.licence_number, 'status': item.status,
                'document_counts': item.section_manifest.get('document_counts', {}) if item.section_manifest else {},
                'error': item.error or None,
                'completed_at': item.completed_at,
                'filename': f'{item.licence_number}.pdf' if item.status == 'server_ready' else None,
                'size': item.output_size if item.status == 'server_ready' else None,
                'sha256': item.output_checksum if item.status == 'server_ready' else None,
                'download_url': f'/api/license-ledger/download-package/{job.key}/licences/{item.pk}/download/' if item.status == 'server_ready' else None,
            } for item in items]
        return payload

    @action(detail=False, methods=['post'], url_path='download-package-pdf')
    def download_package_pdf(self, request):
        """Download all selected package documents merged into one PDF."""
        from rest_framework.exceptions import ValidationError
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.services.license_ledger_package import LicenseLedgerPackageService
        license_ids = request.data.get('license_ids') if isinstance(request.data, dict) else None
        if not isinstance(license_ids, list) or len(license_ids) != 1:
            raise ValidationError({'license_ids': 'Select exactly one licence for a canonical PDF package.'})
        datasets, licence_numbers = [], []
        for license_id in license_ids:
            found_type, license_obj = self._authorized_license(request, str(license_id))
            datasets.append(CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id, found_type))
            licence_numbers.append(str(license_obj.license_number))
        output = LicenseLedgerPackageService.build_merged_pdf(datasets=datasets, requested_by=request.user, base_url=request.build_absolute_uri('/'))
        filename = f'{licence_numbers[0]}.pdf'
        response = FileResponse(output, as_attachment=True, filename=filename, content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename=\"{filename}\"; filename*=UTF-8''{filename}"
        return response

    @action(detail=True, methods=['get'], url_path='custom-ledger-pdf')
    def custom_ledger_pdf(self, request, pk=None):
        """Download the same Customs Ledger — Item Detail matrix used in a package."""
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.services.custom_ledger_pdf import get_custom_ledger_data, render_custom_ledger_pdf
        found_type, license_obj = self._authorized_license(request, pk, request.query_params.get('license_type', 'DFIA'))
        if found_type != 'DFIA':
            return Response({'error': 'Customs item detail is available for DFIA licences only.'}, status=400)
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id, found_type)
        pdf = render_custom_ledger_pdf(get_custom_ledger_data(license_obj, request.user, canonical_dataset=dataset))
        filename = f'{license_obj.license_number}.pdf'
        response = FileResponse(BytesIO(pdf), as_attachment=True, filename=filename, content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename=\"{filename}\"; filename*=UTF-8''{filename}"
        return response

    @action(detail=True, methods=['get'], url_path='financial-ledger-pdf')
    def financial_ledger_pdf(self, request, pk=None):
        """Download the canonical native financial-ledger PDF for one licence."""
        from apps.license.services.license_ledger_export import generate_license_ledger_statement_pdf
        found_type, license_obj = self._authorized_license(request, pk, request.query_params.get('license_type', 'AUTO'))
        pdf = generate_license_ledger_statement_pdf(
            query_params=request.query_params,
            user=request.user,
            base_url=request.build_absolute_uri("/"),
            license_ref=(license_obj.id, found_type),
        )
        filename = f'{license_obj.license_number}.pdf'
        response = FileResponse(pdf, as_attachment=True, filename=filename, content_type='application/pdf')
        response['Content-Disposition'] = f"attachment; filename=\"{filename}\"; filename*=UTF-8''{filename}"
        return response

    def list(self, request):
        """Preserve the router's established collection endpoint."""
        return self.license_wise(request)

    def retrieve(self, request, pk=None):
        """Preserve the router's established per-license endpoint."""
        return self.ledger_detail(request, pk=pk)

    def _authorized_license(self, request, license_ref, license_type='AUTO'):
        """Resolve a license for an already-authorized ledger user."""
        from rest_framework.exceptions import APIException, ValidationError

        requested_type = str(license_type or 'AUTO').strip().upper()
        allowed_types = {'AUTO', 'DFIA', 'INCENTIVE', 'ALL_INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS'}
        if requested_type not in allowed_types:
            raise ValidationError({'license_type': f"Invalid license type '{license_type}'."})

        if requested_type == 'DFIA':
            found_type, license_obj = self._find_license_by_id_or_number(license_ref, True, False)
        elif requested_type in {'INCENTIVE', 'ALL_INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS'}:
            found_type, license_obj = self._find_license_by_id_or_number(license_ref, False, True)
        else:
            found_type, license_obj = self._find_license_by_id_or_number(license_ref, True, True)
        if (license_obj and requested_type in {'RODTEP', 'ROSTL', 'MEIS'}
                and found_type != requested_type):
            license_obj = None
        if not license_obj:
            class LicenseNotFound(APIException):
                status_code = 404
                default_code = 'not_found'
            raise LicenseNotFound(detail={'error': f'License not found: {license_ref}'})

        return found_type, license_obj

    def _find_license_by_id_or_number(self, pk, search_dfia=True, search_incentive=True):
        """
        Helper method to find license in DFIA and/or Incentive tables by ID or license_number.

        Args:
            pk: License ID (int) or license_number (str)
            search_dfia: Whether to search in DFIA licenses
            search_incentive: Whether to search in Incentive licenses

        Returns:
            Tuple of (license_type, license_object) or (None, None) if not found
        """
        # Search DFIA if requested
        if search_dfia:
            try:
                if pk.isdigit() and not pk.startswith('0'):
                    try:
                        license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(pk=int(pk))
                        return ('DFIA', license)
                    except LicenseDetailsModel.DoesNotExist:
                        license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(license_number=pk)
                        return ('DFIA', license)
                else:
                    try:
                        license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(license_number=pk)
                        return ('DFIA', license)
                    except LicenseDetailsModel.DoesNotExist:
                        try:
                            license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(pk=int(pk))
                            return ('DFIA', license)
                        except (ValueError, TypeError, LicenseDetailsModel.DoesNotExist):
                            pass
            except LicenseDetailsModel.DoesNotExist:
                pass

        # Search Incentive if requested
        if search_incentive:
            try:
                if pk.isdigit() and not pk.startswith('0'):
                    try:
                        license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(pk=int(pk))
                        return (license.license_type, license)
                    except IncentiveLicense.DoesNotExist:
                        license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(license_number=pk)
                        return (license.license_type, license)
                else:
                    try:
                        license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(license_number=pk)
                        return (license.license_type, license)
                    except IncentiveLicense.DoesNotExist:
                        try:
                            license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(pk=int(pk))
                            return (license.license_type, license)
                        except (ValueError, TypeError, IncentiveLicense.DoesNotExist):
                            pass
            except IncentiveLicense.DoesNotExist:
                pass

        return (None, None)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get canonical summary statistics for every authorized ledger licence.
        """
        from apps.license.services.license_ledger_export import build_license_ledger_data
        return Response(build_license_ledger_data(
            request.query_params,
        )['summary'])

    @action(detail=True, methods=['get'])
    def ledger_detail(self, request, pk=None):
        """
        Get detailed ledger view for a specific license showing all transactions.
        Works for both DFIA and Incentive licenses.
        Accepts either ID (integer) or license_number (string) as pk parameter.
        Auto-searches both tables if license_type not specified.

        **Phase 4C:** API consumes CanonicalLedgerService as the single source of truth.
        All financial calculations are performed by CanonicalLedgerService; the API layer
        is a transparent serialization layer with no business logic.
        """
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.serializers import CanonicalLedgerSerializer
        from rest_framework.exceptions import ValidationError
        license_type = request.query_params.get('license_type', 'AUTO')
        company_value = request.query_params.get('company')
        try:
            company_id = int(company_value) if company_value else None
        except (TypeError, ValueError):
            raise ValidationError({'company': 'Company must be a valid numeric ID.'})
        found_type, license = self._authorized_license(request, pk, license_type)

        # Delegate all calculation to CanonicalLedgerService (single source of truth).
        # The API is a transparent serialization layer with NO business logic.
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=license.id,
            license_type=found_type,
            company_id=company_id,
        )

        from apps.license.services.license_ledger_export import enrich_invoice_documents
        enrich_invoice_documents(
            {"licenses": [dataset]}, user=request.user,
            base_url=request.build_absolute_uri("/"),
        )

        # Serialize for response (representation only; no calculations)
        serializer = CanonicalLedgerSerializer(dataset)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='license-wise')
    def license_wise(self, request):
        """
        Returns trades grouped by license, then by company within each license.
        Structure: license → [company → purchases/sales/totals]

        The collection is role-authorized and accepts the public ledger filters.
        """
        from apps.license.services.license_ledger_export import build_license_ledger_data
        collection = build_license_ledger_data(
            request.query_params,
        )
        datasets = collection['licenses']
        return Response({'licenses': [{
            'license_id': data['license_id'],
            'license_number': data['license_number'],
            'license_date': data['license_date'],
            'expiry_date': data.get('expiry_date'),
            'license_type': data['license_type'],
            'sion_norms': data.get('sion_norms') or '',
            # Flat, transaction-level rows for the screen ledger.  Keep the
            # established company summary alongside it for older consumers.
            'transactions': data.get('display_transactions') or [],
            'summary': data.get('summary') or {},
            'individual_ledger_projection': data.get('individual_ledger_projection') or {},
            'companies': data['license_wise_companies'],
        } for data in datasets],
            # Canonical reporting hierarchy. The UI consumes this verbatim;
            # the flat license-wise shape remains for detail compatibility.
            'company_groups': collection['company_groups'],
            'grand_total': collection['grand_total'],
        })

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """Render PDF or Excel from the same canonical datasets used by the UI."""
        from apps.license.services.license_ledger_export import (
            build_license_ledger_data,
            generate_license_ledger_statement_pdf,
            render_license_ledger,
        )

        file_format = request.query_params.get('file_format', '').lower()
        if file_format not in {'pdf', 'xlsx'}:
            return Response({'error': "format must be 'pdf' or 'xlsx'"}, status=400)

        license_ref = None
        requested_license = request.query_params.get('license_id')
        if requested_license:
            found_type, license_obj = self._authorized_license(
                request,
                requested_license,
                request.query_params.get('license_type', 'AUTO'),
            )
            license_ref = (license_obj.id, found_type)

        canonical_data = build_license_ledger_data(
            request.query_params, license_ref=license_ref,
        )
        datasets = canonical_data['licenses']
        if not datasets:
            return Response({'error': 'No License Ledger data available for export.'}, status=404)

        output = (
            generate_license_ledger_statement_pdf(
                user=request.user,
                base_url=request.build_absolute_uri("/"),
                canonical_data=canonical_data,
            )
            if file_format == 'pdf'
            else render_license_ledger(canonical_data, file_format)
        )
        if len(datasets) == 1:
            slug = f"license-ledger-{datasets[0]['license_id']}"
            item_id = request.query_params.get('item_id')
            if item_id:
                slug += f"-{item_id}"
        else:
            slug = 'license-ledger'
        content_type = 'application/pdf' if file_format == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response = FileResponse(output, as_attachment=file_format == 'xlsx', filename=f'{slug}.{file_format}', content_type=content_type)
        if file_format == 'pdf':
            response['Content-Disposition'] = f'inline; filename="{slug}.pdf"'
        return response
