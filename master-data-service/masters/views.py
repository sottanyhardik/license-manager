"""
Generic master API.

`MasterViewSet` gives every master, for free:
- `?updated_since=<iso8601>` delta filtering (the sync driver)
- collection `ETag` + `If-None-Match` -> `304 Not Modified` (cheap refresh)
- `GET .../_meta` high-water-mark ({max_modified, count, etag})
- `POST .../bulk_upsert` keyed on the natural key (hydration + consolidation)
plus cursor pagination and scoped token auth from settings.

Concrete viewsets for all 17 masters are generated from MASTER_REGISTRY.
"""

import hashlib

from django.db.models import Count, Max
from django.utils.dateparse import parse_datetime
from django.utils.http import quote_etag
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import MASTER_REGISTRY, MasterChange
from .pagination import ChangeFeedCursorPagination
from .serializers import SERIALIZERS, MasterChangeSerializer


class MasterViewSet(viewsets.ModelViewSet):
    """Base viewset for a single master model. Subclasses set queryset,
    serializer_class, and natural_key_field."""

    natural_key_field = None

    def get_queryset(self):
        qs = super().get_queryset()
        updated_since = self.request.query_params.get("updated_since")
        if updated_since:
            dt = parse_datetime(updated_since)
            if dt is not None:
                qs = qs.filter(modified_on__gt=dt)
        return qs

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

    @action(detail=False, methods=["post"], url_path="delete_by_key")
    def delete_by_key(self, request):
        """Delete the row identified by its NATURAL KEY (ids diverge across
        servers, so consumers can only address a row by its business key —
        ADR-001 Decision 2). Deleting via the ORM fires the ``post_delete``
        signal, which appends a ``MasterChange`` delete so the change feed
        carries the deletion to every other mirror.

        Body: ``{"<natural_key_field>": <value>}`` (or ``{"key": <value>}``).
        Returns 200 ``{"deleted": <n>}``. Idempotent: deleting an absent key is
        a no-op success (``deleted == 0``) so a retried delete never 404s.
        """
        field = self.natural_key_field
        payload = request.data if isinstance(request.data, dict) else {}
        key = payload.get(field, payload.get("key"))
        if key in (None, ""):
            return Response(
                {"detail": f"a natural key '{field}' (or 'key') is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        Model = self.queryset.model
        deleted = 0
        # Delete instances one-by-one so post_delete fires per row (QuerySet
        # .delete() would emit the MasterChange, but iterating keeps the natural
        # key available and is trivial volume for a single-key delete).
        for obj in Model.objects.filter(**{field: key}):
            obj.delete()
            deleted += 1
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)

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


def _make_viewset(model, natural_key):
    return type(
        f"{model.__name__}ViewSet",
        (MasterViewSet,),
        {
            "queryset": model.objects.all(),
            "serializer_class": SERIALIZERS[model],
            "natural_key_field": natural_key,
        },
    )


# (viewset_class, url_endpoint, basename) for every master.
MASTER_VIEWSETS = [
    (_make_viewset(model, natural_key), endpoint, model.__name__.lower())
    for model, natural_key, endpoint in MASTER_REGISTRY
]


class MasterChangeViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only change feed. `?since=<iso8601>` returns changes after a cursor;
    consumers use it to apply deletes and trigger targeted refreshes."""

    queryset = MasterChange.objects.all()
    serializer_class = MasterChangeSerializer
    pagination_class = ChangeFeedCursorPagination

    def get_queryset(self):
        qs = super().get_queryset()
        since = self.request.query_params.get("since")
        if since:
            dt = parse_datetime(since)
            if dt is not None:
                qs = qs.filter(at__gt=dt)
        return qs
