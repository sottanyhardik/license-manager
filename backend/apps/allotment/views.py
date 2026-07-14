# allotment/views.py
"""
AllotmentViewSet — DRF ModelViewSet.

No ORM lives here. All mutations are delegated to the service layer
(apps.allotment.services.allotment_service). The view is responsible only for
auth/permission, serialization, filtering, and HTTP responses.
"""
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.accounts.permissions import AllotmentPermission
from apps.allotment.filters import AllotmentFilter
from apps.allotment.models import AllotmentModel
from apps.allotment.serializers import AllotmentSerializer
from apps.allotment.services.allotment_service import (
    create_allotment,
    update_allotment,
    delete_allotment,
)


class AllotmentViewSet(viewsets.ModelViewSet):
    """
    CRUD endpoints for AllotmentModel.

    Mutations (create/update/destroy) are handled by the service layer so
    business logic and side effects (Celery task dispatch) stay out of the view.
    """

    serializer_class = AllotmentSerializer
    permission_classes = [AllotmentPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AllotmentFilter
    search_fields = ["item_name", "company__name", "invoice", "bl_detail"]
    ordering_fields = ["estimated_arrival_date", "modified_on", "company__name", "item_name"]
    ordering = ["-estimated_arrival_date"]

    def get_queryset(self):
        return (
            AllotmentModel.objects
            .select_related("company", "port", "related_company")
            .prefetch_related(
                "allotment_details",
                "allotment_details__item",
                "allotment_details__item__license",
            )
            .order_by("-estimated_arrival_date")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allotment = create_allotment(dict(serializer.validated_data), request.user)
        out = AllotmentSerializer(allotment, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        allotment = update_allotment(
            instance.pk, dict(serializer.validated_data), request.user
        )
        out = AllotmentSerializer(allotment, context={"request": request})
        return Response(out.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        delete_allotment(instance.pk, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="generate-pdf")
    def generate_pdf(self, request, pk=None):
        """
        Async PDF generation — dispatch Celery task and return task_id.

        The task import is intentionally lazy; if apps.allotment.tasks is not
        yet available the endpoint degrades gracefully and still returns 202.
        """
        instance = self.get_object()
        try:
            from apps.allotment.tasks import generate_allotment_pdf_task
            task = generate_allotment_pdf_task.delay(instance.pk)
            return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)
        except Exception:
            return Response(
                {"task_id": None, "detail": "PDF task not available"},
                status=status.HTTP_202_ACCEPTED,
            )
