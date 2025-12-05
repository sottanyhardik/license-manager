import "./App.css";
import {BrowserRouter, Navigate, Route, Routes} from "react-router-dom";
import {lazy, Suspense} from "react";
import {ToastContainer} from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

import {AuthProvider} from "./context/AuthContext";
import ProtectedRoute from "./routes/ProtectedRoute";
import RoleRoute from "./routes/RoleRoute";
import AdminLayout from "./layout/AdminLayout";

import Login from "./pages/Login";
import Unauthorized from "./pages/errors/Unauthorized";
import NotFound from "./pages/errors/NotFound";

// Lazy load pages
const Dashboard = lazy(() => import("./pages/Dashboard"));
const LicensePage = lazy(() => import("./pages/LicensePage"));
const Settings = lazy(() => import("./pages/Settings"));
const Profile = lazy(() => import("./pages/Profile"));
const MasterList = lazy(() => import("./pages/masters/MasterList"));
const MasterForm = lazy(() => import("./pages/masters/MasterForm"));
const AllotmentAction = lazy(() => import("./pages/AllotmentAction"));
const BOETransferLetter = lazy(() => import("./pages/BOETransferLetter"));
const SionE1 = lazy(() => import("./pages/reports/SionE1"));
const SionE5 = lazy(() => import("./pages/reports/SionE5"));
const SionE126 = lazy(() => import("./pages/reports/SionE126"));
const SionE132 = lazy(() => import("./pages/reports/SionE132"));
const ExpiringLicenses = lazy(() => import("./pages/reports/ExpiringLicenses"));
const ActiveLicenses = lazy(() => import("./pages/reports/ActiveLicenses"));
const ItemPivotReport = lazy(() => import("./pages/reports/ItemPivotReport"));
const TradeForm = lazy(() => import("./pages/TradeForm"));
const LedgerCSVUpload = lazy(() => import("./pages/LedgerCSVUpload"));
const LedgerUpload = lazy(() => import("./pages/LedgerUpload"));

export default function App() {
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
                <Suspense fallback={<div className="p-4">Loading...</div>}>
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
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/licenses/create"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/licenses/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            {/* Allotment CRUD Routes */}
                            <Route
                                path="/allotments"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/allotments/create"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/allotments/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/allotments/:id/allocate"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <AllotmentAction/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            {/* Reports Routes */}
                            
                            <Route
                                path="/reports/parle/sion-e1"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager", "accounts"]}>
                                            <AdminLayout>
                                                <SionE1/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/parle/sion-e5"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager", "accounts"]}>
                                            <AdminLayout>
                                                <SionE5/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/parle/sion-e126"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager", "accounts"]}>
                                            <AdminLayout>
                                                <SionE126/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/parle/sion-e132"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager", "accounts"]}>
                                            <AdminLayout>
                                                <SionE132/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/expiring-licenses"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager", "accounts"]}>
                                            <AdminLayout>
                                                <ExpiringLicenses/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/active-licenses"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager", "accounts"]}>
                                            <AdminLayout>
                                                <ActiveLicenses/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/reports/item-pivot"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager", "accounts"]}>
                                            <AdminLayout>
                                                <ItemPivotReport/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            {/* Bill of Entry CRUD Routes */}
                            <Route
                                path="/bill-of-entries"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/bill-of-entries/create"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/bill-of-entries/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/bill-of-entries/:id/generate-transfer-letter"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <BOETransferLetter/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            {/* Trade CRUD Routes */}
                            <Route
                                path="/trades"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/trades/create"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <TradeForm/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/trades/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <TradeForm/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/ledger-csv-upload"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <LedgerCSVUpload/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/ledger-upload"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <LedgerUpload/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/settings"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin"]}>
                                            <AdminLayout>
                                                <Settings/>
                                            </AdminLayout>
                                        </RoleRoute>
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
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterList/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/masters/:entity/create"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            <Route
                                path="/masters/:entity/:id/edit"
                                element={
                                    <ProtectedRoute>
                                        <RoleRoute roles={["admin", "manager"]}>
                                            <AdminLayout>
                                                <MasterForm/>
                                            </AdminLayout>
                                        </RoleRoute>
                                    </ProtectedRoute>
                                }
                            />

                            {/* 404 */}
                            <Route path="*" element={<NotFound/>}/>
                        </Routes>
                    </Suspense>
                </BrowserRouter>
        </AuthProvider>
    );
}
