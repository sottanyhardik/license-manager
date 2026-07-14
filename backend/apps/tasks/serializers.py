"""
apps/tasks/serializers.py

DRF serializers for Task and TaskRemark.
"""
from rest_framework.serializers import CharField, ModelSerializer

from apps.tasks.models import Task, TaskRemark


class TaskRemarkSerializer(ModelSerializer):
    created_by_username = CharField(
        source="created_by.username", read_only=True, allow_null=True
    )

    class Meta:
        model = TaskRemark
        fields = [
            "id",
            "task",
            "text",
            "created_by",
            "created_by_username",
            "created_on",
        ]
        read_only_fields = ["id", "created_by", "created_by_username", "created_on"]


class TaskSerializer(ModelSerializer):
    created_by_username = CharField(
        source="created_by.username", read_only=True, allow_null=True
    )
    assigned_to_username = CharField(
        source="assigned_to.username", read_only=True, allow_null=True
    )
    rejected_by_username = CharField(
        source="rejected_by.username", read_only=True, allow_null=True
    )
    remarks = TaskRemarkSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "assigned_to",
            "assigned_to_username",
            "assigned_on",
            "due_date",
            "completed_on",
            "rejected_by",
            "rejected_by_username",
            "rejection_reason",
            "created_by",
            "created_by_username",
            "created_on",
            "modified_on",
            "remarks",
        ]
        read_only_fields = [
            "id",
            "completed_on",
            "assigned_on",
            "rejected_by",
            "rejected_by_username",
            "rejection_reason",
            "created_by",
            "created_by_username",
            "assigned_to_username",
            "created_on",
            "modified_on",
            "remarks",
        ]
