"""Sync API URL configuration (Module 04)."""
from django.urls import path

from .views import (
    SyncPushView,
    SyncPullView,
    DeleteCheckView,
    SyncStatusView,
    MediaDownloadView,
    SyncConflictLogView,
)

app_name = "sync"

urlpatterns = [
    path("push/", SyncPushView.as_view(), name="sync-push"),
    path("pull/", SyncPullView.as_view(), name="sync-pull"),
    path("delete-check/", DeleteCheckView.as_view(), name="sync-delete-check"),
    path("status/", SyncStatusView.as_view(), name="sync-status"),
    path("media/download/", MediaDownloadView.as_view(), name="sync-media-download"),
    path("conflicts/", SyncConflictLogView.as_view(), name="sync-conflicts"),
]
