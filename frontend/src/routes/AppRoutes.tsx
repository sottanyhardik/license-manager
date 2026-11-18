import { lazy, Suspense, type ReactElement } from "react";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";

import ProtectedRoute from "./ProtectedRoute";
import AdminLayout from "../layout/AdminLayout";
import { PageLoader } from "../components/LoadingFallback";
import { lazyLoadWithRetry } from "../utils/lazyLoad";


import Login from "../pages/Login";
import PasswordReset from "../pages/auth/PasswordReset";
import Unauthorized from "../pages/errors/Unauthorized";
import NotFound from "../pages/errors/NotFound";
import Forbidden from "../pages/Forbidden";
import {
    ROLES,
    ACCOUNTING_ROLES,
    REPORT_ROLES,
    ALLOTMENT_ROLES,
    BOE_LIST_ROLES,
    BOE_TRANSFER_LETTER_ROLES,
    INCENTIVE_LICENSE_ROLES,
    LEDGER_PACKAGE_READINESS_ROLES,
    LEDGER_READ_ROLES,
    LEDGER_UPLOAD_ROLES,
    LICENSE_OVERVIEW_ROLES,
    LICENSE_ROLES,
    RECONCILIATION_ISSUES_ROLES,
    RECONCILIATION_ROLES,
    TRADE_ROLES,
    USER_ADMIN_ROLES,
} from "./authorizationRoles";

const AccountingWorkspace = lazy(() => import("../pages/accounting/AccountingWorkspace"));

const UserList = lazyLoadWithRetry(() => import("../pages/admin/UserList"));
const UserForm = lazyLoadWithRetry(() => import("../pages/admin/UserForm"));
const ActivityLog = lazyLoadWithRetry(() => import("../pages/admin/ActivityLog"));

const Dashboard = lazyLoadWithRetry(() => import("../pages/Dashboard"));
const Settings = lazyLoadWithRetry(() => import("../pages/Settings"));
const Profile = lazyLoadWithRetry(() => import("../pages/Profile"));
const MasterList = lazyLoadWithRetry(() => import("../pages/masters/MasterList"));
const MasterForm = lazyLoadWithRetry(() => import("../pages/masters/MasterForm"));
const MastersHub = lazyLoadWithRetry(() => import("../pages/masters/MastersHub"));
const AllotmentAction = lazyLoadWithRetry(() => import("../pages/AllotmentAction"));
const BOETransferLetter = lazyLoadWithRetry(() => import("../pages/BOETransferLetter"));

const SionE1 = lazy(() => import("../pages/reports/SionE1"));
const SionE5 = lazy(() => import("../pages/reports/SionE5"));
const SionE126 = lazy(() => import("../pages/reports/SionE126"));
const SionE132 = lazy(() => import("../pages/reports/SionE132"));
const ExpiringLicenses = lazy(() => import("../pages/reports/ExpiringLicenses"));
const ActiveLicenses = lazy(() => import("../pages/reports/ActiveLicenses"));
const DownloadLicense = lazy(() => import("../pages/reports/DownloadLicense"));
const ItemPivotReport = lazyLoadWithRetry(() => import("../pages/reports/ItemPivotReport"));
const ItemReport = lazyLoadWithRetry(() => import("../pages/reports/ItemReport"));
const PlannedReport = lazyLoadWithRetry(() => import("../pages/reports/PlannedReport"));
const LicensePurchaseProfitReport = lazyLoadWithRetry(() => import("../pages/reports/LicensePurchaseProfitReport"));

