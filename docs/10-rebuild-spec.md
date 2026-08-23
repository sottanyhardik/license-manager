# 10 — Rebuild Specification

This document contains everything an AI or developer needs to rebuild License Manager from scratch. Read docs 01–09 first for full context.

---

## Tech Stack

| Layer | Exact Versions | Notes |
|---|---|---|
| **Frontend** | React 19.2, TypeScript 5, Vite 6, Rolldown | |
| **CSS** | Tailwind CSS v4 (`@tailwindcss/vite` plugin), CSS-first config | No tailwind.config.js |
| **UI Components** | shadcn/ui (Radix UI primitives), lucide-react icons | |
| **Animation** | Framer Motion 12 | |
| **Routing** | React Router v7 | |
| **HTTP Client** | Axios | With interceptors for JWT, deduplication, refresh |
| **Forms** | React Hook Form + react-datepicker + react-select + react-select/async | |
| **Notifications** | react-toastify + Sonner | |
| **Excel (FE)** | ExcelJS | |
| **PDF (FE)** | jsPDF | |
| **Backend** | Django 6.0.4, Python 3.11+ | |
| **API** | Django REST Framework 3.17.1 | |
| **Auth** | SimpleJWT 5.5.1 with rotation + blacklist | |
| **Database** | PostgreSQL 15+ | |
| **ORM** | Django ORM (psycopg 3) | |
| **Async** | Celery 5 + Redis | |
| **PDF (BE)** | ReportLab, docxtpl, PyPDF | |
| **OCR** | Pytesseract + pdf2image + pyzbar | |
| **Excel (BE)** | OpenPyXL | |

---

## Project Structure

```
license-manager/
├── backend/
│   ├── lmanagement/          # Django project (settings, urls, wsgi)
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── celery.py
│   ├── apps/
│   │   ├── accounts/         # Custom User + JWT auth
│   │   ├── core/             # Masters: company, port, HS code, SION, exchange rates
│   │   ├── license/          # DFIA + incentive licenses, ledger, reports
│   │   ├── bill_of_entry/    # BOE header + row details
│   │   ├── allotment/        # Allotment + items
│   │   ├── trade/            # Trade invoices + lines + payments
│   │   └── tasks/            # Internal workflow tasks
│   ├── api_utils/            # Shared mixins, filters, pagination
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/              # Axios instance + per-entity API modules
│   │   ├── components/       # Shared React components + shadcn/ui primitives
│   │   ├── context/          # AuthContext, ThemeContext, ToastContext
│   │   ├── hooks/            # useFileUpload, useBackButton, useSpeechRecognition
│   │   ├── layout/           # AdminLayout, TopNav, Sidebar
│   │   ├── pages/            # Page components (one per route)
│   │   │   ├── masters/      # MasterList + MasterForm (generic for all entities)
│   │   │   ├── reports/      # ItemPivotReport, ItemReport, SionNormReport, etc.
│   │   │   ├── admin/        # UserList, UserForm, ActivityLog
│   │   │   └── ...
│   │   ├── routes/           # AppRoutes.tsx + config.ts (nav config)
│   │   ├── styles/           # tailwind.css (token bridge), theme/tabler.css
│   │   ├── theme/            # tokens.ts (design tokens)
│   │   ├── types/            # index.ts (domain interfaces)
│   │   └── utils/            # dateFormatter, numberFormatter, ledgerExport, etc.
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── scripts/maintenance/sync-masters.sh           # Cross-server master data sync
└── CLAUDE.md
```

---

## Step-by-Step Rebuild Order

### Phase 1: Backend Foundation

1. **Django project setup**
   - Create project: `django-admin startproject lmanagement`
   - Configure `settings.py`: database (PostgreSQL), installed apps, middleware, CORS, JWT
   - Add `DisableCSRFForAPIMiddleware` for `/api/` paths
   - Add `ActivityLogMiddleware`

2. **Custom User model** (`apps.accounts`)
   - Extend `AbstractBaseUser + PermissionsMixin`
   - Fields: `username`, `email`, `first_name`, `last_name`, `is_staff`, `is_active`, `date_joined`, `avatar`
   - Override `groups` and `user_permissions` with custom `related_name` to avoid auth.User clash
   - Role helper methods: `has_role()`, `has_any_role()`, `get_role_codes()`
   - Set `AUTH_USER_MODEL = 'accounts.User'` in settings **before first migration**

3. **Abstract AuditModel** (`apps.core` or `api_utils`)
   - Fields: `created_on`, `modified_on`, `created_by` FK, `modified_by` FK
   - Thread-local middleware to auto-populate `created_by`/`modified_by`

4. **JWT Authentication**
   - `rest_framework_simplejwt` with ROTATE_REFRESH_TOKENS, BLACKLIST_AFTER_ROTATION
   - Custom `LoginView` returning `{access, refresh, user}` (user serialized with roles)
   - `LogoutView` blacklisting refresh token
   - `MeView` (RetrieveUpdate for current user profile)

