# Illustrative request/response (paths and behavior derived directly from source; not executed against a live server in this pass)

## What a role-gated API call correctly returns for a low-privilege user

```
GET /api/licenses/0510012345/
Authorization: Bearer <JWT for user with ONLY INCENTIVE_LICENSE_VIEWER role>

HTTP/1.1 403 Forbidden
{"detail": "You do not have permission to perform this action."}
```
(enforced by `LicensePermission.required_roles_for_read`, `backend/apps/accounts/permissions.py:34-36`)

## The same user against the media endpoint for the same license's stored file

```
GET /api/media/licenses/0510012345/0510012345%20Copy.pdf
Authorization: Bearer <JWT for user with ONLY INCENTIVE_LICENSE_VIEWER role>

HTTP/1.1 200 OK
Content-Type: application/pdf
<PDF bytes of the licence copy>
```
(`ProtectedMediaView.get`, `backend/apps/core/views/media.py:35-59` — only checks
`IsAuthenticated`; never checks `LicensePermission` or any role)

This second response is what constitutes the authorization bypass: identical
authenticated principal, identical underlying document, opposite access
decision depending only on which URL prefix is used to reach it.
