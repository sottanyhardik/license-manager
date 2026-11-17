"""Shared API plumbing: permission, error mapping, parameter parsing, Decimal-safe JSON."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import EntityBooks, FinancialYear
from apps.accounting.services import AccountingError
from apps.accounts.permissions import AccountingPermission


def jsonable(value):
    """Money is always serialised as a Decimal string (never float)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if is_dataclass(value):
        return jsonable(asdict(value))
    return value


def ok(data, code=status.HTTP_200_OK) -> Response:
    return Response(jsonable(data), status=code)


class AccountingView(APIView):
    permission_classes = [AccountingPermission]
    write_level = "write"

    def handle_exception(self, exc):
        if isinstance(exc, AccountingError):
            return Response({"detail": str(exc), "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)
        if isinstance(exc, ProtectedError):
            return Response({"detail": str(exc.args[0]), "code": "protected"}, status=status.HTTP_400_BAD_REQUEST)
        if isinstance(exc, ObjectDoesNotExist):
            return Response({"detail": "Not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        return super().handle_exception(exc)


class ApproverView(AccountingView):
    write_level = "approve"


def param(request, name: str, default=None, required: bool = False):
    value = request.data.get(name) if request.method not in ("GET", "HEAD") and hasattr(request.data, "get") else None
    if value in (None, ""):
        value = request.query_params.get(name, default)
    if required and value in (None, ""):
        raise ValidationError({name: "This field is required."})
    return value


def as_date(value, name: str = "date", default: date | None = None) -> date:
    if value in (None, ""):
        if default is None:
            raise ValidationError({name: "A date is required (YYYY-MM-DD)."})
        return default
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    raise ValidationError({name: "Use YYYY-MM-DD or DD-MM-YYYY."})


def as_money(value, name: str = "amount", default: str | None = None) -> Decimal:
    if value in (None, ""):
        if default is None:
            raise ValidationError({name: "An amount is required."})
        value = default
    if isinstance(value, float):
        value = repr(value)
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValidationError({name: "Invalid amount."}) from exc


def as_int(value, name: str):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "An integer id is required."}) from exc


def entity_from(request, name: str = "entity") -> EntityBooks:
    """Entity ids are the existing company ids (EntityBooks pk = CompanyModel pk)."""
    entity_id = as_int(param(request, name, required=True), name)
    return EntityBooks.objects.select_related("company").get(pk=entity_id)


def period_from(request, entity: EntityBooks) -> tuple[date, date, date]:
    """(start, end, fy_start) from ?fy=2026-27 or ?start/&end (defaults: current FY)."""
    from apps.accounting.services.books import fy_bounds
    fy_label = param(request, "fy")
    if fy_label:
        fy = FinancialYear.objects.get(entity=entity, label=fy_label)
        return fy.start_date, fy.end_date, fy.start_date
    today = timezone.localdate()
    _l, fy_start, fy_end = fy_bounds(as_date(param(request, "end"), "end", today))
    start = as_date(param(request, "start"), "start", fy_start)
    end = as_date(param(request, "end"), "end", fy_end)
    if start > end:
        raise ValidationError({"start": "start must be on or before end."})
    return start, end, fy_bounds(start)[1]


def page(request, items, present=lambda x: x, default_size: int = 50) -> dict:
    """Page a list or queryset (sliced in SQL) in StandardPagination's shape."""
    size = min(max(as_int(request.query_params.get("page_size", default_size), "page_size"), 1), 500)
    number = max(as_int(request.query_params.get("page", 1), "page"), 1)
    total = len(items) if isinstance(items, list) else items.count()
    start = (number - 1) * size
    return {"count": total, "page": number, "page_size": size,
            "next": number + 1 if start + size < total else None, "previous": number - 1 if number > 1 else None,
            "results": [present(x) for x in items[start:start + size]]}
