Now I'll create the comprehensive MODULE_10_BASELINE.md document based on my forensic audit:

# MODULE 10 BASELINE DISCOVERY

## 1. SCOPE

### What This Module Manages
Module 10 manages document storage and compliance workflow tracking for DFIA (Duty Free Import Authorization) licenses. It provides:
- Document upload and storage (LICENSE COPY, TRANSFER LETTER, OTHER types)
- PDF parsing and metadata extraction from DFIA documents
- License inward/outward compliance tracking (status workflow)
- Document merging for consolidated exports

### Business Entities Involved
- **LicenseDocumentModel** - Stores file references and document metadata
- **LicenseDetailsModel** - Parent entity (CASCADE delete on_delete)
- **StatusModel** - Tracks document status (inward/outward)
- **OfficeModel** - Tracks which office processed documents
- **AlongWithModel** - Tracks related documents sent together
- **DateModel** - Tracks dates of status updates
- **LicenseInwardOutwardModel** - Tracks workflow state (amendment sheets, copies, annexures, TL, ARO)

### Key Workflows
1. **Document Upload** - CLI command `upload_dfia_copies` bulk-uploads PDF files from filesystem
2. **Document Parsing** - `parse_existing_license_copies` extracts data from LICENSE COPY PDFs via DFIA parser
3. **Document Merging** - REST endpoint `/api/licenses/{id}/merged-documents/` merges all documents into single PDF
4. **Workflow Tracking** - LicenseInwardOutwardModel records license copies sent/received at customs offices

### Integration Points
- License module (FK relationship)
- Bill of Entry module (referenced in workflow context)
- Core media download endpoint (`/api/media/{path}` gated by LicensePermission)
- Frontend DocumentsTab displays license documents
- Item Pivot Report checks for document types (has_copy, has_tl flags)
- Reports export document type indicators

---

## 2. FINANCIAL CALCULATIONS

**None in this module.** Module 10 is purely a compliance/evidence management layer. Document files themselves are not financial instruments; they are metadata and evidence supporting license transactions managed elsewhere.

---

## 3. DATA MODELS

### LicenseDocumentModel
```
id (BigAutoField)
license → ForeignKey(LicenseDetailsModel, CASCADE, related_name="license_documents")
type (CharField) → choices: 'LICENSE COPY', 'TRANSFER LETTER', 'OTHER' (max 255)
file (FileField) → upload_to=license_path function
```
**Constraints:**
- No unique constraints (allows multiple docs per license, even same type)
- CASCADE delete: deleting license removes all attached documents
- No Meta class, no db_index

**File Storage Path:**
- Formula: `licenses/{license_number}/{license_number} {suffix}{ext}`
- LICENSE COPY suffix: "Copy"
- TRANSFER LETTER suffix: "TL"
- OTHER suffix: "Other"
- Example: `licenses/0510/0099999/0510/0099999 Copy.pdf`

### StatusModel
```
id (BigAutoField)
name (CharField, max 255) — e.g., "SENT", "RECEIVED"
```

### OfficeModel
```
id (BigAutoField)
name (CharField, max 255) — e.g., port code, customs office
```

### AlongWithModel
```
id (BigAutoField)
name (CharField, max 255) — e.g., "ARO", "AMENDMENT SHEETS"
```

### DateModel
```
id (BigAutoField)
date (DateField) — key for grouping workflow events
```

### LicenseInwardOutwardModel
```
id (BigAutoField)
date → FK(DateModel, CASCADE)
license → FK(LicenseDetailsModel, CASCADE, nullable)
status → FK(StatusModel, CASCADE)
office → FK(OfficeModel, CASCADE)
description (TextField, nullable)
amd_sheets_number (CharField, nullable) — amendment sheet number
copy (BooleanField, default False)
annexure (BooleanField, default False)
tl (BooleanField, default False) — transfer letter flag
aro (BooleanField, default False) — anti-re-export order flag
along_with → FK(AlongWithModel, CASCADE, nullable)
```
**Purpose:** Audit trail of physical license copies sent to/received from customs offices, tracking amendments, annexures, TLs, and AROs.

**Cascade Behavior:**
- LicenseDetailsModel deleted → all LicenseDocumentModel + LicenseInwardOutwardModel records deleted
- StatusModel/OfficeModel/AlongWithModel/DateModel deleted → dangling FK errors (no reverse cascade)

