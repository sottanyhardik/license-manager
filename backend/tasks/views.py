from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tasks.models import Task, TaskRemark
from tasks.serializers import TaskRemarkSerializer, TaskSerializer


class TaskViewSet(viewsets.ModelViewSet):
    """
    Personal task list. Users see tasks they created OR were assigned.
    Superusers see all tasks.
    """

    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "priority", "assigned_to"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_on", "due_date", "priority", "status"]
    ordering = ["-created_on"]

    def get_queryset(self):
        user = self.request.user
        qs = Task.objects.select_related("created_by", "assigned_to").prefetch_related("remarks__created_by")
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

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self._can_modify(instance):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self._can_modify(instance):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
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

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        if not self._can_modify(task):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        task.mark_completed()
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        task = self.get_object()
        if not self._can_modify(task):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        reason = (request.data.get("reason") or "").strip()
        task.mark_rejected()
        if reason:
            TaskRemark.objects.create(task=task, text=f"[Rejected] {reason}", created_by=request.user)
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        task = self.get_object()
        if not self._can_modify(task):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        task.status = Task.STATUS_PENDING
        task.completed_on = None
        task.save(update_fields=["status", "completed_on", "modified_on", "modified_by"])
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["get", "post"], url_path="remarks")
    def remarks(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            qs = task.remarks.select_related("created_by").all()
            return Response(TaskRemarkSerializer(qs, many=True).data)

        if not self._can_modify(task):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"text": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        remark = TaskRemark.objects.create(task=task, text=text, created_by=request.user)
        return Response(TaskRemarkSerializer(remark).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="assignable-users")
    def assignable_users(self, request):
        """Lightweight list of active users that tasks can be assigned to."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        users = User.objects.filter(is_active=True).order_by("username").values("id", "username", "first_name", "last_name")
        return Response(list(users))
