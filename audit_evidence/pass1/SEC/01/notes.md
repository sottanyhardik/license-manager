# SEC-01 — ProtectedMediaView bypasses per-resource RBAC (LicensePermission /
BillOfEntryPermission / TradePermission) for stored documents

## Location
- `backend/apps/core/views/media.py:24-59` (`ProtectedMediaView`)
- Route: `backend/lmanagement/urls.py:40` — `re_path(r"^api/media/(?P<path>.+)$", ProtectedMediaView.as_view(), ...)`
- Predictable path templates that make the gap exploitable:
  - `backend/apps/license/models/core.py:47-` (`license_path`) — license copy /
    transfer letter files stored at `licenses/<license_number>/<license_number> Copy.ext`,
    `... TL.ext`, `... Other.ext`
  - `backend/apps/bill_of_entry/models.py:216-221` — `boe_pdf_copy` stored under
    `upload_to='boe_copies/'`
  - `backend/apps/trade/models.py:225-226` — purchase invoices under
    `upload_to="trade/purchase_invoices/"`
- Contrast with the RBAC the rest of the app enforces for the *same* data over the API:
  - `backend/apps/accounts/permissions.py` `LicensePermission` (read: `LICENSE_MANAGER`,
    `LICENSE_VIEWER`, `TRADE_VIEWER`, `TRADE_MANAGER`)
  - `BillOfEntryPermission` (read: `BOE_MANAGER`, `BOE_VIEWER`, `ACCOUNT_ACCESS`, `TL_GENERATE`)
  - `TradePermission` (read: `TRADE_MANAGER`, `TRADE_VIEWER`)

## What & why

`ProtectedMediaView.permission_classes = [IsAuthenticated]` — that is the *only*
authorization check performed before streaming a file out of `MEDIA_ROOT`
(source, verbatim):

```python
class ProtectedMediaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, path):
        media_root = os.path.realpath(settings.MEDIA_ROOT)
        full = os.path.realpath(os.path.join(media_root, path))
        if full != media_root and not full.startswith(media_root + os.sep):
            raise Http404()
        if not os.path.isfile(full):
            raise Http404()
        ...
        return FileResponse(open(full, "rb"), as_attachment=False, filename=filename)
```

The view's own docstring frames it as the fix for a *prior* CRITICAL issue
(nginx used to serve `/media/` publicly, so anyone who could guess a path —
paths are explicitly documented as "highly predictable" — could download BOE
PDFs, licence copies and transfer letters without any authentication). The fix
that shipped closes the **unauthenticated** attacker case, but only checks
`IsAuthenticated` — it never consults `LicensePermission`,
`BillOfEntryPermission`, `TradePermission`, or any resource-specific role/
ownership check. Every other read of the same underlying business objects
(licence detail, BOE detail, trade/invoice detail) goes through a role-gated
viewset; the file-download path is the one door in the app that only checks
"are you logged in", not "do you hold a role entitled to see this record".

Because file paths are namespaced by the same business-identifiers the app
itself calls "highly predictable" (license numbers, BOE copies, trade purchase
invoices — not random/opaque tokens), and because a large surface of
low-privilege roles exist by design (`INCENTIVE_LICENSE_VIEWER`,
`ALLOTMENT_VIEWER`, `REPORT_VIEWER`, `ACCOUNT_ACCESS`, ... — see
`backend/apps/accounts/views/user_management.py:13-27` `ROLE_CODES`), any
authenticated user — regardless of which of those roles they hold — can pull
another module's confidential documents by requesting
`/api/media/licenses/<license_number>/<license_number> Copy.pdf`,
`/api/media/boe_copies/<filename>`, or
`/api/media/trade/purchase_invoices/<filename>` directly, entirely bypassing
`LicensePermission` / `BillOfEntryPermission` / `TradePermission`.

## Exploit scenario

1. Attacker is a legitimate but low-privilege user, e.g. holds only
   `INCENTIVE_LICENSE_VIEWER` (no `LICENSE_VIEWER`/`LICENSE_MANAGER`,
   `BOE_VIEWER`/`BOE_MANAGER`, or `TRADE_VIEWER`/`TRADE_MANAGER`). Calling
   `GET /api/licenses/<id>/` or the BOE/trade endpoints correctly returns 403
   from `LicensePermission`/`BillOfEntryPermission`.
2. The attacker already knows (or can obtain from any of the many broadly
   readable master-data / report endpoints, or simply from having seen a
   licence number on paper/email — DGFT licence numbers are not secrets) a
   target licence number, e.g. `0510012345`.
3. `GET /api/media/licenses/0510012345/0510012345%20Copy.pdf` with the
   attacker's own valid JWT succeeds (`IsAuthenticated` only), streaming the
   scanned licence document — a customs/PII document the attacker has no role
   entitlement to see — straight past `LicensePermission`.
4. The same pattern applies to `boe_copies/` (ICEGATE BOE PDFs — PII on
   importer/exporter, invoice values) and `trade/purchase_invoices/`
   (commercial invoice PDFs).

## Business risk

Confidential customs and financial documents (licence copies, BOE PDFs,
purchase invoices, transfer letters) become accessible to any authenticated
user in the system irrespective of their assigned module/role, undermining
the entire RBAC model the rest of the API enforces. This is a broken
access-control / IDOR-class defect (OWASP A01) at the document layer.

## Mitigation recommendation

`ProtectedMediaView.get()` must resolve which business object a given stored
path belongs to and re-run the same permission check the corresponding
viewset would use (e.g. parse the `licenses/<license_number>/...` prefix,
look up the `LicenseDetailsModel`, and call `LicensePermission().has_permission`
equivalent / check `request.user.has_any_role([...])` with the same role sets
`LicensePermission`/`BillOfEntryPermission`/`TradePermission` use for read).
Minimal fix: switch on a path-prefix map (`licenses/` → license read roles,
`boe_copies/` → BOE read roles, `trade/` → trade read roles) before serving.
This does not change any public API shape, so it isn't a breaking change.

## Confidence

High — the gap is deterministic and provable purely from source: the class
declares only `IsAuthenticated`, with no per-path role/ownership logic
anywhere in `get()`. No ambiguity in current behavior.

## Unverifiable assumptions
- Whether the production nginx configs actually deployed match the
  `nginx-license-manager.conf` / `nginx-license-tractor.conf` / `nginx-labdhi.conf`
  files in this repo (which do correctly restrict `/media/` to the internal
  `/protected-media/` location). `docs/media-security-cutover.md` states the
  public `/media/` block was still live as of that runbook's writing; the
  checked-in configs show it already removed, but I cannot verify the actual
  running server config from source alone.
