"""Outbound sync credentials supplied by deployment configuration."""
from __future__ import annotations

from django.conf import settings


def token_for_peer(server_id: str) -> str | None:
    """Return a configured non-empty secret for ``server_id`` or ``None``.

    ``SYNC_PEER_TOKENS`` is intentionally a settings mapping populated from an
    environment-only JSON object.  It must never be populated from ``SyncPeer``
    fields because that would retain peer secrets in plaintext database dumps.
    """
    tokens = getattr(settings, "SYNC_PEER_TOKENS", {})
    if not isinstance(tokens, dict):
        return None
    token = tokens.get(server_id)
    return token.strip() if isinstance(token, str) and token.strip() else None
