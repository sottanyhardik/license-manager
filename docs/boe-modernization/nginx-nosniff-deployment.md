# nginx: X-Content-Type-Options nosniff on protected media

## Change
`nginx-protected-media.conf`, internal `location /protected-media/`: added
`add_header X-Content-Type-Options "nosniff" always;` next to the existing
`Cache-Control "private, no-store"` header. No `default_type` override; `alias`,
`internal;`, auth (Django checks auth before X-Accel-Redirect), and the
Content-Type / Content-Disposition values Django sets on the redirect response
are untouched. add_header inheritance: the location already defined its own
add_header, so the existing header is kept; any server-level headers wanted on
media must be repeated in this block.

## Deployment (ops, NOT done by this change)
1. Copy the updated block into the live site config.
2. Ops runs: `nginx -t && systemctl reload nginx` (with sudo).

Local syntax validation was not possible (no nginx binary on the dev machine);
`nginx -t` on the server is the check.

## Verify
With an authenticated token against an uploaded file:
`curl -I -H "Authorization: Bearer $TOKEN" https://<host>/api/media/<path>`
Expect `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`,
and the expected `Content-Type` / `Content-Disposition`. An unauthenticated
request must still return 401/403, and `/protected-media/<path>` requested
directly must return 404.

## Rollback
Remove the `add_header X-Content-Type-Options` line, then ops runs
`nginx -t && systemctl reload nginx`.
