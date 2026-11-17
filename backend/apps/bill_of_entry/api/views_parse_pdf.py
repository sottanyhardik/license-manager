"""
Endpoint to parse an uploaded ICEGATE Bill of Entry PDF and return the
extracted fields, ready to prefill the Allotment form. Also returns hints
for matched company, port, and license items in the local database.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import BillOfEntryPermission, CompanyPermission
from apps.allotment.models import AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel
from apps.bill_of_entry.parsers.boe_pdf import parse_boe_pdf
from apps.bill_of_entry.services.boe_documents import validate_boe_pdf
from apps.core.models import CompanyModel, ExchangeRateModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel

logger = logging.getLogger(__name__)

_PARSE_FAILED_DETAIL = "Failed to parse PDF. Check that it is an ICEGATE Bill of Entry PDF."
_TRUTHY = frozenset({"true", "1", "yes", "on"})

# Why a requested company auto-create was skipped (additive response field).
SKIP_NOT_REQUESTED = "not_requested"
SKIP_NO_PERMISSION = "no_company_write_permission"
SKIP_MDS_MANAGED = "company_master_managed_by_mds"
SKIP_INCOMPLETE = "missing_iec_or_name"


def _decimal(value, default=None):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _match_port(port_code: str | None):
    if not port_code:
        return None
    return PortModel.objects.filter(code__iexact=port_code).first()


def _user_can_write_company(user) -> bool:
    """Same write role set CompanyViewSet enforces (CompanyPermission)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return user.has_any_role(CompanyPermission.required_roles_for_write)


def _company_mds_managed() -> bool:
    """True when the MDS write cutover owns CompanyModel writes.

    Mirrors ``MasterViewSet._mds_active``: MDS is the write authority then, so a
    local ORM create here would bypass it — the caller must skip creation."""
    from django.conf import settings

    if not getattr(settings, "MDS_ENABLED", False):
        return False
    try:
        from apps.core.mds_write import mds_active_for
    except Exception:  # noqa: BLE001 - mds_client not installed -> local behaviour
        return False
    return mds_active_for(CompanyModel)


def _company_create_skip_reason(user, requested: bool, iec: str, name: str) -> str | None:
    """Return why creation must be skipped, or None when it is allowed (D9)."""
    if not requested:
        return SKIP_NOT_REQUESTED
    if not (iec and name):
        return SKIP_INCOMPLETE
    if not _user_can_write_company(user):
        return SKIP_NO_PERMISSION
    if _company_mds_managed():
        return SKIP_MDS_MANAGED
    return None


def _match_or_create_company(parsed: dict[str, Any], create_if_missing: bool, user=None):
    """Match by IEC then name; create only when requested AND permitted (D9).

    Returns ``(company, created, skip_reason)``; ``skip_reason`` is None when a
    company was matched or created."""
    iec = (parsed.get("iec") or "").strip()
    name = (parsed.get("buyer_name") or "").strip()
    company = None

    if iec:
        company = CompanyModel.objects.filter(iec=iec).first()
    if not company and name:
        company = CompanyModel.objects.filter(name__iexact=name).first()
    if company:
        return company, False, None

    skip_reason = _company_create_skip_reason(user, create_if_missing, iec, name)
    if skip_reason:
        return None, False, skip_reason

    company = CompanyModel.objects.create(
        iec=iec,
        name=name,
        address_line_1=(parsed.get("buyer_address") or "").strip(),
    )
    return company, True, None


def _match_allotment_by_invoice(invoice_no: str | None):
    if not invoice_no:
        return None
    return (
        AllotmentModel.objects
        .filter(invoice__iexact=invoice_no.strip())
        .order_by("-id")
        .first()
    )


def _convert_to_usd_rate(parsed: dict[str, Any]) -> Decimal | None:
    """
    Return INR-per-USD rate for the BOE.

    If the BOE currency is already USD, use the rate on the BOE directly.
    Otherwise, look up the USD rate for the BOE date (or the latest available)
    in ExchangeRateModel.
    """
    currency = (parsed.get("currency") or "").upper()
    rate = _decimal(parsed.get("exchange_rate"))
    if currency == "USD" and rate and rate > 0:
        return rate
    # Find USD rate for the BOE date, else fall back to latest
    be_date = parsed.get("be_date")
    rate_row = None
    if be_date:
        rate_row = ExchangeRateModel.get_rate_for_date(be_date) \
            if hasattr(ExchangeRateModel, "get_rate_for_date") else None
    if rate_row is None and hasattr(ExchangeRateModel, "get_active_rate"):
        rate_row = ExchangeRateModel.get_active_rate()
    if rate_row and getattr(rate_row, "usd", None):
        return _decimal(rate_row.usd)
    return None


