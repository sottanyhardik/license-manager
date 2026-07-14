"""
apps/tasks/filters.py

django-filter FilterSet for the Task model.
"""
import django_filters

from apps.tasks.models import Task


class TaskFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Task.STATUS_CHOICES)
    priority = django_filters.ChoiceFilter(choices=Task.PRIORITY_CHOICES)
    assigned_to = django_filters.NumberFilter()

    class Meta:
        model = Task
        fields = ["status", "priority", "assigned_to"]
