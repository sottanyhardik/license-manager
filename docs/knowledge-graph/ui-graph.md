# UI Graph

> Living document. Add routes/screens as frontend/ modules are implemented.

## Route Map

| Route | Component | Layout | Auth | Role | Status |
|---|---|---|---|---|---|
| /login | Login | AuthLayout | none | any | pending |
| / | Dashboard | AdminLayout | JWT | any | pending |
| /licenses | LicenseList | AdminLayout | JWT | license-viewer+ | done — Phase 3 |
| /licenses/:id | LicenseDetail | AdminLayout | JWT | license-viewer+ | done — Phase 3 |
| /allotments | AllotmentList | AdminLayout | JWT | allotment-viewer+ |
| /boe | BOEList | AdminLayout | JWT | boe-viewer+ |
| /trade | TradeList | AdminLayout | JWT | trade-viewer+ |
| /trade/new | TradeForm | AdminLayout | JWT | trade-manager |
| /reports/* | ReportPages | AdminLayout | JWT | report-viewer+ |
| /masters/companies | CompanyList | AdminLayout | JWT | any (write: superuser) |
| /masters/ports | PortList | AdminLayout | JWT | any (write: superuser) |
| /masters/:entity | MasterList (generic) | AdminLayout | JWT | any (write: superuser) |
| /tasks | TaskDrawer | AdminLayout | JWT | any |
| /settings | Settings | AdminLayout | JWT | any |
| * | NotFound | Minimal | none | any |

## Shared Components (frontend/src/shared/ui/)

> Populated as components are added via shadcn/ui CLI or custom-built.

| Component | Source | Status |
|---|---|---|
| Button | shadcn/ui | pending |
| Input | shadcn/ui | pending |
| Table | TanStack Table + shadcn/ui | pending |
| Dialog | shadcn/ui | pending |
| Toast | Sonner | pending |
| Skeleton | shadcn/ui | pending |
| Badge | shadcn/ui | pending |
| Card | shadcn/ui | pending |
| Dropdown | Radix UI via shadcn | pending |
| DatePicker | React Day Picker | pending |
| MasterSelect | features/masters (custom) | done — Phase 2 |
| MasterDataTable | features/masters (TanStack Table) | done — Phase 2 |

## State Management Strategy

- **Server state:** TanStack Query (all API data)
- **Auth state:** AuthContext (user, tokens, roles)
- **Form state:** React Hook Form + Zod
- **UI state:** local `useState` (modals, toggles) — no global store
- **Theme:** CSS variables via Tailwind v4 + shadcn/ui theming

## API → Component Map

| API Hook | Used By |
|---|---|
| useLicenses | LicenseList, Dashboard |
| useLicense | LicenseDetail, AllotmentForm, TradeForm |
| useLicenseItems | LicenseDetail (Import Items tab) |
| useLicenseBalance | LicenseBalancePanel |
| useLicenseItemUsage | LicenseImportItems (expand-row detail) |
| useCreateLicense, useUpdateLicense | LicenseFormModal |
| usePatchLicenseField | LicenseBalancePanel (inline editable fields) |
| useAllotments | AllotmentList |
| useBOEs | BOEList |
| useTrades | TradeList |
| useCompaniesAll, usePortsAll, useHSCodesAll, etc. | MasterSelect (any form that needs a master dropdown) |
| useCompanies, usePorts, useHSCodes, etc. | CompanyList, PortList, MasterList |
| useAuth | AuthContext, ProtectedRoute |
