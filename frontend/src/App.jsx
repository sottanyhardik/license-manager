import "./App.css";
import {BrowserRouter, Navigate, Route, Routes} from "react-router-dom";
import {lazy, Suspense, useEffect} from "react";
import {ToastContainer} from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

import {AuthProvider} from "./context/AuthContext";
import ProtectedRoute from "./routes/ProtectedRoute";
import AdminLayout from "./layout/AdminLayout";
import {PageLoader} from "./components/LoadingFallback";
import {lazyLoadWithRetry, preloadCriticalRoutes} from "./utils/lazyLoad";
import ErrorBoundary from "./components/ErrorBoundary";

import Login from "./pages/Login";
import Unauthorized from "./pages/errors/Unauthorized";
import NotFound from "./pages/errors/NotFound";

// Lazy load pages with retry logic
const Dashboard = lazyLoadWithRetry(() => import("./pages/Dashboard"));
const LicensePage = lazyLoadWithRetry(() => import("./pages/LicensePage"));
const Settings = lazyLoadWithRetry(() => import("./pages/Settings"));
const Profile = lazyLoadWithRetry(() => import("./pages/Profile"));
const MasterList = lazyLoadWithRetry(() => import("./pages/masters/MasterList"));
const MasterForm = lazyLoadWithRetry(() => import("./pages/masters/MasterForm"));
const AllotmentAction = lazyLoadWithRetry(() => import("./pages/AllotmentAction"));
const BOETransferLetter = lazyLoadWithRetry(() => import("./pages/BOETransferLetter"));

// Report pages - lazy load on demand
const SionE1 = lazy(() => import("./pages/reports/SionE1"));
const SionE5 = lazy(() => import("./pages/reports/SionE5"));
const SionE126 = lazy(() => import("./pages/reports/SionE126"));
const SionE132 = lazy(() => import("./pages/reports/SionE132"));
const ExpiringLicenses = lazy(() => import("./pages/reports/ExpiringLicenses"));
const ActiveLicenses = lazy(() => import("./pages/reports/ActiveLicenses"));
const ItemPivotReport = lazyLoadWithRetry(() => import("./pages/reports/ItemPivotReport"));
const ItemReport = lazyLoadWithRetry(() => import("./pages/reports/ItemReport"));

// Trade & Ledger Upload
const TradeForm = lazy(() => import("./pages/TradeForm"));
const LedgerCSVUpload = lazy(() => import("./pages/LedgerCSVUpload"));
const LedgerUpload = lazy(() => import("./pages/LedgerUpload"));
const LicenseLedger = lazy(() => import("./pages/LicenseLedger"));
const LicenseLedgerDetail = lazy(() => import("./pages/LicenseLedgerDetail"));



export default function App() {
    // Preload critical routes after initial load
    useEffect(() => {
        preloadCriticalRoutes({
            masterList: () => import("./pages/masters/MasterList"),
            itemReport: () => import("./pages/reports/ItemReport"),
            itemPivotReport: () => import("./pages/reports/ItemPivotReport")
        }, 3000); // Preload after 3 seconds
    }, []);

    return (
        <AuthProvider>
            <BrowserRouter>
                <ToastContainer
                    position="top-right"
                    autoClose={3000}
                    hideProgressBar={false}
                    newestOnTop
                    closeOnClick
                    rtl={false}
                    pauseOnFocusLoss
                    draggable
                    pauseOnHover
                />
                <ErrorBoundary>
                    <Suspense fallback={<PageLoader />}>
                        <Routes>

                            {/* Public */}
                            <Route path="/login" element={<Login/>}/>
                            <Route path="/401" element={<Unauthorized/>}/>

                            {/* Root redirect */}
                            <Route
                                path="/"
                                element={
                                    <ProtectedRoute>
                                        <Navigate to="/dashboard"/>
                                    </ProtectedRoute>
                                }
                            />

                            {/* Protected */}
                            <Route
                                path="/dashboard"
                                element={
                                    <ProtectedRoute>
                                        <AdminLayout>
                                            <Dashboard/>
                                        </AdminLayout>
                                    </ProtectedRoute>
                                }
                            />

                            {/* License CRUD Routes */}
                            <Route
                                path="/licenses"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/licenses/create"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/licenses/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            {/* Allotment CRUD Routes */}
                            <Route
                                path="/allotments"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/allotments/create"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/allotments/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/allotments/:id/allocate"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <AllotmentAction/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            {/* Reports Routes */}
                            
                            <Route
                                path="/reports/parle/sion-e1"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <SionE1/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/parle/sion-e5"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <SionE5/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/parle/sion-e126"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <SionE126/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/parle/sion-e132"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <SionE132/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/expiring-licenses"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <ExpiringLicenses/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/active-licenses"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <ActiveLicenses/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/item-pivot"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <ItemPivotReport/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/item-report"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <ItemReport/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            {/* Bill of Entry CRUD Routes */}
                            <Route
                                path="/bill-of-entries"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/bill-of-entries/create"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/bill-of-entries/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/bill-of-entries/:id/generate-transfer-letter"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <BOETransferLetter/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            {/* Trade CRUD Routes */}
                            <Route
                                path="/trades"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/trades/create"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <TradeForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/trades/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <TradeForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            {/* Incentive License CRUD Routes */}
                            <Route
                                path="/incentive-licenses"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/incentive-licenses/create"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/incentive-licenses/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/ledger-csv-upload"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <LedgerCSVUpload/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/ledger-upload"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <LedgerUpload/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/license-ledger"
                                element={
                                    <ProtectedRoute>
                                        <AdminLayout>
                                            <LicenseLedger/>
                                        </AdminLayout>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/license-ledger/:id"
                                element={
                                    <ProtectedRoute>
                                        <AdminLayout>
                                            <LicenseLedgerDetail/>
                                        </AdminLayout>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/settings"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <Settings/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/profile"
                                element={
                                    <ProtectedRoute>
                                        <AdminLayout>
                                            <Profile/>
                                        </AdminLayout>
                                    </ProtectedRoute>
                                }
                            />

                            {/* Master CRUD Routes */}
                            <Route
                                path="/masters/:entity"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/masters/:entity/create"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/masters/:entity/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        
                                    </ProtectedRoute>
                                }
                            />

                            {/* 404 */}
                            <Route path="*" element={<NotFound/>}/>
                        </Routes>
                    </Suspense>
                </ErrorBoundary>
            </BrowserRouter>
        </AuthProvider>
    );
}
