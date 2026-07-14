# UI Graph

> Living document. Add routes/screens as frontend/ modules are implemented.

## Route Map

| Route | Component | Layout | Auth | Role |
|---|---|---|---|---|
| /login | Login | AuthLayout | none | any |
| / | Dashboard | AdminLayout | JWT | any |
| /licenses | LicenseList | AdminLayout | JWT | license-viewer+ |
| /licenses/:id | LicenseDetail | AdminLayout | JWT | license-viewer+ |
| /allotments | AllotmentList | AdminLayout | JWT | allotment-viewer+ |
| /boe | BOEList | AdminLayout | JWT | boe-viewer+ |
| /trade | TradeList | AdminLayout | JWT | trade-viewer+ |
| /trade/new | TradeForm | AdminLayout | JWT | trade-manager |
| /reports/* | ReportPages | AdminLayout | JWT | report-viewer+ |
| /masters/* | MasterPages | AdminLayout | JWT | master-viewer+ |
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
| useAllotments | AllotmentList |
| useBOEs | BOEList |
| useTrades | TradeList |
| useMasters | All forms (company, port, HS code selectors) |
| useAuth | AuthContext, ProtectedRoute |
