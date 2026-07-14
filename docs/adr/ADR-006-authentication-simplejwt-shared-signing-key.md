# ADR-006 — Authentication: SimpleJWT with Shared Signing Key

**Status:** Accepted
**Date:** 2026-07-14

## Context

During the transition period, users are authenticated against one app but may
have their requests routed to either the legacy app or the new app depending on
the URL prefix (ADR-005). If a user logs in via the legacy app and receives a
JWT signed with legacy's SECRET_KEY, that token must be verifiable by the new
app — and vice versa. Without a shared key, the user would need to log in twice
(once per app), which is unacceptable.

The system is a single-tenant internal tool. Cookie-based session auth is
unsuitable for the React SPA because it requires same-origin constraints, CSRF
protection on every mutating request, and does not compose well with the
nginx-based routing between two origins.

## Decision

Use **djangorestframework-simplejwt (SimpleJWT)** with the following
configuration:

**Algorithm during transition:** HS256 (HMAC-SHA256)  
**Shared key:** Both legacy and new app read `SECRET_KEY` from the same
environment variable. This makes tokens minted by either app verifiable by
the other.

**Token lifetimes:**
- Access token: 30 minutes (configurable via `ACCESS_TOKEN_LIFETIME` env var)
- Refresh token: 7 days, rotating (new refresh token issued on each use),
  with token blacklist enabled (`BLACKLIST_AFTER_ROTATION = True`)

**Transport:** Bearer token in the `Authorization` header only. No cookie-based
JWT transport. No session auth for API endpoints.

**Token blacklist:** `rest_framework_simplejwt.token_blacklist` app installed.
Rotated-out refresh tokens are immediately blacklisted to prevent reuse.

**At final cutover:** Rotate to RS256. Generate a new RSA keypair. The legacy
app is decommissioned, so shared-key compatibility is no longer required.
Private key signs (new app only). Public key can be distributed to any future
service consumers.

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| RS256 during transition | The private key must be installed only on one signer. If both apps sign, they need separate keypairs — and the other app must trust both public keys. This is more complex than a shared symmetric secret for a time-limited transition. |
| Session-based auth (Django session + cookie) | Stateful; requires sticky sessions or shared session store between two apps during transition; CSRF tokens add complexity to SPA; does not compose with nginx upstream routing. |
| OAuth2 / OIDC (separate auth server) | Correct for multi-tenant or multi-service architectures; significant operational overhead for a single-tenant internal tool with a known cutover endpoint. |
| HTTP Basic Auth | Not secure over any non-TLS path; no expiry; no refresh mechanism; rejected outright. |

## Consequences

**Positive:**
- Users experience seamless authentication across both apps during transition
  — no double login.
- Stateless JWT means no shared session store infrastructure needed during
  transition.
- Rotating refresh tokens with blacklist limit the blast radius of a leaked
  refresh token to 7 days, and to zero once the token is rotated.
- SimpleJWT's integration with DRF is well-tested and low-maintenance.

**Negative:**
- Shared SECRET_KEY means a key compromise affects both apps simultaneously.
  Mitigate by storing SECRET_KEY in a secrets manager (not in `.env` committed
  to git) and rotating immediately at cutover.
- Access tokens cannot be revoked before expiry (30 min window). For
  forced-logout requirements, reduce ACCESS_TOKEN_LIFETIME or implement a
  server-side token ID blocklist.
- The RS256 rotation at cutover is a non-trivial operation: clients holding
  valid HS256 tokens at the moment of rotation will have a 30-minute graceful
  degradation window before their tokens expire and they must re-login with
  RS256 tokens.
- Token blacklist table grows over time; a periodic cleanup task (Celery beat
  job) must be configured to flush expired blacklisted tokens.

## Related ADRs

- ADR-001 — Migration Strategy: Hybrid Parallel-Run
- ADR-003 — Backend Tech Stack
- ADR-005 — API Versioning: /api/v1/ prefix
- ADR-008 — Signal Strategy: Celery Replaces Cross-App Signals