def _find_license(lic_no: str):
    """Find a license by number with progressive fallbacks for format variants."""
    if not lic_no:
        return None
    lic_no = lic_no.strip()
    # 1) exact
    lic = LicenseDetailsModel.objects.filter(license_number=lic_no).first()
    if lic:
        return lic
    # 2) case-insensitive (in case of trailing letters)
    lic = LicenseDetailsModel.objects.filter(license_number__iexact=lic_no).first()
    if lic:
        return lic
    # 3) without leading zeros, then with extra leading zero
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
    # 4) endswith (catches stored values with a prefix like "L-")
    if stripped:
        lic = LicenseDetailsModel.objects.filter(license_number__endswith=stripped).first()
        if lic:
            return lic
    # 5) digits-only (handles prefixed PDF values like "L-3411007518")
    import re as _re
    digits = _re.sub(r"\D", "", lic_no)
    if digits and digits != lic_no:
        lic = LicenseDetailsModel.objects.filter(license_number=digits).first()
        if lic:
            return lic
    return None


def _match_license_rows(parsed: dict[str, Any], usd_rate: Decimal | None):
    """
    For each licence row in the PDF, find the license first (with format
    fallbacks), then look up the serial number on that license. Returns a list
    of dicts with a match_status field so the UI can distinguish:
        matched          - both license and serial found
        license_only     - license found but serial number doesn't exist
        license_missing  - license number not found in DB
        no_data          - parser couldn't extract a license number
    """
    rows = []
    for lic in parsed.get("licences") or []:
        lic_no = (lic.get("licence_number") or "").strip()
        slno = lic.get("licence_slno")
        item = None
        license_obj = None
        status = "no_data"
        if lic_no:
            license_obj = _find_license(lic_no)
            if license_obj:
                if slno is not None:
                    item = LicenseImportItemsModel.objects.filter(
                        license=license_obj, serial_number=slno
                    ).first()
                    status = "matched" if item else "license_only"
                else:
                    status = "license_only"
            else:
                status = "license_missing"

        debit_inr = _decimal(lic.get("debit_value_inr"))
        qty = _decimal(lic.get("qty"))
        cif_fc = None
        if debit_inr is not None and usd_rate and usd_rate > 0:
            cif_fc = (debit_inr / usd_rate).quantize(Decimal("0.01"))

        rows.append({
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
            "match_status": status,
        })
    return rows


class BOEPdfParseView(APIView):
    """
    POST /api/bill-of-entries/parse-pdf/
        multipart-form: file=<BOE PDF>
        optional form: create_company=true|false (default false — D9; creation
        also requires CompanyPermission write roles and no MDS write cutover
        for CompanyModel, otherwise the unmatched company info is returned)

    Returns a JSON object suitable for prefilling AllotmentFormModal.
    """
    permission_classes = [IsAuthenticated, BillOfEntryPermission]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"detail": "No file uploaded. Send the PDF as multipart field 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_boe_pdf(upload)
        except DjangoValidationError as exc:
            return Response(
                {"detail": " ".join(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parsed = parse_boe_pdf(upload)
        except Exception:  # noqa: BLE001 - never echo parser internals (D9)
            logger.exception("BOE PDF parse failed for upload by user id=%s", request.user.pk)
            return Response(
                {"detail": _PARSE_FAILED_DETAIL},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not parsed.get("be_number"):
            return Response(
                {
                    "detail": "Could not detect a BOE number — this may not be an "
                              "ICEGATE Bill of Entry PDF, or the layout is unsupported.",
                    "parsed": parsed,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        create_company = str(request.data.get("create_company", "false")).strip().lower() in _TRUTHY
        company, company_created, company_skip_reason = _match_or_create_company(
            parsed, create_company, request.user,
        )
        port = _match_port(parsed.get("port_code"))
        allotment = _match_allotment_by_invoice(parsed.get("invoice_no"))
        # A BOE is unique by number and date.  Tell the create form about an
        # existing record before it submits, so it can open that record with
        # the parsed values still ready to review and save.
        existing_boe = BillOfEntryModel.objects.filter(
            bill_of_entry_number=parsed["be_number"],
            bill_of_entry_date=parsed.get("be_date"),
        ).order_by("id").first()

        usd_rate = _convert_to_usd_rate(parsed)
        licences = _match_license_rows(parsed, usd_rate)

        # Compute prefill values for the Allotment form
        cif_inr_total = sum(
            (_decimal(row["cif_inr"]) for row in licences if row.get("cif_inr") is not None),
            Decimal("0"),
        )
        qty_total = sum(
            (_decimal(row["qty"]) for row in licences if row.get("qty") is not None),
            Decimal("0"),
        )
        cif_fc_total = (cif_inr_total / usd_rate).quantize(Decimal("0.01")) \
            if usd_rate and usd_rate > 0 and cif_inr_total > 0 else None

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
            "estimated_arrival_date": None,
            "is_boe": True,
        }

        return Response({
            "parsed": parsed,
            "prefill": prefill,
            "matched_allotment_id": allotment.id if allotment else None,
            "existing_boe_id": existing_boe.id if existing_boe else None,
            "matched_company_id": company.id if company else None,
            "company_created": company_created,
            # Additive (D9): why no company was auto-created, plus the parsed
            # company details so the user can pick/create it explicitly.
            "company_creation_skipped_reason": company_skip_reason,
            "unmatched_company": None if company else {
                "iec": (parsed.get("iec") or "").strip() or None,
                "name": (parsed.get("buyer_name") or "").strip() or None,
                "address": (parsed.get("buyer_address") or "").strip() or None,
            },
            "matched_port_id": port.id if port else None,
            "licences": licences,
        })
