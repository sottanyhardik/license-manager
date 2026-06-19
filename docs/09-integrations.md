# 09 — Integrations

---

## Internal Integrations

### Celery + Redis (Task Queue)

**Purpose**: Offload heavy ledger file processing to background workers.

**Setup**:
- Broker: Redis
- Backend: Redis (for task result storage)
- Workers: `celery -A lmanagement worker -Q celery,ledger -l info` (must bind the `ledger` queue — `process_single_license` is dispatched there via `apply_async(..., queue='ledger')`)

**Tasks**:
- `process_single_license` — processes one license row from a ledger upload; creates/updates `RowDetails`, recalculates balances
- `CeleryTaskTracker` model records running task IDs for monitoring

**Frontend Integration**: `LedgerUpload.tsx` polls `GET /api/ledger-task-status/:task_id/` every second, reading from Celery's result backend via `AsyncResult`.

---

### WhiteNoise (Static Files)

**Purpose**: Serve frontend assets directly from the Django process — no Nginx needed for static files.

- `frontend/dist/assets/` served at `/assets/`
- React `index.html` served by catch-all URL pattern for all non-API routes
- Production: compressed (brotli/gzip) assets via WhiteNoise

---

### Django Admin (Internal)

Built-in Django admin at `/admin/` used for:
- Emergency data corrections
- Viewing activity logs
- Managing Celery task tracker entries

---

## External Document Generation

### ReportLab (PDF Generation)

**Purpose**: Generate license balance PDFs server-side.

**Used in**:
- `balance_pdf` action on `LicenseDetailsViewSet` — multi-page PDF with license header, per-company utilisation, and signature block
- `bulk_balance_excel` — not PDF, but same data pipeline

**Key Files**: `backend/apps/license/views/balance_pdf.py` (or similar)

---

### docxtpl (DOCX Template Rendering)

**Purpose**: Render transfer letters by filling a Word DOCX template with dynamic data.

**How it works**:
1. Transfer letter templates (`.docx` files) uploaded via admin and stored in `MEDIA_ROOT`
2. Template uses Jinja2-style `{{ variable }}` syntax
3. `docxtpl` renders a filled `.docx` per party
4. Multiple rendered `.docx` files are zipped, or converted to PDF via LibreOffice headless

**Key Variables Available in Templates**:
- `company_name`, `address_line1`, `address_line2`
- `license_number`, `cif_value`, `sr_number` (per line)
- `date`, `exporter_name`, `port_code`

---

### OpenPyXL (Excel Export)

**Purpose**: Generate multi-sheet Excel files for license balance reports.

**Used in**:
- `bulk_balance_excel` — one sheet per license, cover sheet summary
- Sheet structure: license header (rows 1-3), data rows with BOE + allotment breakdown, totals row
- Column includes CIF INR (added via backend feature `RowDetails.cif_inr`)

---

### ExcelJS (Frontend Excel)

**Purpose**: Generate ledger Excel exports client-side without a server round-trip.

**Used in**: `frontend/src/utils/ledgerExport.ts`

---

### jsPDF (Frontend PDF)

**Purpose**: Generate ledger PDFs client-side from rendered table data.

**Used in**: `frontend/src/utils/ledgerExport.ts`

---

## OCR / PDF Parsing

### PyPDF + Pytesseract + pdf2image

**Purpose**: Extract structured data from scanned government-issued license PDFs.

**Pipeline**:
1. User uploads a PDF via `POST /api/licenses/parse-pdf/`
2. `pdf2image` converts PDF pages to images
3. `pytesseract` (Google Tesseract OCR) extracts text from images
4. Custom regex parsers extract:
   - License number
   - Dates (license date, expiry date, registration date)
   - Exporter name (fuzzy-matched against company master)
   - Port code (fuzzy-matched against port master)
   - Import items: serial number, product description, HS code, CIF value
5. Matched allotments and companies are resolved to DB IDs
6. Result returned as a suggested pre-fill JSON for user review

**Requirements**: Tesseract OCR must be installed on the server (`apt install tesseract-ocr`).

---

### pyzbar (QR Code Reading)

**Purpose**: Read QR codes embedded in some government documents.

**Used in**: Document verification workflows (when QR codes are present on scanned copies).

---

## Authentication Provider

No external OAuth/SSO provider. Authentication is fully managed internally via:
- Django custom `User` model
- SimpleJWT for token generation and refresh
- Django Groups for role management

---

## Email

No email integration configured in the codebase. Password resets (`PasswordReset.tsx` page exists) would require SMTP configuration via `EMAIL_BACKEND` in Django settings — this feature may be partially implemented or planned.

---

## Web Speech API (Browser)

**Purpose**: Voice input for task creation in `TaskDrawer.tsx`.

**Integration**: Browser-native `window.SpeechRecognition` / `window.webkitSpeechRecognition` — no external service. Works in Chrome/Edge; not supported in Firefox/Safari.

**Parsing**: Custom `parseVoiceCommand()` function extracts task title, assignee, and priority from spoken text using regex patterns.

---

## Multi-Server Sync (`sync-masters.sh`)

**Purpose**: Replicate master data from the canonical license-manager server to follower servers (labdhi, tractor).

**Tools Used**:
- `sshpass` — SSH with password for automation
- `scp` — file transfer between servers
- `python manage.py audit_masters` — canonical server exports JSON snapshot
- `python manage.py auto_import_masters` — followers import from snapshot

**Schedule**: Recommended via cron every 15 minutes:
```cron
*/15 * * * * cd /path/to/license-manager && bash sync-masters.sh --quiet >> /tmp/master-sync.log 2>&1
```

---

## Deployment Infrastructure

| Service | Software |
|---|---|
| Web Server | Gunicorn (WSGI) |
| Reverse Proxy | Nginx (assumed) |
| Process Manager | systemd (assumed) |
| SSL | Let's Encrypt (DuckDNS domains) |
| OS | Ubuntu (assumed from `apt`) |

---

## Python Dependencies Summary

| Package | Purpose |
|---|---|
| Django 6.0.4 | Web framework |
| djangorestframework 3.17.1 | REST API |
| djangorestframework-simplejwt 5.5.1 | JWT auth |
| django-filter | Advanced queryset filtering |
| django-cors-headers | CORS support |
| django-extensions | Developer tools |
| django-redis | Redis cache backend |
| celery | Async task queue |
| redis | Celery broker / result backend |
| psycopg | PostgreSQL driver (v3) |
| openpyxl | Excel file generation |
| reportlab | PDF generation |
| docxtpl | DOCX template rendering |
| pypdf | PDF text extraction |
| pillow | Image processing |
| pytesseract | OCR (Tesseract wrapper) |
| pdf2image | PDF → image for OCR |
| pyzbar | QR code reading |
| num2words | Number → words (for invoices) |
| python-dotenv | `.env` file loading |
