"""Suggest the item for an import line's product description, using the same C969 rules as save."""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.services.c969_product_classifier import (
    NO_DESCRIPTION,
    UNRECOGNISED,
    C969_NORM,
    classify_c969_category,
)


class ImportItemSuggestionView(APIView):
    """POST {description, norm_class_ids} -> {items: [{id, name}]} (at most one item).

    Only C969 has product-name rules here; other norms return no suggestion, so their
    behaviour is unchanged. Blank, deleted, and unrecognised descriptions return no item.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        description = str(request.data.get("description") or "").strip()
        norm_ids = [int(i) for i in (request.data.get("norm_class_ids") or []) if str(i).isdigit()]
        norms = set(SionNormClassModel.objects.filter(pk__in=norm_ids).values_list("norm_class", flat=True))
        if C969_NORM not in norms:
            return Response({"items": []})
        category = classify_c969_category(description)
        if category in (NO_DESCRIPTION, UNRECOGNISED):
            return Response({"items": []})
        item = ItemNameModel.objects.filter(
            name__iexact=category, sion_norm_class__norm_class=C969_NORM,
        ).first()
        if item is None:
            return Response({"items": []})
        return Response({"items": [{"id": item.id, "name": item.name}]})
