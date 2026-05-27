import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "./ProtectedRoute";
import AdminLayout from "../layout/AdminLayout";
import { PageLoader } from "../components/LoadingFallback";
import { lazyLoadWithRetry, preloadCriticalRoutes } from "../utils/lazyLoad";

import Login from "../pages/Login";
import Unauthorized from "../pages/errors/Unauthorized";
import NotFound from "../pages/errors/NotFound";
import Forbidden from "../pages/Forbidden";

const UserList = lazyLoadWithRetry(() => import("../pages/admin/UserList"));
const UserForm = lazyLoadWithRetry(() => import("../pages/admin/UserForm"));
const ActivityLog = lazyLoadWithRetry(() => import("../pages/admin/ActivityLog"));

const Dashboard = lazyLoadWithRetry(() => import("../pages/Dashboard"));
const Settings = lazyLoadWithRetry(() => import("../pages/Settings"));
const Profile = lazyLoadWithRetry(() => import("../pages/Profile"));
const MasterList = lazyLoadWithRetry(() => import("../pages/masters/MasterList"));
const MasterForm = lazyLoadWithRetry(() => import("../pages/masters/MasterForm"));
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

const TradeForm = lazy(() => import("../pages/TradeForm"));
const LedgerUpload = lazy(() => import("../pages/LedgerUpload"));
const LicenseLedger = lazy(() => import("../pages/LicenseLedger"));
const LicenseLedgerDetail = lazy(() => import("../pages/LicenseLedgerDetail"));
const PDFViewer = lazy(() => import("../pages/PDFViewer"));

const REPORT_ROLES = [
    "REPORT_VIEWER",
    "LICENSE_MANAGER",
    "LICENSE_VIEWER",
    "TRADE_MANAGER",
    "TRADE_VIEWER",
    "ALLOTMENT_MANAGER",
    "BOE_MANAGER",
    "INCENTIVE_LICENSE_MANAGER",
];

const REPORT_ROUTES = [
    ["/reports/parle/sion-e1", <SionE1 />],
    ["/reports/parle/sion-e5", <SionE5 />],
    ["/reports/parle/sion-e126", <SionE126 />],
    ["/reports/parle/sion-e132", <SionE132 />],
    ["/reports/expiring-licenses", <ExpiringLicenses />],
    ["/reports/active-licenses", <ActiveLicenses />],
    ["/reports/download-license", <DownloadLicense />],
    ["/reports/item-pivot", <ItemPivotReport />],
    ["/reports/item-report", <ItemReport />],
];

export default function AppRoutes() {
    useEffect(() => {
        preloadCriticalRoutes(
            {
                masterList: () => import("../pages/masters/MasterList"),
                itemReport: () => import("../pages/reports/ItemReport"),
                itemPivotReport: () => import("../pages/reports/ItemPivotReport"),
            },
            3000,
        );
    }, []);

    return (
        <Suspense fallback={<PageLoader />}>
            <Routes>
                {/* Public */}
                <Route path="/login" element={<Login />} />
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
                    <ProtectedRoute requiredAnyRole={["LICENSE_MANAGER", "LICENSE_VIEWER"]}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/licenses/create" element={
                    <ProtectedRoute requiredRole="LICENSE_MANAGER">
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/licenses/:id/edit" element={
                    <ProtectedRoute requiredRole="LICENSE_MANAGER">
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Allotment CRUD */}
                <Route path="/allotments" element={
                    <ProtectedRoute requiredAnyRole={["ALLOTMENT_MANAGER", "ALLOTMENT_VIEWER"]}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/allotments/create" element={
                    <ProtectedRoute requiredRole="ALLOTMENT_MANAGER">
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/allotments/:id/edit" element={
                    <ProtectedRoute requiredRole="ALLOTMENT_MANAGER">
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/allotments/:id/allocate" element={
                    <ProtectedRoute requiredRole="ALLOTMENT_MANAGER">
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
                    <ProtectedRoute requiredAnyRole={["BOE_MANAGER", "BOE_VIEWER", "TL_GENERATE", "ACCOUNT_ACCESS"]}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/bill-of-entries/create" element={
                    <ProtectedRoute requiredRole="BOE_MANAGER">
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/bill-of-entries/:id/edit" element={
                    <ProtectedRoute requiredRole="BOE_MANAGER">
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/bill-of-entries/:id/generate-transfer-letter" element={
                    <ProtectedRoute requiredAnyRole={["BOE_MANAGER", "BOE_VIEWER", "TL_GENERATE"]}>
                        <AdminLayout><BOETransferLetter /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Trade CRUD */}
                <Route path="/trades" element={
                    <ProtectedRoute requiredAnyRole={["TRADE_MANAGER", "TRADE_VIEWER"]}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/trades/create" element={
                    <ProtectedRoute requiredRole="TRADE_MANAGER">
                        <AdminLayout><TradeForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/trades/:id/edit" element={
                    <ProtectedRoute requiredRole="TRADE_MANAGER">
                        <AdminLayout><TradeForm /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Incentive License CRUD */}
                <Route path="/incentive-licenses" element={
                    <ProtectedRoute requiredAnyRole={["INCENTIVE_LICENSE_MANAGER", "INCENTIVE_LICENSE_VIEWER"]}>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/incentive-licenses/create" element={
                    <ProtectedRoute requiredRole="INCENTIVE_LICENSE_MANAGER">
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/incentive-licenses/:id/edit" element={
                    <ProtectedRoute requiredRole="INCENTIVE_LICENSE_MANAGER">
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Ledger */}
                <Route path="/ledger-upload" element={
                    <ProtectedRoute requiredAnyRole={["LICENSE_MANAGER", "LEDGER_MANAGER"]}>
                        <AdminLayout><LedgerUpload /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/license-ledger" element={
                    <ProtectedRoute requiredAnyRole={["LICENSE_MANAGER", "TRADE_MANAGER", "TRADE_VIEWER", "LEDGER_MANAGER"]}>
                        <AdminLayout><LicenseLedger /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/license-ledger/:id/:companyId?" element={
                    <ProtectedRoute requiredAnyRole={["LICENSE_MANAGER", "TRADE_MANAGER", "TRADE_VIEWER", "LEDGER_MANAGER"]}>
                        <AdminLayout><LicenseLedgerDetail /></AdminLayout>
                    </ProtectedRoute>
                } />

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
                <Route path="/masters/:entity" element={
                    <ProtectedRoute>
                        <AdminLayout><MasterList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/masters/:entity/create" element={
                    <ProtectedRoute requireSuperuser>
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/masters/:entity/:id/edit" element={
                    <ProtectedRoute requireSuperuser>
                        <AdminLayout><MasterForm /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* Admin — Users */}
                <Route path="/admin/users" element={
                    <ProtectedRoute requiredAnyRole={["USER_MANAGER"]}>
                        <AdminLayout><UserList /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/admin/users/create" element={
                    <ProtectedRoute requiredAnyRole={["USER_MANAGER"]}>
                        <AdminLayout><UserForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/admin/users/:id/edit" element={
                    <ProtectedRoute requiredAnyRole={["USER_MANAGER"]}>
                        <AdminLayout><UserForm /></AdminLayout>
                    </ProtectedRoute>
                } />
                <Route path="/admin/activity-log" element={
                    <ProtectedRoute requiredAnyRole={["USER_MANAGER"]}>
                        <AdminLayout><ActivityLog /></AdminLayout>
                    </ProtectedRoute>
                } />

                {/* 404 */}
                <Route path="*" element={<NotFound />} />
            </Routes>
        </Suspense>
    );
}
