"""Authentication primitives for the private master-sync API.

Sync is a server-to-server protocol.  A user JWT (including a superuser JWT)
is deliberately not a credential for this API: accepting one lets any user
claim to be an arbitrary peer in the request body.
"""
from __future__ import annotations

from dataclasses import dataclass

from rest_framework import authentication, exceptions

from .models import SyncPeer


@dataclass(frozen=True)
class SyncPeerPrincipal:
    """Minimal authenticated principal exposed to DRF permission classes."""

    peer: SyncPeer

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    @property
    def username(self) -> str:
        return f"sync-peer:{self.peer.server_id}"

    @property
    def pk(self) -> int:
        # Existing rate-limit keys require an authenticated identity with pk.
        return self.peer.pk


class PeerTokenAuthentication(authentication.BaseAuthentication):
    """Authenticate an active registered peer by its server id and secret.

    The database stores only a password-style hash of the secret.  The secret
    itself belongs in the process environment of each server, not in a model,
    dump, admin response, or log line.
    """

    server_header = "HTTP_X_SYNC_SERVER_ID"

    def authenticate(self, request):
        server_id = request.META.get(self.server_header, "").strip()
        authorization = request.META.get("HTTP_AUTHORIZATION", "")
        scheme, _, token = authorization.partition(" ")
        if not server_id or scheme.lower() != "bearer" or not token.strip():
            raise exceptions.AuthenticationFailed("Peer sync credentials are required.")

        try:
            peer = SyncPeer.objects.get(server_id=server_id, is_active=True)
        except SyncPeer.DoesNotExist:
            raise exceptions.AuthenticationFailed("Unknown or inactive sync peer.")

        if not peer.check_auth_token(token.strip()):
            raise exceptions.AuthenticationFailed("Invalid sync peer credential.")
        return SyncPeerPrincipal(peer), peer
