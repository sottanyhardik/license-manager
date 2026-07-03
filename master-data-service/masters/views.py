"""
Generic master API.

`MasterViewSet` gives every master, for free:
- `?updated_since=<iso8601>` delta filtering (the sync driver)
- collection `ETag` + `If-None-Match` -> `304 Not Modified` (cheap refresh)
- `GET .../_meta` high-water-mark ({max_modified, count, etag})
- `POST .../bulk_upsert` keyed on the natural key (hydration + consolidation)
plus cursor pagination and scoped token auth from settings.
"""

import hashlib

from django.db.models import Count, Max
from django.utils.dateparse import parse_datetime
from django.utils.http import quote_etag
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Company, ExchangeRate, MasterChange, Port
from .serializers import (
    CompanySerializer,
    ExchangeRateSerializer,
    MasterChangeSerializer,
    PortSerializer,
)


class MasterViewSet(viewsets.ModelViewSet):
    """Base viewset for a single master model. Subclasses set queryset,
    serializer_class, and natural_key_field."""

    natural_key_field = None

    # -- delta filtering ----------------------------------------------------
    def get_queryset(self):
        qs = super().get_queryset()
        updated_since = self.request.query_params.get("updated_since")
        if updated_since:
            dt = parse_datetime(updated_since)
            if dt is not None:
                qs = qs.filter(modified_on__gt=dt)
        return qs

    # -- ETag / high-water mark --------------------------------------------
    def _meta_values(self):
        """(max_modified, count, etag) over the WHOLE model (not the delta)."""
        agg = self.queryset.model.objects.aggregate(m=Max("modified_on"), c=Count("id"))
        token = f"{agg['m']}-{agg['c']}"
        etag = quote_etag(hashlib.md5(token.encode()).hexdigest())
        return agg["m"], agg["c"], etag

    def list(self, request, *args, **kwargs):
        _, _, etag = self._meta_values()
        if request.headers.get("If-None-Match") == etag:
            return Response(status=status.HTTP_304_NOT_MODIFIED)
        resp = super().list(request, *args, **kwargs)
        resp["ETag"] = etag
        return resp

    @action(detail=False, methods=["get"], url_path="_meta")
    def meta(self, request):
        max_modified, count, etag = self._meta_values()
        return Response({"max_modified": max_modified, "count": count, "etag": etag})

    # -- bulk upsert by natural key ----------------------------------------
    @action(detail=False, methods=["post"], url_path="bulk_upsert")
    def bulk_upsert(self, request):
        field = self.natural_key_field
        payload = request.data
        items = payload if isinstance(payload, list) else payload.get("items", [])
        if not isinstance(items, list):
            return Response({"detail": "expected a list of records"}, status=status.HTTP_400_BAD_REQUEST)

        Model = self.queryset.model
        created = updated = 0
        for row in items:
            key = row.get(field)
            if key in (None, ""):
                return Response(
                    {"detail": f"each record needs a natural key '{field}'"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            existing = Model.objects.filter(**{field: key}).first()
            serializer = self.get_serializer(instance=existing, data=row, partial=bool(existing))
            serializer.is_valid(raise_exception=True)
            serializer.save()
            if existing:
                updated += 1
            else:
                created += 1
        return Response({"created": created, "updated": updated}, status=status.HTTP_200_OK)


class CompanyViewSet(MasterViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    natural_key_field = "iec"


class PortViewSet(MasterViewSet):
    queryset = Port.objects.all()
    serializer_class = PortSerializer
    natural_key_field = "code"


class ExchangeRateViewSet(MasterViewSet):
    queryset = ExchangeRate.objects.all()
    serializer_class = ExchangeRateSerializer
    natural_key_field = "date"


class MasterChangeViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only change feed. `?since=<iso8601>` returns changes after a cursor;
    consumers use it to apply deletes and trigger targeted refreshes."""

    queryset = MasterChange.objects.all()
    serializer_class = MasterChangeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        since = self.request.query_params.get("since")
        if since:
            dt = parse_datetime(since)
            if dt is not None:
                qs = qs.filter(at__gt=dt)
        return qs
