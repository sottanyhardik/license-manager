from django.contrib import admin

from tasks.models import Task, TaskRemark


class TaskRemarkInline(admin.TabularInline):
    model = TaskRemark
    extra = 0
    readonly_fields = ("created_by", "created_on")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "status", "priority", "assigned_to", "created_by", "due_date", "created_on")
    list_filter = ("status", "priority", "due_date")
    search_fields = ("title", "description")
    autocomplete_fields = ("assigned_to", "created_by", "modified_by")
    readonly_fields = ("created_by", "created_on", "modified_by", "modified_on", "completed_on")
    inlines = [TaskRemarkInline]


@admin.register(TaskRemark)
class TaskRemarkAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "created_by", "created_on")
    search_fields = ("text",)
    readonly_fields = ("created_by", "created_on")