5. **Core master data models**
   - `CompanyModel`, `PortModel`, `HSCodeModel`, `SionNormClassModel`, `ItemNameModel`
   - `ExchangeRateModel`, `SchemeCode`, `NotificationNumber`, `PurchaseStatus`
   - `TransferLetterModel` (template file reference)
   - Register all as DRF `ModelViewSet` with standard CRUD

### Phase 2: License Module

6. **License models** (most complex — do this carefully)
   - `LicenseDetailsModel` — main header
   - `LicenseImportItemsModel` — per-item with `available_quantity`, `debited_quantity`, `allotted_quantity`
   - `LicenseExportItemModel` — export entitlement
   - OneToOne sub-tables: `LicenseBalance`, `LicenseFlags`, `LicenseOwnership`, `LicenseNotes`
   - `LicenseDocumentModel`
   - `LicenseTransferModel`
   - `IncentiveLicense`

7. **License signals**
   - `post_save` on `LicenseDetailsModel` → auto-create all OneToOne sub-tables
   - `post_save` on `LicenseImportItemsModel` → update `LicenseBalance.balance_cif`

8. **License ViewSet** (`LicenseDetailsViewSet`)
   - Custom `get_object()` supporting both pk and license_number lookup
   - `nested_items` action (lazy-loaded on demand)
   - `item_usage` action
   - `balance_pdf` action (ReportLab)
   - `bulk_balance_excel` action (OpenPyXL, CIF INR column from `RowDetails.cif_inr`)
   - `parse_pdf` action (OCR pipeline)

### Phase 3: BOE + Allotment + Trade

9. **BOE models** (`apps.bill_of_entry`)
   - `BillOfEntryModel` header
   - `RowDetails` with `frozen`, `is_dispute` flags
   - `post_save/delete` on `RowDetails` → update `LicenseImportItemsModel.debited_quantity`

10. **Allotment models** (`apps.allotment`)
    - `AllotmentModel`, `AllotmentItems`
    - `post_save/delete` on `AllotmentItems` → update `LicenseImportItemsModel.allotted_quantity`

11. **Trade models** (`apps.trade`)
    - `LicenseTrade`, `LicenseTradeLine`, `IncentiveTradeLine`, `LicenseTradePayment`
    - Auto invoice number generation per FY
    - `linked_trade` self-FK for paired trades

12. **Transfer Letter Generation**
    - `generate-transfer-letter` custom action on allotment, BOE, trade ViewSets
    - docxtpl renders DOCX from template + context
    - Output: ZIP of DOCXs, combined PDF (via LibreOffice headless), or inline PDF

### Phase 4: Async + Reports

13. **Celery setup**
    - `celery.py` in Django project
    - `process_single_license` task for ledger upload
    - `LedgerUploadView` + `LedgerTaskStatusView` 

14. **Reports**
    - `DashboardDataView` — multi-model aggregation, role-filtered, cached
    - `LicenseLedgerViewSet` — read-only, per-company transaction view
    - `ExpiringLicensesViewSet`, `ActiveLicensesViewSet`
    - `ItemPivotViewSet`, `ItemReportViewSet`
    - `InventoryBalanceViewSet`

15. **Management commands**
    - `audit_masters` — JSON snapshot of all master tables
    - `auto_import_masters` — idempotent import with conflict resolution
    - `update_license_expiry` — nightly flag refresh

### Phase 5: Tasks + Activity Log

16. **Tasks** (`apps.tasks`)
    - `Task`, `TaskRemark` models
    - `TaskViewSet` with `complete`, `reject`, `reopen`, `remarks`, `assignable_users` actions
    - Visibility filtered by creator/assignee

17. **Activity Log**
    - `ActivityLog` model
    - `ActivityLogMiddleware` — capture every HTTP request
    - `ActivityLogViewSet` — read-only, superuser only

---

## Critical Implementation Notes

### 1. Balance Materialisation (Do Not Skip)
Balances are NOT computed on read. They are materialised by signals. Any rebuild MUST implement the signal chain:
```
RowDetails save/delete → debited_quantity on import item
AllotmentItems save/delete → allotted_quantity on import item
ImportItem save → balance_cif on LicenseBalance
```
Missing any of these links will produce stale balances.

### 2. OneToOne Sub-Tables Pattern
```python
# In signal:
@receiver(post_save, sender=LicenseDetailsModel)
def create_license_subtables(sender, instance, created, **kwargs):
    if created:
        LicenseBalance.objects.get_or_create(license=instance)
        LicenseFlags.objects.get_or_create(license=instance)
        LicenseOwnership.objects.get_or_create(license=instance)
        LicenseNotes.objects.get_or_create(license=instance)
```