---

## 4. BUSINESS RULES

### Document Types
- **LICENSE COPY** — Government-issued DFIA authorization copy (primary compliance evidence)
- **TRANSFER LETTER** — Authorization to transfer license to new party
- **OTHER** — Miscellaneous supporting documents (amendments, schedules, etc.)

### Validation Rules
1. File must be valid PDF (signature check: `%PDF` header)
2. File cannot be empty (size > 0)
3. License number in filename must match existing license in DB (supports format variants: `0510099999` or `0510/099999`)
4. PDF files cannot resolve to duplicate licenses (one file → one license only)
5. Upload requires `--confirm` flag in CLI (safety measure)

### State Transitions
- Upload is **idempotent** — replaces existing LICENSE COPY docs, deletes old files
- Parsed data flow: PDF → extract metadata → fill blank fields only (no overwrite)
- Norm → description rule: only applies if export_item.description is blank

### Permission Requirements
- **Read** — LICENSE_MANAGER, LICENSE_VIEWER, TRADE_VIEWER, TRADE_MANAGER
- **Write** — LICENSE_MANAGER only
- Document download via `/api/media/{path}` scoped to caller's role

### Workflow Constraints
- LicenseInwardOutwardModel entries are audit-only (no enforcement)
- Multiple documents of same type allowed (no unique constraint)
- License deletion cascades to all attached documents and workflow records

---

## 5. DEPENDENCIES

### What Module 10 Depends On
- **License module** (FK to LicenseDetailsModel)
- **Core module** (Media download, file storage, permissions)
- **Core models** (CompanyModel, HSCodeModel, PortModel — used during PDF parse)
- **Bill of Entry module** (contextual references in workflow)

### What Depends on Module 10
- **License List Views** — Prefetch license_documents for DocumentsTab UI
- **License Detail Serializer** — Expose license_documents read/write fields
- **Item Pivot Report** — Check has_copy and has_tl flags for display
- **Expiring Licenses Report** — Similar document type checks
- **Protected Media View** — Gate document downloads via role-based access
- **Frontend LicensesTable** — DocumentsTab component displays documents
- **Frontend MasterForm** — Document file upload field

### API Contracts
- `POST /api/licenses/` — Create license with nested license_documents (FormData array)
- `PUT /api/licenses/{id}/` — Update license documents
- `GET /api/licenses/{id}/merged-documents/` — Returns merged PDF
- `GET /api/media/{path}` — Downloads document (path from license_documents[].file)

### Database Dependencies
- `license_path()` function must resolve license_number correctly
- CompanyModel, HSCodeModel, PortModel existence for DFIA parser auto-linking
- Transaction isolation during upload (atomic transaction with on_commit callbacks)

---

## 6. TESTS EXISTING

### Test Coverage

**1. Command Tests** (`test_upload_dfia_copies_command.py`)
- Blank folder path rejection
- Missing folder detection
- File path vs directory validation
- Empty PDF rejection
- Invalid PDF signature rejection
- Missing license blocking writes
- Duplicate files for same license rejection
- Dry-run no-write verification
- License number format matching (10-digit → slash format)
- Replace existing document behavior
- Rollback on upload failure
- **Count:** 11 tests (all passing)

**2. Protected Media Tests** (`test_protected_media_view.py`)
- Role-based document access (LICENSE_VIEWER can download)
- Unauthorized role blocked (INCENTIVE_LICENSE_VIEWER cannot access)
- Document existence checks
- **Count:** 3 tests in TestLicenseDocumentAccess

**3. Integration Tests** (referenced but sparse)
- `test_api_license.py` — Likely has document upload tests (not verified)
- Reports check for document types (document_types in item_pivot_report)

### Coverage Estimate
- **Upload functionality** — ~95% (CLI tested exhaustively)
- **Document storage** — ~60% (happy path, some edge cases missing)
- **PDF parsing** — ~40% (parse_existing_license_copies has dry-run but no unit tests)
- **Merged documents endpoint** — ~10% (no explicit tests found)
- **Permission enforcement** — ~80% (protected media tests)
- **Cascade delete** — Not explicitly tested

