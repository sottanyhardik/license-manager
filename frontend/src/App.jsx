import "./App.css";
import {BrowserRouter, Navigate, Route, Routes} from "react-router-dom";
import {lazy, Suspense} from "react";

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

export default function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
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
