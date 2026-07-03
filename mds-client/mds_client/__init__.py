"""
mds_client — Django client for the central Master-Data Service (ADR-001, Decision 3).

Responsibilities:
- WRITE masters to the central MDS over REST (``write_master`` / ``MDSClient.bulk_upsert``).
- Keep a local read-only MIRROR fresh via delta pulls + the change feed
  (``mds_client.sync``).
- Degrade gracefully: reads always work from the local mirror; writes fail
  loudly (``MDSUnavailable``) — never silently dropped — when MDS is unreachable.

Public surface (import lazily where possible to keep Django app-loading clean):
    from mds_client.client import MDSClient, MDSUnavailable, MDSError
    from mds_client.sync import sync_model, sync_all, write_master
"""

default_app_config = "mds_client.apps.MDSClientConfig"

__version__ = "0.1.0"

# Ready-to-use reference mapping for all 17 masters (a plain dict — no Django
# models imported at package-load time, so this is import-safe).
from .model_map import DEFAULT_MDS_MODELS, KEYLESS_MODEL_LABELS  # noqa: E402

__all__ = [
    "__version__",
    "default_app_config",
    "DEFAULT_MDS_MODELS",
    "KEYLESS_MODEL_LABELS",
]