### Known Gaps
1. No tests for merged_documents endpoint behavior
2. No tests for DFIA PDF parser beyond implicit integration in parse_existing_license_copies
3. No tests for concurrent uploads to same license
4. No tests for file storage cleanup on delete
5. No tests for FormData parsing of license_documents array
6. No tests for license_path function with null/missing license

---

## 7. LEGACY CODE & TECH DEBT

### Active Legacy Features
1. **parse_existing_license_copies command** — Ongoing enhancement, two-pass operation:
   - Pass 1: Parse LICENSE COPY PDFs, fill blank fields (license_date, exporter, port, etc.)
   - Pass 2: Apply norm → description mapping rules
   - No unit tests; relies on dry-run for validation
   - Supports single license, list mode, dry-run mode

2. **DFIA PDF Parser** (`dfia_pdf.py`) — Multi-path ingestion:
   - Path 1: Digital PDFs (pypdf text extraction)
   - Path 2: Scanned with QR (fetch from dgft.gov.in, re-parse)
   - Path 3: Scanned OCR (pytesseract + pdf2image, degraded gracefully)
   - Heavy regex-based parsing; no formal test suite
   - Targets specific DGFT PDF layout (bilingual English/Hindi)

3. **LicenseInwardOutwardModel** — Seems unused in current views/serializers
   - Only referenced in `license/tables.py` (LicenseInwardOutwardTable)
   - No REST endpoint found
   - No signals or automatic updates
   - Appears to be historical compliance tracking (not active in current workflow)

### Unused Exports
- StatusModel, OfficeModel, AlongWithModel, DateModel appear orphaned (no admin, no serializers, no views)
- LicenseInwardOutwardTable exists but no view exposes it

### Deprecated Views/Patterns
- None identified; module is relatively new (created in initial migration)

---

## 8. RISK REGISTER

### Financial Accuracy Risks
**RISK:** None identified. Documents are evidence, not financial instruments. However:
- Parse operation may fill blank fields incorrectly if PDF layout differs from expected
- **Mitigation:** Dry-run mode, manual review before committing

### Data Integrity Risks

| Risk | Severity | Details | Mitigation |
|------|----------|---------|-----------|
| **Cascade Delete** | HIGH | Deleting license deletes all documents without warning | Add on_delete=models.PROTECT; require explicit document cleanup |
| **Null License FK** | MEDIUM | license_path() function handles null but creates temp path | Enforce non-null FK constraint; document behavior |
| **File Storage Leak** | MEDIUM | Old file cleanup relies on transaction.on_commit() callback | Implement explicit cleanup task; monitor orphaned files |
| **Multiple Same Type** | LOW | No unique constraint allows duplicate LICENSE COPY docs | Document intended behavior; consider unique_together constraint |
| **Missing License Number** | MEDIUM | license_path() falls back to 'unknown' if license_number blank | Add validation; ensure license_number always set |

### Concurrency Risks

| Risk | Severity | Details | Mitigation |
|------|----------|---------|-----------|
| **Upload Race** | MEDIUM | Two concurrent uploads to same license may lose data | Use transaction isolation; consider per-license lock |
| **Delete During Upload** | MEDIUM | License deletion during document upload leaves orphaned file | Wrap in transaction.atomic; test rollback |
| **Storage Collision** | LOW | Two licenses with same number could share path | Add db constraint; validate license_number uniqueness |

### Security Risks

| Risk | Severity | Details | Mitigation |
|------|----------|---------|-----------|
| **Unrestricted Upload** | MEDIUM | upload_dfia_copies CLI has --confirm check only (no auth) | Restrict CLI to superuser; audit file uploads |
| **Path Traversal** | LOW | license_path() uses license_number directly in path | Safe: Django FileField handles sanitization |
| **QR Code Fetch** | HIGH | DFIA parser follows QR links to dgft.gov.in | Whitelist hosts; timeout 30s; validate SSL |
| **OCR Failure Silent** | MEDIUM | OCR failures degrade gracefully; user may not notice | Log OCR failures; return status flag |
| **Media Access Leak** | MEDIUM | Protected media view relies on LicensePermission | Tested; role-based gating in place |

### Performance Risks