const TradeForm = lazy(() => import("../pages/TradeForm"));
const ReconciliationPanel = lazyLoadWithRetry(() => import("../pages/ReconciliationPanel"));
const ReconciliationIssues = lazyLoadWithRetry(() => import("../pages/ReconciliationIssues"));
const LedgerUpload = lazy(() => import("../pages/LedgerUpload"));
const LicenseLedger = lazy(() => import("../pages/LicenseLedger"));
const LicenseLedgerDetail = lazy(() => import("../pages/LicenseLedgerDetail"));
const LicenseLedgerPackageReadiness = lazyLoadWithRetry(() => import("../pages/LicenseLedgerPackageReadiness"));
const LicenseDownloadRequests = lazyLoadWithRetry(() => import("../pages/LicenseDownloadRequests"));
const LicenseDownloadRequestDetail = lazyLoadWithRetry(() => import("../pages/LicenseDownloadRequestDetail"));
const BoeDetailPage = lazy(() => import("../pages/bill-of-entry/BoeDetailPage"));
const LicenseOverviewPage = lazy(() => import("../pages/license-overview/LicenseOverviewPage"));
const LicensePlanningWorkspace = lazy(() => import("../pages/planning/LicensePlanningWorkspace"));
const PDFViewer = lazy(() => import("../pages/PDFViewer"));

/** Old `/licenses/:id/balance` bookmarks/links redirect to the new Overview page — explicit absolute target (built from the route's own `:id` param) rather than a relative `Navigate` path, so the destination is unambiguous. */
function RedirectToLicenseOverview() {
    const { id } = useParams<{ id: string }>();
    const location = useLocation();
    return <Navigate to={`/licenses/${id}/overview${location.search}${location.hash}`} replace />;
}

const REPORT_ROUTES: [string, ReactElement][] = [
    ["/reports/parle/sion-e1", <SionE1 />],
    ["/reports/parle/sion-e5", <SionE5 />],
    ["/reports/parle/sion-e126", <SionE126 />],
    ["/reports/parle/sion-e132", <SionE132 />],
    ["/reports/expiring-licenses", <ExpiringLicenses />],
    ["/reports/active-licenses", <ActiveLicenses />],
    ["/reports/download-license", <DownloadLicense />],
    ["/reports/item-pivot", <ItemPivotReport />],
    ["/reports/item-report", <ItemReport />],
    ["/reports/planned-report", <PlannedReport />],
    ["/reports/license-purchase-profit", <LicensePurchaseProfitReport />],
];

