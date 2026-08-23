# SEC-05 (improvement) — PDF-parsing upload endpoints have no explicit file-size cap

## Location
- `backend/apps/bill_of_entry/views/parse_pdf.py` (`BOEPdfParseView.post`) — no
  size check before `parse_boe_pdf(upload)`.
- `backend/apps/license/views/parse_pdf.py` — same pattern for license PDF parsing.
- Contrast with `backend/apps/license/views/ledger_upload.py:45`
  (`MAX_FILE_SIZE = 50 * 1024 * 1024`) which does enforce a cap for ledger
  CSV/HTM uploads.
- `backend/lmanagement/settings.py` has no `DATA_UPLOAD_MAX_MEMORY_SIZE` /
  `FILE_UPLOAD_MAX_MEMORY_SIZE` override (Django defaults apply, which only
  govern the in-memory/temp-file threshold, not a hard reject).

## What & why
Any authenticated user holding `BillOfEntryPermission`/`LicensePermission`
write access can POST an arbitrarily large file to the PDF-parse endpoints;
there is no size guard before the parser runs, unlike the ledger upload path
which explicitly caps at 50MB. A large or pathological PDF could cause
excessive memory/CPU consumption in the parsing library during a single
request.

## Risk
Low — requires an authenticated, role-holding user (an insider-only DoS
vector, not exploitable pre-auth), and is bounded somewhat by Django/DRF's
general request-size defaults and the reverse proxy's `client_max_body_size`.
Still worth closing for consistency with the ledger upload path's existing
convention.

## Mitigation recommendation
Add the same `MAX_FILE_SIZE` check pattern used in `ledger_upload.py` to both
PDF-parse endpoints before invoking the parser.

## Confidence
High (verified absence of any size check by reading both files in full).

## Classification
Improvement (consistency/hardening), not a defect — no evidence this is
currently being exploited or that it's reachable pre-authentication.
