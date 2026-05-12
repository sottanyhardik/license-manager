from rest_framework import serializers

from tasks.models import Task, TaskRemark


class TaskRemarkSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = TaskRemark
        fields = ["id", "task", "text", "created_by", "created_by_username", "created_on"]
        read_only_fields = ["id", "created_by", "created_by_username", "created_on"]


class TaskSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    assigned_to_username = serializers.CharField(source="assigned_to.username", read_only=True)
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
            "due_date",
            "completed_on",
            "created_by",
            "created_by_username",
            "created_on",
            "modified_on",
            "remarks",
        ]
        read_only_fields = [
            "id",
            "completed_on",
            "created_by",
            "created_by_username",
            "assigned_to_username",
            "created_on",
            "modified_on",
            "remarks",
        ]
