"""
apps/tasks/views.py

TaskViewSet: full CRUD + custom actions (complete, reject, reopen, remarks,
assignable-users).

Visibility:  superusers see all tasks; regular users see only tasks they
             created or were assigned to.
Mutation:    any of creator / assignee / superuser may update or add remarks;
             only creator or superuser may delete.
"""
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tasks.filters import TaskFilter
from apps.tasks.models import Task
from apps.tasks.serializers import TaskRemarkSerializer, TaskSerializer
from apps.tasks.services import task_service


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TaskFilter
    search_fields = ["title", "description"]
    ordering_fields = ["created_on", "due_date", "priority", "status"]
    ordering = ["-created_on"]

    def get_queryset(self):
        user = self.request.user
        qs = Task.objects.select_related(
            "created_by", "assigned_to", "rejected_by"
        ).prefetch_related("remarks__created_by")
        if user.is_superuser:
            return qs
        return qs.filter(Q(created_by=user) | Q(assigned_to=user))

    def _can_modify(self, task):
        user = self.request.user
        return (
            user.is_superuser
            or task.created_by_id == user.id
            or task.assigned_to_id == user.id
        )

    def perform_create(self, serializer):
        from django.utils import timezone

        user = self.request.user
        assigned_to = serializer.validated_data.get("assigned_to") or user
        serializer.save(
            created_by=user,
            modified_by=user,
            assigned_to=assigned_to,
            assigned_on=timezone.now(),
        )

    def perform_update(self, serializer):
        from django.utils import timezone

        instance = serializer.instance
        new_assignee = serializer.validated_data.get("assigned_to", instance.assigned_to)
        extra = {}
        if new_assignee != instance.assigned_to:
            extra["assigned_on"] = timezone.now()
        serializer.save(modified_by=self.request.user, **extra)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self._can_modify(instance):
            return Response(
                {"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self._can_modify(instance):
            return Response(
                {"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        if not (user.is_superuser or instance.created_by_id == user.id):
            return Response(
                {"detail": "Only the creator (or superuser) can delete a task."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    # ── Custom actions ────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        if not self._can_modify(task):
            return Response(
                {"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN
            )
        if task.status == Task.STATUS_COMPLETED:
            return Response(
                {"detail": "Task is already completed."}, status=status.HTTP_409_CONFLICT
            )
        if task.status == Task.STATUS_REJECTED:
            return Response(
                {"detail": "Cannot complete a rejected task; reopen it first."},
                status=status.HTTP_409_CONFLICT,
            )
        task_service.complete_task(task)
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        task = self.get_object()
        if not self._can_modify(task):
            return Response(
                {"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN
            )
        reason = request.data.get("reason") or ""
        task_service.reject_task(task, by_user=request.user, reason=reason)
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        task = self.get_object()
        if not self._can_modify(task):
            return Response(
                {"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN
            )
        task_service.reopen_task(task)
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["get", "post"], url_path="remarks")
    def remarks(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            qs = task.remarks.select_related("created_by").all()
            return Response(TaskRemarkSerializer(qs, many=True).data)
        # POST
        if not self._can_modify(task):
            return Response(
                {"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN
            )
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response(
                {"text": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        remark = task_service.add_remark(task_id=task.pk, text=text, user=request.user)
        return Response(TaskRemarkSerializer(remark).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="assignable-users")
    def assignable_users(self, request):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        users = (
            User.objects.filter(is_active=True)
            .order_by("username")
            .values("id", "username", "first_name", "last_name")
        )
        return Response(list(users))
