# bill_of_entry/views/boe.py
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.accounts.permissions import BillOfEntryPermission
from apps.bill_of_entry import services
from apps.bill_of_entry.filters import BillOfEntryFilter
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.bill_of_entry.serializers import BillOfEntrySerializer, RowDetailsSerializer


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
