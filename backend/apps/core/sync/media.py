"""
Media Sync Service (Module 04)

Handles synchronization of media files (images, documents) across servers.

Flow:
1. When a sync event contains media field references, a MediaSyncTask is created.
2. A background worker picks up pending tasks and downloads files from the source peer.
3. Downloaded files are verified via SHA256 before being saved.
4. Failed downloads are retried with exponential backoff.
5. After all retries are exhausted, the task is marked as failed for manual intervention.
"""
from __future__ import annotations

import hashlib
import logging
from io import BytesIO

from django.apps import apps
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import MediaSyncTask, SyncPeer
from .registry import get_entry
from .mixins import media_sha256

logger = logging.getLogger("sync.media")

MAX_RETRY_ATTEMPTS = 5


def create_media_tasks(
    model_label: str,
    natural_key: str,
    media_data: dict[str, dict],
    source_server: str,
) -> list[MediaSyncTask]:
    """Create MediaSyncTask records for media fields that need syncing.

    media_data shape:
    {
        "logo": {"path": "companies/logos/abc.png", "sha256": "deadbeef..."},
        "signature": {"path": "companies/sigs/xyz.png", "sha256": "cafebabe..."},
    }
    """
    tasks = []
    for field_name, info in media_data.items():
        if not info or not info.get("path"):
            continue

        # Check if we already have a pending task for this exact file
        existing = MediaSyncTask.objects.filter(
            model_label=model_label,
            natural_key=natural_key,
            field_name=field_name,
            source_path=info["path"],
            status__in=[MediaSyncTask.STATUS_PENDING, MediaSyncTask.STATUS_IN_PROGRESS],
        ).exists()

        if existing:
            continue

        task = MediaSyncTask.objects.create(
            model_label=model_label,
            natural_key=natural_key,
            field_name=field_name,
            source_server=source_server,
            source_path=info["path"],
            expected_sha256=info.get("sha256", ""),
        )
        tasks.append(task)
        logger.info(
            "Created media sync task: %s[%s].%s from %s",
            model_label, natural_key, field_name, source_server,
        )

    return tasks


def process_media_task(task: MediaSyncTask, file_content: bytes) -> bool:
    """Process a single media sync task with the downloaded file content.

    Verifies SHA256 if expected_sha256 is set, then saves the file to the
    model instance's field.

    Returns True on success, False on failure.
    """
    task.status = MediaSyncTask.STATUS_IN_PROGRESS
    task.attempts += 1
    task.save(update_fields=["status", "attempts"])

    try:
        # SHA256 verification
        if task.expected_sha256:
            actual_sha256 = hashlib.sha256(file_content).hexdigest()
            if actual_sha256 != task.expected_sha256:
                raise ValueError(
                    f"SHA256 mismatch: expected {task.expected_sha256}, "
                    f"got {actual_sha256}"
                )

        # Resolve the model instance
        entry = get_entry(task.model_label)
        if entry is None:
            raise ValueError(f"Unknown model_label: {task.model_label}")

        Model = apps.get_model(task.model_label)
        nk_parts = task.natural_key.split("|")
        nk_filter = dict(zip(entry.natural_key, nk_parts))
        instance = Model.objects.get(**nk_filter)

        # Save the file to the field
        field = getattr(instance, task.field_name)
        filename = task.source_path.split("/")[-1] if "/" in task.source_path else task.source_path
        field.save(filename, ContentFile(file_content), save=True)

        task.status = MediaSyncTask.STATUS_COMPLETE
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "completed_at"])

        logger.info(
            "Media sync complete: %s[%s].%s (SHA256 verified: %s)",
            task.model_label, task.natural_key, task.field_name,
            bool(task.expected_sha256),
        )
        return True

    except Exception as exc:
        task.last_error = str(exc)
        if task.attempts >= MAX_RETRY_ATTEMPTS:
            task.status = MediaSyncTask.STATUS_FAILED
            logger.error(
                "Media sync FAILED (max retries): %s[%s].%s — %s",
                task.model_label, task.natural_key, task.field_name, exc,
            )
        else:
            task.status = MediaSyncTask.STATUS_PENDING  # retry later
            logger.warning(
                "Media sync retry %d/%d: %s[%s].%s — %s",
                task.attempts, MAX_RETRY_ATTEMPTS,
                task.model_label, task.natural_key, task.field_name, exc,
            )
        task.save(update_fields=["status", "last_error"])
        return False


def get_pending_media_tasks(limit: int = 50) -> list[MediaSyncTask]:
    """Return pending media sync tasks ordered by creation time."""
    return list(
        MediaSyncTask.objects.filter(
            status=MediaSyncTask.STATUS_PENDING,
        ).order_by("created_at")[:limit]
    )


def get_media_info(instance, entry) -> dict[str, dict]:
    """Extract media field info (path + SHA256) from a model instance.

    Used when serializing sync events to include media metadata.
    """
    info = {}
    for field_name in entry.media_fields:
        field_file = getattr(instance, field_name, None)
        if field_file and field_file.name:
            info[field_name] = {
                "path": field_file.name,
                "sha256": media_sha256(field_file) or "",
            }
        else:
            info[field_name] = None
    return info


def download_media_from_peer(peer: SyncPeer, media_path: str) -> bytes | None:
    """Download a media file from a peer server.

    Uses the peer's base_url and auth_token to fetch the file.
    Returns the file content as bytes, or None on failure.
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    # The path must be percent-encoded: uploaded filenames legitimately contain
    # spaces, "&" and "+", all of which would otherwise truncate or corrupt the
    # query parameter and make the peer serve the wrong file (or 404).
    query = urllib.parse.urlencode({"path": media_path})
    url = f"{peer.base_url.rstrip('/')}/api/sync/media/download/?{query}"
    req = urllib.request.Request(url)
    if peer.auth_token:
        req.add_header("Authorization", f"Bearer {peer.auth_token}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        logger.error("Failed to download media from %s: %s", peer.server_id, exc)
        return None
    except Exception:
        # A socket read timeout raises TimeoutError, not URLError.  Anything
        # unexpected here must degrade to a retry, never abort the worker loop
        # and leave the remaining tasks unprocessed.
        logger.exception("Unexpected error downloading media from %s", peer.server_id)
        return None


def run_media_sync_worker():
    """Process all pending media sync tasks.

    For each task, attempts to download the file from the source peer
    and save it locally. This is designed to be called periodically
    by a Celery beat task or management command.
    """
    tasks = get_pending_media_tasks()
    if not tasks:
        return

    # Group tasks by source server for connection reuse
    by_server: dict[str, list[MediaSyncTask]] = {}
    for task in tasks:
        by_server.setdefault(task.source_server, []).append(task)

    for server_id, server_tasks in by_server.items():
        try:
            peer = SyncPeer.objects.get(server_id=server_id, is_active=True)
        except SyncPeer.DoesNotExist:
            logger.error("No active peer found for server_id: %s", server_id)
            for task in server_tasks:
                task.last_error = f"No active peer for {server_id}"
                task.save(update_fields=["last_error"])
            continue

        for task in server_tasks:
            content = download_media_from_peer(peer, task.source_path)
            if content is not None:
                process_media_task(task, content)
            else:
                task.attempts += 1
                task.last_error = "Download returned None"
                if task.attempts >= MAX_RETRY_ATTEMPTS:
                    task.status = MediaSyncTask.STATUS_FAILED
                else:
                    task.status = MediaSyncTask.STATUS_PENDING
                task.save(update_fields=["status", "attempts", "last_error"])