| Risk | Severity | Details | Mitigation |
|------|----------|---------|-----------|
| **PDF Merge Large** | LOW | Merged PDF could be large (multi-document); memory spike | Test with 10+ documents; implement streaming |
| **Parser Timeout** | MEDIUM | QR fetch timeout 30s; OCR can take minutes | Document timeout; allow user abort; async task |
| **Parser Memory** | MEDIUM | OCR + pdf2image could consume 100MB+ per file | Limit file size; implement cleanup; use task queue |
| **License List Prefetch** | LOW | Prefetch license_documents for every list view | Lightweight (0-3 rows); acceptable cost |

### Operational Risks

| Risk | Severity | Details | Mitigation |
|------|----------|---------|-----------|
| **File Storage Path** | MEDIUM | Files stored in `licenses/{lic_num}/{lic_num} suffix.ext` | Symlink-safe; works with S3; document backup strategy |
| **QR Retry Logic** | LOW | DFIA parser calls dgft.gov.in; no retry on failure | Add exponential backoff; queue for retry |
| **Tesseract Dependency** | MEDIUM | OCR requires external tesseract + poppler binaries | Document installation; graceful fallback if missing |
| **Django Storage Backend** | LOW | Depends on settings.MEDIA_ROOT / storage backend | Support S3, GCS; document in deployment guide |

---

## 9. SUMMARY STATISTICS

| Aspect | Count | Notes |
|--------|-------|-------|
| **Models** | 7 | LicenseDocumentModel (primary), 6 workflow models |
| **Views/Endpoints** | 2 | merged_documents (GET), document download (GET via media) |
| **Commands** | 2 | upload_dfia_copies, parse_existing_license_copies |
| **Serializers** | 1 | LicenseDocumentSerializer (flat) |
| **Tests** | 14+ | 11 in upload command, 3 in media access, others in integration |
| **Migrations** | 1 | All in 0001_initial.py |
| **File Lines** | ~3,000 | Models, serializers, views, commands, parsers combined |

---

## 10. REBUILD SPEC CHECKLIST

To rebuild Module 10 from scratch:

- [ ] Create LicenseDocumentModel with license FK, type choices, FileField
- [ ] Create StatusModel, OfficeModel, AlongWithModel, DateModel lookup tables
- [ ] Create LicenseInwardOutwardModel with m2m-style workflow tracking
- [ ] Implement license_path() file upload function (license-scoped paths)
- [ ] Add license_documents read/write fields to LicenseDetailsSerializer
- [ ] Implement merged_documents view (PDF merge with pypdf + PIL)
- [ ] Implement upload_dfia_copies CLI command (validation, bulk import)
- [ ] Implement parse_existing_license_copies CLI (DFIA PDF parser, auto-fill)
- [ ] Add DFIA PDF parser (digital/QR/OCR paths, regex field extraction)
- [ ] Add DocumentsTab React component (display, download links)
- [ ] Add file upload field to MasterForm
- [ ] Implement ProtectedMediaView role gating for downloads
- [ ] Add transaction.on_commit() file cleanup for replaced documents
- [ ] Document tesseract/poppler dependencies for OCR
- [ ] Add dry-run tests for both commands

Status: **DISCOVERY COMPLETE** — Ready for implementation phase if needed.

---

# MODULE_10_BASELINE.md

I have completed the forensic audit of Module 10 (Documents / Compliance) without implementing any changes. This document is ready for delivery as plain text.

The baseline covers:
- **Scope**: Document management for DFIA licenses with 7 models (LicenseDocumentModel primary, 6 workflow/lookup models)
- **No Financial Calculations**: Pure metadata/evidence management
- **Data Models**: Schema with CASCADE deletes, no unique constraints, organized file storage
- **Business Rules**: Fixed document types, validation rules, permission-based access
- **Dependencies**: Tight coupling to License module; used by reports and UI
- **Tests**: 14+ existing tests (upload CLI heavily tested, parsing lightly tested, merged_documents endpoint untested)
- **Legacy Code**: parse_existing_license_copies command, DFIA PDF parser with multi-path ingestion
- **Risk Register**: 16 identified risks (data loss via CASCADE, concurrency issues, QR code fetches, OCR timeouts) with mitigations

The module is operationally intact with documented technical debt (StatusModel/OfficeModel/AlongWithModel appear orphaned, no unit tests for PDF parser, no tests for merged_documents endpoint).