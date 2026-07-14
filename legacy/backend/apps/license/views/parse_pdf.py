"""
Endpoint to parse an uploaded DFIA licence PDF and return the extracted
fields, ready to prefill the License create/update form. Also returns hints
for matched/created company, matched port, and import-item rows.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import LicensePermission
from apps.core.models import (
    CompanyModel,
    HSCodeModel,
    NotificationNumber,
    PortModel,
    SchemeCode,
)
from apps.license.models import LicenseDetailsModel
from apps.license.parsers.dfia_pdf import parse_dfia_pdf


# DFIA licences historically all had scheme code "26" (≈99% of existing rows).
# The parser doesn't read scheme_code from the PDF text — there's no consistent
# header for it — so we default to "26" so the form's Scheme Code dropdown
# arrives pre-selected the way it used to before this column became an FK.
DFIA_DEFAULT_SCHEME_CODE = "26"


def _decimal(value, default=None):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _match_or_create_company(parsed: dict[str, Any], create_if_missing: bool):
    iec = (parsed.get("iec") or "").strip()
    name = (parsed.get("company_name") or "").strip()
    company = None
    created = False

    if iec:
        company = CompanyModel.objects.filter(iec=iec).first()
    if not company and name:
        company = CompanyModel.objects.filter(name__iexact=name).first()

    if not company and create_if_missing and iec and name:
        company = CompanyModel.objects.create(
            iec=iec,
            name=name,
            address_line_1=(parsed.get("company_address") or "").strip(),
        )
        created = True

    return company, created


def _match_port(port_code: str | None):
    if not port_code:
        return None
    return PortModel.objects.filter(code__iexact=port_code.strip()).first()


def _match_hs_code(hsn: str | None):
    if not hsn:
        return None
    return HSCodeModel.objects.filter(hs_code=hsn.strip()).first()


def _resolve_notification_number(code: str | None):
    """Look up a NotificationNumber row by code, creating one if the PDF
    contains a new notification value we haven't seen before.

    Before the CharField→FK conversion the form took whatever string the PDF
    yielded; now we need an integer FK to populate the Select. Auto-creating
    keeps that behaviour transparent to the user — they get to see the
    parsed notification number preselected in the dropdown either way.
    """
    if not code:
        return None
    code = code.strip()
    if not code:
        return None
    obj, _ = NotificationNumber.objects.get_or_create(
        code=code, defaults={"label": code}
    )
    return obj


def _resolve_scheme_code(code: str | None):
    """Look up a SchemeCode row by code. The DFIA parser does not extract a
    scheme code from the PDF, so callers pass `DFIA_DEFAULT_SCHEME_CODE`."""
    if not code:
        return None
    return SchemeCode.objects.filter(code=code.strip()).first()


def _annotate_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach matched HS-code IDs to the parsed item rows."""
    out = []
    for item in items:
        hs = _match_hs_code(item.get("hsn"))
        out.append({
            **item,
            "matched_hs_code_id": hs.id if hs else None,
        })
    return out


class LicensePdfParseView(APIView):
    """
    POST /api/licenses/parse-pdf/
        multipart-form: file=<DFIA Licence PDF>
        optional form:  create_company=true|false (default true)

    Returns parsed fields plus a `prefill` block suitable for prefilling the
    License create/update form on the frontend.
    """
    permission_classes = [IsAuthenticated, LicensePermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"detail": "No file uploaded. Send the PDF as multipart field 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parsed = parse_dfia_pdf(upload)
        except Exception as exc:
            return Response(
                {"detail": f"Failed to parse PDF: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not parsed.get("license_number"):
            return Response(
                {
                    "detail": "Could not detect a licence number — this may not be a "
                              "DGFT DFIA licence PDF, or the layout is unsupported.",
                    "parsed": parsed,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Check for duplicate before creating any company side-effects.
        existing = LicenseDetailsModel.objects.filter(
            license_number=parsed["license_number"]
        ).only("id", "license_number").first()

        create_company = str(request.data.get("create_company", "true")).lower() != "false"
        company, company_created = _match_or_create_company(parsed, create_company)
        port = _match_port(parsed.get("port_code"))
        notification = _resolve_notification_number(parsed.get("notification_number"))
        scheme = _resolve_scheme_code(DFIA_DEFAULT_SCHEME_CODE)

        items = _annotate_items(parsed.get("items") or [])

        # Auto-calculate registration_number (license_number with any
        # leading zero stripped) to match the form's existing autofill rule.
        reg_number = None
        lic_no = parsed.get("license_number") or ""
        if lic_no:
            reg_number = lic_no[1:] if lic_no.startswith("0") else lic_no

        prefill = {
            "license_number": parsed.get("license_number"),
            "license_date": parsed.get("license_date"),
            "license_expiry_date": parsed.get("license_expiry_date"),
            "file_number": parsed.get("file_number"),
            "registration_number": reg_number,
            "registration_date": parsed.get("license_date"),
            # scheme_code / notification_number on the License serializer are
            # SlugRelatedField(slug_field="code"), so the form expects the
            # CODE string ("26", "025/2023") — not the PK. Pass the code
            # straight through; AsyncSelectField resolves the label via the
            # masters detail endpoint, whose lookup_field is also "code".
            "notification_number": notification.code if notification else None,
            "scheme_code": scheme.code if scheme else None,
            "exporter": company.id if company else None,
            "port": port.id if port else None,
            "condition_sheet": parsed.get("condition_sheet"),
        }

        return Response({
            "parsed": parsed,
            "prefill": prefill,
            "item_conditions": parsed.get("item_conditions") or [],
            "matched_company_id": company.id if company else None,
            "matched_company_name": company.name if company else parsed.get("company_name"),
            "company_created": company_created,
            "matched_port_id": port.id if port else None,
            "matched_port_code": parsed.get("port_code"),
            "items": items,
            "existing_license_id": existing.id if existing else None,
        })
