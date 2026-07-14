from django.contrib import admin

from apps.tasks.models import Task, TaskRemark


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "status", "priority", "assigned_to", "created_by", "created_on"]
    list_filter = ["status", "priority"]
    search_fields = ["title", "description"]
    readonly_fields = [
        "created_on",
        "modified_on",
        "created_by",
        "assigned_on",
        "completed_on",
        "rejected_by",
    ]


@admin.register(TaskRemark)
class TaskRemarkAdmin(admin.ModelAdmin):
    list_display = ["id", "task", "created_by", "created_on"]
    readonly_fields = ["created_on"]
