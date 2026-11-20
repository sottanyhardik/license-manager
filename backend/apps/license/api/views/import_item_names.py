"""Licence Detail -> Import Items: per-row Item Name correction (row override; owner decision 2026-11-20).

Thin HTTP wrappers over ``services/product_intelligence/import_item_override``, attached to ``LicenseDetailsViewSet``
with the same convention as ``add_license_overview_actions``. Reads use the viewset's read permission; writes need
LICENSE_MANAGER (``_can_approve``). Classification only: no quantity / CIF / balance is written."""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response


def add_import_item_name_actions(viewset_class):
    def _svc():
        from apps.license.services.product_intelligence import import_item_override
        return import_item_override

    def _deny(request):
        from apps.license.api.views.item_pivot_intelligence import _can_approve
        if _can_approve(request.user):
            return None
        return Response({"detail": "Changing an Item Name needs the LICENSE_MANAGER role."}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['get'], url_path='import-item-names')
    def import_item_names(self, request, pk=None):
        from apps.license.api.views.item_pivot_intelligence import _can_approve
        lic = self.get_object()
        return Response({"can_edit": _can_approve(request.user), "rows": _svc().rows_for_licence(lic.pk)})

    @action(detail=True, methods=['post'], url_path='import-item-names/save')
    def import_item_names_save(self, request, pk=None):
        from apps.license.services.product_matching import MatchValidationError
        lic = self.get_object()
        denied = _deny(request)
        if denied:
            return denied
        svc = _svc()
        data = request.data if isinstance(request.data, dict) else {}
        try:
            result = svc.save_changes(license_id=lic.pk, changes=data.get("changes"), user=request.user, reason=str(data.get("reason") or ""))
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (svc.OverrideConcurrencyError, svc.ia.ApprovalConcurrencyError) as exc:
            return Response({"detail": str(exc), "import_item_ids": exc.import_item_ids}, status=status.HTTP_409_CONFLICT)
        return Response({"saved": result["saved"], "unchanged": result["unchanged"], "mapping_change": result["mapping_change"],
                         "propagation": result["propagation"], "rows": svc.rows_for_licence(lic.pk)}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='import-item-names/preview')
    def import_item_names_preview(self, request, pk=None):
        from apps.license.services.product_matching import MatchValidationError
        lic = self.get_object()  # read permission only: nothing is written
        data = request.data if isinstance(request.data, dict) else {}
        try:
            previews = _svc().preview_changes(license_id=lic.pk, changes=data.get("changes"))
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"previews": previews})

    @action(detail=True, methods=['post'], url_path='import-item-names/revert')
    def import_item_names_revert(self, request, pk=None):
        from apps.license.services.product_matching import MatchValidationError
        lic = self.get_object()
        denied = _deny(request)
        if denied:
            return denied
        svc = _svc()
        data = request.data if isinstance(request.data, dict) else {}
        ids = data.get("import_item_ids")
        try:
            if not isinstance(ids, list):
                raise MatchValidationError("import_item_ids must be a list")
            result = svc.revert_overrides(license_id=lic.pk, import_item_ids=ids, user=request.user)
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"reverted": result["reverted"], "reapplied": result["reapplied"], "rows": svc.rows_for_licence(lic.pk)})

    @action(detail=True, methods=['get'], url_path=r'import-item-names/(?P<import_item_id>\d+)/history')
    def import_item_names_history(self, request, pk=None, import_item_id=None):
        from apps.license.models import LicenseImportItemsModel
        from rest_framework.exceptions import NotFound
        lic = self.get_object()
        if not LicenseImportItemsModel.objects.filter(pk=import_item_id, license_id=lic.pk).exists():
            raise NotFound("Import item not found.")
        return Response({"events": _svc().history(int(import_item_id), license_id=lic.pk)})

    for method in (import_item_names, import_item_names_save, import_item_names_preview, import_item_names_revert, import_item_names_history):
        setattr(viewset_class, method.__name__, method)
    return viewset_class
