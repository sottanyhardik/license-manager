# bill_of_entry/views/boe.py
"""
BillOfEntryViewSet — CRUD for BOE records plus domain-specific actions:

  GET    /bill-of-entries/                            — list (paginated, filtered)
  POST   /bill-of-entries/                            — create
  GET    /bill-of-entries/{id}/                       — retrieve
  PATCH  /bill-of-entries/{id}/                       — partial update
  DELETE /bill-of-entries/{id}/                       — destroy

  GET    /bill-of-entries/{id}/rows/                  — list rows
  POST   /bill-of-entries/{id}/rows/                  — add row
  PATCH  /bill-of-entries/{id}/rows/{row_id}/         — update row
  DELETE /bill-of-entries/{id}/rows/{row_id}/         — delete row

  POST   /bill-of-entries/{id}/rows/{row_id}/resolve-dispute/  — link dispute row
  POST   /bill-of-entries/{id}/resolve-dispute/               — clear all disputes

  POST   /bill-of-entries/parse-pdf/                 — parse BOE PDF, return prefill data
  GET    /bill-of-entries/fetch-allotment-details/   — allotment item prefill
  POST   /bill-of-entries/{id}/generate-transfer-letter/      — generate TL (501 stub)
  POST   /bill-of-entries/{id}/merge/                — merge source BOE into this one
  POST   /bill-of-entries/{id}/update-invoice-no/    — update invoice_no (ACCOUNT_ACCESS)
"""
from __future__ import annotations

import logging

from decimal import Decimal, InvalidOperation

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.permissions import (
    AccountAccessPermission,
    BillOfEntryPermission,
    TransferLetterPermission,
)
from apps.bill_of_entry import services
from apps.bill_of_entry.filters import BillOfEntryFilter
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.bill_of_entry.serializers import BillOfEntrySerializer, RowDetailsSerializer

logger = logging.getLogger(__name__)


class BillOfEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [BillOfEntryPermission]
    serializer_class = BillOfEntrySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = BillOfEntryFilter
    search_fields = [
        "bill_of_entry_number",
        "invoice_no",
        "product_name",
        "company__name",
        "port__name",
    ]
    ordering_fields = [
        "bill_of_entry_date",
        "bill_of_entry_number",
        "company__name",
    ]
    ordering = ["-bill_of_entry_date"]

    def get_permissions(self):
        if self.action == "generate_transfer_letter":
            return [TransferLetterPermission()]
        if self.action == "update_invoice_no":
            return [AccountAccessPermission()]
        return super().get_permissions()

    def get_queryset(self):
        return (
            BillOfEntryModel.objects.select_related("company", "port")
            .prefetch_related(
                "item_details",
                "item_details__sr_number",
                "item_details__sr_number__license",
                "item_details__sr_number__hs_code",
                "item_details__sr_number__license__purchase_status",
                "allotment",
            )
            .order_by("-bill_of_entry_date")
        )

    # ---------------------------------------------------------------------------
    # Row sub-resource actions
    # ---------------------------------------------------------------------------

    @action(detail=True, methods=["get", "post"], url_path="rows")
    def rows(self, request, pk=None):
        """
        GET  /bill-of-entries/{pk}/rows/  — list all rows for a BOE
        POST /bill-of-entries/{pk}/rows/  — add a new row to a BOE
        """
        boe = self.get_object()

        if request.method == "GET":
            rows_qs = RowDetails.objects.filter(bill_of_entry=boe).select_related(
                "sr_number",
                "sr_number__license",
                "sr_number__hs_code",
                "sr_number__license__purchase_status",
            )
            serializer = RowDetailsSerializer(rows_qs, many=True)
            return Response(serializer.data)

        # POST — create a new row
        from django.db import IntegrityError

        serializer = RowDetailsSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save(
                    bill_of_entry=boe,
                    created_by=request.user,
                    modified_by=request.user,
                )
            except IntegrityError:
                return Response(
                    {"detail": "A row with this sr_number and transaction_type already exists for this BOE."},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"rows/(?P<row_id>[^/.]+)",
    )
    def row_detail(self, request, pk=None, row_id=None):
        """
        PATCH  /bill-of-entries/{pk}/rows/{row_id}/  — update a row
        DELETE /bill-of-entries/{pk}/rows/{row_id}/  — delete a row

        Returns HTTP 403 when the row is frozen.
        """
        if request.method == "PATCH":
            try:
                row = services.update_row_detail(
                    row_id=int(row_id),
                    data=request.data,
                    user=request.user,
                    boe_id=int(pk),
                )
            except ValueError as exc:
                if "frozen" in str(exc).lower():
                    return Response(
                        {"detail": "This row is frozen and cannot be modified."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            serializer = RowDetailsSerializer(row)
            return Response(serializer.data)

        # DELETE
        try:
            services.delete_row_detail(row_id=int(row_id), user=request.user, boe_id=int(pk))
        except ValueError as exc:
            if "frozen" in str(exc).lower():
                return Response(
                    {"detail": "This row is frozen and cannot be modified."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"rows/(?P<row_id>[^/.]+)/resolve-dispute",
    )
    def resolve_dispute(self, request, pk=None, row_id=None):
        """
        POST /bill-of-entries/{pk}/rows/{row_id}/resolve-dispute/
        Link a specific dispute row to a LicenseImportItemsModel; clears is_dispute.
        Body: {"license_item_id": <int>}
        """
        license_item_id = request.data.get("license_item_id")
        if not license_item_id:
            return Response(
                {"detail": "license_item_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            row = services.resolve_dispute_row(
                row_id=int(row_id),
                license_item_id=int(license_item_id),
                user=request.user,
                boe_id=int(pk),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = RowDetailsSerializer(row)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="resolve-dispute")
    def resolve_boe_dispute(self, request, pk=None):
        """
        POST /bill-of-entries/{pk}/resolve-dispute/
        Clear is_dispute on ALL rows of a BOE.
        """
        boe = self.get_object()
        result = services.resolve_dispute(boe)
        return Response(result)

    # ---------------------------------------------------------------------------
    # BOE PDF parse — prefill the create form from an uploaded ICEGATE PDF
    # ---------------------------------------------------------------------------

    @action(
        detail=False,
        methods=["post"],
        url_path="parse-pdf",
        parser_classes=[MultiPartParser, FormParser],
    )
    def parse_pdf(self, request):
        """
        POST /bill-of-entries/parse-pdf/
        Parse an uploaded ICEGATE BOE PDF and return extracted fields for
        prefilling the BOE create form.

        Multipart form field: file=<BOE PDF>
        Optional form field:  create_company=true|false  (default: true)

        Returns extracted fields including be_number, be_date, port/company
        hints, and a licences list matched against the local database.
        """
        from apps.bill_of_entry.parsers.boe_pdf import parse_boe_pdf

        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"detail": "No file uploaded. Send the PDF as multipart field 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parsed = parse_boe_pdf(upload)
        except Exception as exc:
            return Response(
                {"detail": f"Failed to parse PDF: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not parsed.get("be_number"):
            return Response(
                {
                    "detail": (
                        "Could not detect a BOE number — this may not be an "
                        "ICEGATE Bill of Entry PDF, or the layout is unsupported."
                    ),
                    "parsed": parsed,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        def _decimal(value, default=None):
            if value in (None, ""):
                return default
            try:
                return Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                return default

        # Match port
        port = None
        port_code = parsed.get("port_code")
        if port_code:
            from apps.core.models import PortModel
            port = PortModel.objects.filter(code__iexact=port_code).first()

        # Match or create company
        company = None
        company_created = False
        create_company = str(request.data.get("create_company", "true")).lower() != "false"
        iec = (parsed.get("iec") or "").strip()
        buyer_name = (parsed.get("buyer_name") or "").strip()
        if iec or buyer_name:
            from apps.core.models import CompanyModel
            if iec:
                company = CompanyModel.objects.filter(iec=iec).first()
            if not company and buyer_name:
                company = CompanyModel.objects.filter(name__iexact=buyer_name).first()
            if not company and create_company and iec and buyer_name:
                company = CompanyModel.objects.create(
                    iec=iec,
                    name=buyer_name,
                    address_line_1=(parsed.get("buyer_address") or "").strip(),
                )
                company_created = True

        # Match allotment by invoice number
        allotment = None
        invoice_no = parsed.get("invoice_no")
        if invoice_no:
            from apps.allotment.models import AllotmentModel
            allotment = (
                AllotmentModel.objects
                .filter(invoice__iexact=invoice_no.strip())
                .order_by("-id")
                .first()
            )

        # Determine USD exchange rate
        usd_rate = None
        currency = (parsed.get("currency") or "").upper()
        rate_val = _decimal(parsed.get("exchange_rate"))
        if currency == "USD" and rate_val and rate_val > 0:
            usd_rate = rate_val
        else:
            from apps.core.models import ExchangeRateModel
            be_date = parsed.get("be_date")
            rate_row = None
            if be_date and hasattr(ExchangeRateModel, "get_rate_for_date"):
                rate_row = ExchangeRateModel.get_rate_for_date(be_date)
            if rate_row is None and hasattr(ExchangeRateModel, "get_active_rate"):
                rate_row = ExchangeRateModel.get_active_rate()
            if rate_row and getattr(rate_row, "usd", None):
                usd_rate = _decimal(rate_row.usd)

        # Match license rows from the parsed PDF
        from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel

        def _find_license(lic_no):
            import re as _re
            if not lic_no:
                return None
            lic_no = lic_no.strip()
            lic = LicenseDetailsModel.objects.filter(license_number=lic_no).first()
            if lic:
                return lic
            lic = LicenseDetailsModel.objects.filter(license_number__iexact=lic_no).first()
            if lic:
                return lic
            stripped = lic_no.lstrip("0")
            if stripped and stripped != lic_no:
                lic = LicenseDetailsModel.objects.filter(license_number=stripped).first()
                if lic:
                    return lic
            padded = lic_no.zfill(10)
            if padded != lic_no:
                lic = LicenseDetailsModel.objects.filter(license_number=padded).first()
                if lic:
                    return lic
            if stripped:
                lic = LicenseDetailsModel.objects.filter(
                    license_number__endswith=stripped
                ).first()
                if lic:
                    return lic
            digits = _re.sub(r"\D", "", lic_no)
            if digits and digits != lic_no:
                lic = LicenseDetailsModel.objects.filter(license_number=digits).first()
                if lic:
                    return lic
            return None

        licences = []
        for lic in parsed.get("licences") or []:
            lic_no = (lic.get("licence_number") or "").strip()
            slno = lic.get("licence_slno")
            item = None
            license_obj = None
            match_status = "no_data"
            if lic_no:
                license_obj = _find_license(lic_no)
                if license_obj:
                    if slno is not None:
                        item = LicenseImportItemsModel.objects.filter(
                            license=license_obj, serial_number=slno
                        ).first()
                        match_status = "matched" if item else "license_only"
                    else:
                        match_status = "license_only"
                else:
                    match_status = "license_missing"

            debit_inr = _decimal(lic.get("debit_value_inr"))
            qty = _decimal(lic.get("qty"))
            cif_fc = None
            if debit_inr is not None and usd_rate and usd_rate > 0:
                cif_fc = (debit_inr / usd_rate).quantize(Decimal("0.01"))

            licences.append({
                "licence_number": lic_no or None,
                "licence_slno": slno,
                "licence_date": lic.get("licence_date"),
                "uqc": lic.get("uqc"),
                "qty": str(qty) if qty is not None else None,
                "cif_inr": str(debit_inr) if debit_inr is not None else None,
                "cif_fc": str(cif_fc) if cif_fc is not None else None,
                "matched_license_id": license_obj.id if license_obj else None,
                "matched_license_number": license_obj.license_number if license_obj else None,
                "matched_item_id": item.id if item else None,
                "matched_item_description": item.description if item else None,
                "match_status": match_status,
            })

        # Compute totals for prefill
        cif_inr_total = sum(
            (_decimal(row["cif_inr"]) for row in licences if row.get("cif_inr") is not None),
            Decimal("0"),
        )
        qty_total = sum(
            (_decimal(row["qty"]) for row in licences if row.get("qty") is not None),
            Decimal("0"),
        )
        cif_fc_total = (
            (cif_inr_total / usd_rate).quantize(Decimal("0.01"))
            if usd_rate and usd_rate > 0 and cif_inr_total > 0
            else None
        )

        prefill = {
            "company_id": company.id if company else None,
            "company_name": company.name if company else parsed.get("buyer_name"),
            "company_created": company_created,
            "port_id": port.id if port else None,
            "port_code": parsed.get("port_code"),
            "invoice": parsed.get("invoice_no"),
            "exchange_rate": str(usd_rate) if usd_rate else None,
            "item_name": parsed.get("item_description"),
            "required_quantity": str(qty_total) if qty_total else None,
            "cif_inr": str(cif_inr_total) if cif_inr_total else None,
            "cif_fc": str(cif_fc_total) if cif_fc_total else None,
            "is_boe": True,
        }

        return Response({
            "parsed": parsed,
            "prefill": prefill,
            "matched_allotment_id": allotment.id if allotment else None,
            "matched_company_id": company.id if company else None,
            "company_created": company_created,
            "matched_port_id": port.id if port else None,
            "licences": licences,
        })

    # ---------------------------------------------------------------------------
    # Fetch allotment details — pre-fill BOE row form from an existing allotment
    # ---------------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="fetch-allotment-details")
    def fetch_allotment_details(self, request):
        """
        GET /bill-of-entries/fetch-allotment-details/?allotment_id=X[&boe_id=Y]
        Fetch allotment items for the given allotment_id. Used to pre-fill the
        BOE row form. Items already present in boe_id (if given) are excluded to
        prevent duplicates when pulling from multiple allotments.
        """
        allotment_id = request.query_params.get("allotment_id")
        boe_id = request.query_params.get("boe_id")

        if not allotment_id:
            return Response({"error": "allotment_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = services.fetch_allotment_item_details(
                allotment_id=allotment_id,
                boe_id=boe_id or None,
            )
            return Response(data)
        except Exception as exc:
            logger.exception("fetch_allotment_details failed for allotment %s: %s", allotment_id, exc)
            return Response(
                {"error": "Failed to fetch allotment details"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ---------------------------------------------------------------------------
    # Generate Transfer Letter — returns 501 until utility is ported
    # ---------------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="generate-transfer-letter")
    def generate_transfer_letter(self, request, pk=None):
        """
        POST /bill-of-entries/{id}/generate-transfer-letter/
        Generate transfer letter for BOE using generic utility.

        Request body:
          company_name: str (optional, falls back to BOE company)
          address_line1: str
          address_line2: str
          template_id: int
          cif_edits: dict[str, float]  — boe_item_id -> edited CIF FC

        Returns 501 when the transfer letter utility is not yet available in
        this backend. Use the legacy system until the utility is ported.
        """
        from django.shortcuts import get_object_or_404

        boe = get_object_or_404(BillOfEntryModel.objects.select_related("company"), id=pk)
        try:
            from apps.core.utils.transfer_letter import generate_transfer_letter_generic

            return generate_transfer_letter_generic(boe, request, instance_type="boe")
        except ImportError:
            return Response(
                {
                    "error": (
                        "Transfer letter generation is not yet available in this backend. "
                        "Use the legacy system for this operation."
                    )
                },
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        except Exception as exc:
            logger.exception("generate_transfer_letter failed for BOE %s: %s", pk, exc)
            return Response(
                {"error": "Transfer letter generation failed; check server logs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ---------------------------------------------------------------------------
    # Merge — merge a source BOE into this (target) BOE
    # ---------------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="merge")
    def merge(self, request, pk=None):
        """
        POST /bill-of-entries/{id}/merge/
        Merge a source BOE into this (target) BOE.

        - Moves RowDetails from source to target (skips duplicate sr_number+transaction_type)
        - Transfers allotments from source to target
        - Updates target's port to source's port when target has none
        - Deletes source BOE (atomic transaction)

        Request body: {"source_boe_id": <int>}
        """
        target_boe = self.get_object()
        source_boe_id = request.data.get("source_boe_id")

        try:
            result = services.merge_boe(target_boe, source_boe_id=source_boe_id)
        except ValueError as exc:
            msg = str(exc)
            if "not found" in msg:
                return Response({"error": msg}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result)

    # ---------------------------------------------------------------------------
    # Update invoice number — accessible to ACCOUNT_ACCESS + BOE_MANAGER roles
    # ---------------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="update-invoice-no")
    def update_invoice_no(self, request, pk=None):
        """
        POST /bill-of-entries/{id}/update-invoice-no/
        Update only the invoice_no field on a BOE.
        Accessible to ACCOUNT_ACCESS role (accounts team) and BOE_MANAGER.
        Payload: {"invoice_no": "INV-12345"}
        """
        from django.shortcuts import get_object_or_404

        boe = get_object_or_404(BillOfEntryModel, pk=pk)
        result = services.update_invoice_no(boe, invoice_no=request.data.get("invoice_no", ""))
        return Response(result)