export default function AppRoutes() {
    return (
        <Suspense fallback={<PageLoader />}>
            <Routes>
                {/* Public */}
                <Route path="/login" element={<Login />} />
                <Route path="/forgot-password" element={<PasswordReset />} />
                <Route path="/401" element={<Unauthorized />} />
                <Route path="/403" element={<Forbidden />} />

                {/* Root redirect */}
                <Route
                    path="/"
                    element={
                        <ProtectedRoute>
                            <Navigate to="/dashboard" />
                        </ProtectedRoute>
                    }
                />

                {/* Dashboard */}
                <Route
                    path="/dashboard"
                    element={
                        <ProtectedRoute>
                            <AdminLayout>
                                <Dashboard />
                            </AdminLayout>
                        </ProtectedRoute>
                    }
                />

                {/* License CRUD */}
                <Route path="/licenses" element={
                    <ProtectedRoute requiredAnyRole={LICENSE_ROLES}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/licenses/create" element={
                    <ProtectedRoute requiredRole={ROLES.LICENSE_MANAGER}>
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/licenses/:id/edit" element={
                    <ProtectedRoute requiredRole={ROLES.LICENSE_MANAGER}>
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/planning" element={
                    <ProtectedRoute requiredRole={ROLES.LICENSE_MANAGER}>
                        <AdminLayout><LicensePlanningWorkspace /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Allotment CRUD */}
                <Route path="/allotments" element={
                    <ProtectedRoute requiredAnyRole={ALLOTMENT_ROLES}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/allotments/create" element={
                    <ProtectedRoute requiredRole={ROLES.ALLOTMENT_MANAGER}>
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/allotments/:id/edit" element={
                    <ProtectedRoute requiredRole={ROLES.ALLOTMENT_MANAGER}>
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/allotments/:id/allocate" element={
                    <ProtectedRoute requiredRole={ROLES.ALLOTMENT_MANAGER}>
                        <AdminLayout><AllotmentAction /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Reports */}
                {REPORT_ROUTES.map(([path, element]) => (
                    <Route key={path} path={path} element={
                        <ProtectedRoute requiredAnyRole={REPORT_ROLES}>
                            <AdminLayout>{element}</AdminLayout>
                        </ProtectedRoute>
                    } />
                ))}

                {/* Bill of Entry CRUD */}
                <Route path="/bill-of-entries" element={
                    <ProtectedRoute requiredAnyRole={BOE_LIST_ROLES}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/bill-of-entries/create" element={
                    <ProtectedRoute requiredRole={ROLES.BOE_MANAGER}>
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                {/* Static `/create` outranks the dynamic `:id`; `/:id/edit` has more segments. */}
                <Route path="/bill-of-entries/:id" element={
                    <ProtectedRoute requiredAnyRole={BOE_LIST_ROLES}>
                        <AdminLayout><BoeDetailPage /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/bill-of-entries/:id/edit" element={
                    <ProtectedRoute requiredRole={ROLES.BOE_MANAGER}>
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/bill-of-entries/:id/generate-transfer-letter" element={
                    <ProtectedRoute requiredAnyRole={BOE_TRANSFER_LETTER_ROLES}>
                        <AdminLayout><BOETransferLetter /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Trade CRUD */}
                <Route path="/accounting/*" element={
                    <ProtectedRoute requiredAnyRole={ACCOUNTING_ROLES}>
                        <AdminLayout><AccountingWorkspace /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/trades" element={
                    <ProtectedRoute requiredAnyRole={TRADE_ROLES}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/trades/create" element={
                    <ProtectedRoute requiredRole={ROLES.TRADE_MANAGER}>
                        <AdminLayout><TradeForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/trades/:id/edit" element={
                    <ProtectedRoute requiredRole={ROLES.TRADE_MANAGER}>
                        <AdminLayout><TradeForm /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Reconciliation */}
                <Route path="/reconciliation" element={
                    <ProtectedRoute requiredAnyRole={RECONCILIATION_ROLES}>
                        <AdminLayout><ReconciliationPanel /></AdminLayout>
                    </ProtectedRoute>
                } />
                {/* Reconciliation Issues — read-only portfolio-wide discovery companion to
                    /reconciliation above. Gated on ReconciliationPermission.read_roles
                    (backend/apps/accounts/permissions.py) since it only reads. */}
                <Route path="/reconciliation-issues" element={
                    <ProtectedRoute requiredAnyRole={RECONCILIATION_ISSUES_ROLES}>
                        <AdminLayout><ReconciliationIssues /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Incentive License CRUD */}
                {/* List + record opened inline in its row (`/incentive-licenses/:id`); static `/create` outranks it. */}
                <Route path="/incentive-licenses/:id?" element={
                    <ProtectedRoute requiredAnyRole={INCENTIVE_LICENSE_ROLES}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/incentive-licenses/create" element={
                    <ProtectedRoute requiredRole={ROLES.INCENTIVE_LICENSE_MANAGER}>
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                {/* Old edit-page URL: the list with the record open on its Edit tab (shown to INCENTIVE_LICENSE_MANAGER
                    only; the API enforces IncentiveLicensePermission on save). */}
                <Route path="/incentive-licenses/:id/edit" element={
                    <ProtectedRoute requiredAnyRole={INCENTIVE_LICENSE_ROLES}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Ledger */}
                <Route path="/ledger-upload" element={
                    <ProtectedRoute requiredAnyRole={LEDGER_UPLOAD_ROLES}>
                        <AdminLayout><LedgerUpload /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/license-ledger" element={
                    <ProtectedRoute requiredAnyRole={LEDGER_READ_ROLES}>
                        <AdminLayout><LicenseLedger /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/license-ledger/download-requests" element={
                    <ProtectedRoute requiredAnyRole={LEDGER_READ_ROLES}>
                        <AdminLayout><LicenseDownloadRequests /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/license-ledger/download-requests/:requestId" element={
                    <ProtectedRoute requiredAnyRole={LEDGER_READ_ROLES}>
                        <AdminLayout><LicenseDownloadRequestDetail /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/license-ledger/package-readiness/:jobId" element={
                    <ProtectedRoute requiredAnyRole={LEDGER_PACKAGE_READINESS_ROLES}>
                        <AdminLayout><LicenseLedgerPackageReadiness /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/license-ledger/:licenseId/:itemId" element={
                    <ProtectedRoute requiredAnyRole={LEDGER_READ_ROLES}>
                        <AdminLayout><LicenseLedgerDetail /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/license-ledger/:licenseId" element={
                    <ProtectedRoute requiredAnyRole={LEDGER_READ_ROLES}>
                        <AdminLayout><LicenseLedgerDetail /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* License Overview dashboard — replaces the old Balance Workspace */}
                <Route path="/licenses/:id/overview" element={
                    <ProtectedRoute requiredAnyRole={LICENSE_OVERVIEW_ROLES}>
                        <AdminLayout><LicenseOverviewPage /></AdminLayout>
                    </ProtectedRoute>
                } />
                {/* Bare `/licenses/:id` -> workspace, same guard as /overview. Static `/licenses/create` outranks this dynamic segment; `/:id/edit` has more segments. */}
                <Route path="/licenses/:id" element={
                    <ProtectedRoute requiredAnyRole={LICENSE_OVERVIEW_ROLES}>
                        <RedirectToLicenseOverview />
                    </ProtectedRoute>
                } />
                {/* Old bookmarks/links to the retired Balance Workspace redirect here. */}
                <Route path="/licenses/:id/balance" element={<RedirectToLicenseOverview />} />

                {/* PDF Viewer */}
                <Route path="/pdf-viewer" element={
                    <ProtectedRoute>
                        <PDFViewer />
                    </ProtectedRoute>
                } />

                {/* Settings + Profile */}
                <Route path="/settings" element={
                    <ProtectedRoute requireSuperuser>
                        <AdminLayout><Settings /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/profile" element={
                    <ProtectedRoute>
                        <AdminLayout><Profile /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Master CRUD */}
                <Route path="/masters" element={
                    <ProtectedRoute>
                        <AdminLayout><MastersHub /></AdminLayout>
                    </ProtectedRoute>
                } />
                {/* One route for the list and `/masters/:entity/:id` (record opened inline in its row), so moving
                    between them never remounts the list: search, filters, page and scroll are kept. Static
                    `/create` and the longer `/:id/edit` outrank the optional segment. */}
                <Route path="/masters/:entity/:id?" element={
                    <ProtectedRoute>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/masters/:entity/create" element={
                    <ProtectedRoute requiredAnyRole={USER_ADMIN_ROLES}>
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                {/* Old edit-page URL: the list with the record open on its Edit tab (no standalone edit page). The Edit
                    tab itself is shown only to writers and the API enforces permissions on save. */}
                <Route path="/masters/:entity/:id/edit" element={
                    <ProtectedRoute>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Admin — Users */}
                <Route path="/admin/users" element={
                    <ProtectedRoute requiredAnyRole={USER_ADMIN_ROLES}>
                        <AdminLayout><UserList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/admin/users/create" element={
                    <ProtectedRoute requiredAnyRole={USER_ADMIN_ROLES}>
                        <AdminLayout><UserForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/admin/users/:id/edit" element={
                    <ProtectedRoute requiredAnyRole={USER_ADMIN_ROLES}>
                        <AdminLayout><UserForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/admin/activity-log" element={
                    <ProtectedRoute requiredAnyRole={USER_ADMIN_ROLES}>
                        <AdminLayout><ActivityLog /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* 404 */}
                <Route path="*" element={<NotFound />} />
            </Routes>
        </Suspense>
    );
}