### 3. JWT Logout Must Blacklist
```python
class LogoutView(APIView):
    def post(self, request):
        RefreshToken(request.data['refresh']).blacklist()
        return Response(status=204)
```

### 4. Axios Refresh Queue (Frontend)
```typescript
// On 401: queue all in-flight requests, send ONE refresh, replay all
let isRefreshing = false;
let failedQueue: Array<{resolve, reject}> = [];

axios.interceptors.response.use(null, async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
        if (isRefreshing) {
            return new Promise((resolve, reject) => failedQueue.push({resolve, reject}));
        }
        isRefreshing = true;
        try {
            const {data} = await axios.post('/api/auth/refresh/', {refresh: getRefreshToken()});
            setAccessToken(data.access);
            processQueue(null, data.access);
            return axios(error.config);
        } catch (err) {
            processQueue(err, null);
            logout();
        } finally {
            isRefreshing = false;
        }
    }
    return Promise.reject(error);
});
```

### 5. MasterForm is Generic
`MasterForm.tsx` and `MasterList.tsx` are **generic** — they work for ALL entity types (licenses, allotments, BOE, trades, companies, etc.) driven by metadata fetched from the API. The backend provides field definitions, nested field arrays, and validation rules per entity type. This is the most complex frontend component.

### 6. Ledger Upload Frozen Rows
When creating `RowDetails` via ledger upload, always set `frozen=True`. Provide a `is_dispute=True` fallback when no matching import item exists — never silently drop rows.

### 7. Financial Year Calculation
```python
def get_financial_year(date):
    if date.month >= 4:  # April onwards = new FY
        return date.year
    return date.year - 1  # Jan-Mar belongs to previous FY start year
```

---

## Frontend Component Architecture

### Key Components to Implement

| Component | Purpose | Complexity |
|---|---|---|
| `MasterList.tsx` | Generic CRUD list for any entity | Very High |
| `MasterForm.tsx` | Generic CRUD form with nested arrays | Very High |
| `NestedFieldArray.tsx` | Inline table editor for sub-items | High |
| `AccordionTable.tsx` | Expandable table with nested detail | High |
| `TransferLetterForm.tsx` | Multi-party letter builder | High |
| `AllotmentAction.tsx` | Allotment detail + line item search | High |
| `LicenseLedger.tsx` | Filtered ledger with company picker | Medium |
| `TaskDrawer.tsx` | Slide-in panel with voice input | Medium |
| `HybridSelect.tsx` | FK picker (async or static choices) | Medium |
| `AdvancedFilter.tsx` | Multi-field filter panel | Medium |
| `CommandPalette.tsx` | Cmd+K quick navigation | Medium |
| `DataPagination.tsx` | Server-side pagination controls | Low |

### Design System

- **Token-first CSS**: All colours/spacing via CSS custom properties (`--tb-brand`, `--background`, etc.)
- **shadcn/ui primitives**: Button, Card, Input, Label, Dialog, Tooltip, Tabs, Select, Checkbox, Switch, Textarea, Badge, Skeleton, Separator, Sonner
- **Dark mode**: `[data-theme="dark"]` on `<html>` element via ThemeContext
- **Typography**: System font stack via Tailwind preflight
- **Icons**: lucide-react only (no bootstrap-icons)

---

## Environment Variables

```bash
# Django
DJANGO_SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
DATABASE_URL=postgresql://user:pass@host/dbname
REDIS_URL=redis://localhost:6379/0
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000

# Vite (Frontend)
VITE_API_URL=https://yourdomain.com
```

---

## Data Migration Considerations

When migrating an existing installation:
1. Run migrations in order: `accounts` → `core` → `license` → `bill_of_entry` → `allotment` → `trade` → `tasks`
2. After initial migration, run `python manage.py populate_license_items` if import item data needs reconstruction
3. Run `python manage.py update_license_expiry` to set initial `is_expired` flags
4. Run `python manage.py rebuild_migrations` only if squashing is needed (production databases should not require this)

---

## Acceptance Criteria for a Complete Rebuild

- [ ] User can log in/out with JWT; tokens auto-refresh; idle 30min → logout
- [ ] All 13 feature areas (F-01 through F-13) are functional per feature spec
- [ ] License balance materialises correctly via signal chain
- [ ] Ledger upload processes CSV/HTM files async via Celery with live progress
- [ ] Transfer letters generate valid DOCX/PDF output
- [ ] OCR parse pre-fills license fields from scanned PDF
- [ ] Balance PDF and Excel export work correctly including CIF INR column
- [ ] Dashboard shows correct KPIs with role filtering
- [ ] All 15 roles enforced correctly; superuser bypasses all checks
- [ ] Activity log captures every HTTP request
- [ ] Master sync command works across servers
- [ ] Voice task creation parses title + assignee + priority from speech
- [ ] Dark mode toggle persists across sessions
- [ ] Build: `npm run build` passes, TypeScript 0 errors, ESLint 0 errors
