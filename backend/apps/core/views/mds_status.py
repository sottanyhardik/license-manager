"""
Read-only status endpoint for the central Master-Data Service (ADR-001).

GET /api/masters/mds/status/

Reports whether MDS integration is enabled, the configured base URL, and a
per-model view of the local mirror: how many rows it holds and when it was last
synced. ``healthy`` is true only when MDS is enabled AND every configured model
has synced within the freshness window (~15 min) — the polling backstop from
ADR-001 Decision 3 runs every 5 min, so a healthy system syncs well inside 15.

Design constraints (kept deliberately additive and safe):
- Purely READ-ONLY. It never triggers a sync or writes anything.
- Import-guarded: when the optional ``mds_client`` package is not installed, or
  MDS is disabled, the view still responds with a well-formed, honest payload
  (``enabled: false``, ``models: []``, ``healthy: false``) instead of erroring.
- Guarded by an existing admin permission (least privilege) — this exposes
  operational/config detail (base URL, sync lag) that is not for general users.
"""
from __future__ import annotations

from datetime import timedelta

from django.apps import apps as django_apps
from django.conf import settings
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import UserManagementPermission

#: A model is considered fresh if it synced within this window. The mirror sync
#: beat task runs every 5 min (ADR-001 Decision 3 polling backstop); 15 min
#: tolerates a couple of missed/slow cycles before flagging unhealthy.
FRESHNESS_WINDOW = timedelta(minutes=15)


class MDSStatusView(APIView):
    """Operational status of the MDS mirror sync. Read-only, admin-only."""

    permission_classes = [UserManagementPermission]

    def get(self, request):
        enabled = bool(getattr(settings, "MDS_ENABLED", False))
        base_url = getattr(settings, "MDS_BASE_URL", "") or ""

        payload = {
            "enabled": enabled,
            "base_url": base_url,
            "models": [],
            "healthy": False,
        }

        if not enabled:
            return Response(payload)

        # mds_client is optional. If it is not importable we must still respond
        # cleanly rather than 500 — treat it as "not synced".
        try:
            from mds_client.models import MDSSyncState
        except ImportError:
            return Response(payload)

        model_configs = getattr(settings, "MDS_MODELS", {}) or {}

        # One query for all sync-state rows, keyed by model_label.
        state_by_label = {
            s.model_label: s
            for s in MDSSyncState.objects.all().only(
                "model_label", "last_synced_at"
            )
        }

        now = timezone.now()
        models_info = []
        all_fresh = True

        for model_label, cfg in model_configs.items():
            state = state_by_label.get(model_label)
            last_synced_at = state.last_synced_at if state else None

            models_info.append(
                {
                    "model_label": model_label,
                    "last_synced_at": (
                        last_synced_at.isoformat() if last_synced_at else None
                    ),
                    "count": self._mirror_count(cfg.get("mirror_model")),
                }
            )

            if last_synced_at is None or (now - last_synced_at) > FRESHNESS_WINDOW:
                all_fresh = False

        payload["models"] = models_info
        # Healthy only if enabled, at least one model is configured, and every
        # configured model synced within the freshness window.
        payload["healthy"] = bool(model_configs) and all_fresh
        return Response(payload)

    @staticmethod
    def _mirror_count(mirror_model: str | None) -> int:
        """Row count of the local mirror model, or 0 if it can't be resolved.

        Never raises: an unresolvable/typo'd mirror_model must not break the
        whole status payload."""
        if not mirror_model:
            return 0
        try:
            app_label, model_name = mirror_model.split(".", 1)
            model = django_apps.get_model(app_label, model_name)
            return model.objects.count()
        except Exception:
            return 0
