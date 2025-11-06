import React, { useContext } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";

import Sidebar from "./components/Sidebar";
import TopNavbar from "./components/Navbar";

import Dashboard from "./pages/Dashboard";
import License from "./pages/License";
import Allotment from "./pages/Allotment";
import BillOfEntry from "./pages/BillOfEntry";
import Trade from "./pages/Trade";
import Profile from "./pages/Profile";
import Login from "./pages/Login";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";

import MasterCRUD from "./pages/Master/MasterCRUD";
import { AuthContext } from "./context/AuthContext";

/* ---------------- Protected Route Wrapper ---------------- */
const ProtectedRoute = ({ children }) => {
  const { user } = useContext(AuthContext);
  return user ? children : <Navigate to="/login" replace />;
};

/* ---------------- Main App Component ---------------- */
const App = () => {
  const { user } = useContext(AuthContext);

  return (
    <Router>
      {/* Show Navbar only when logged in */}
      {user && <TopNavbar />}

      <Routes>
        {/* -------- Public Routes -------- */}
        <Route path="/login" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route
          path="/reset-password/:uid/:token"
          element={<ResetPassword />}
        />

        {/* -------- Protected Routes -------- */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <div className="d-flex">
                <Sidebar />
                <div className="main-content flex-grow-1 p-3">
                  <Routes>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/license" element={<License />} />
                    <Route path="/allotment" element={<Allotment />} />
                    <Route path="/bill-of-entry" element={<BillOfEntry />} />
                    <Route path="/trade" element={<Trade />} />
                    <Route path="/profile" element={<Profile />} />

                    {/* -------- Dynamic Master CRUD Routes -------- */}
<Route
  path="/master/company"
  element={
    <MasterCRUD
      key="company" // 👈 this forces re-render
      endpoint="masters/companies/"
      title="Companies"
    />
  }
/>
<Route
  path="/master/port"
  element={
    <MasterCRUD
      key="port" // 👈 unique key for each master page
      endpoint="masters/ports/"
      title="Ports"
    />
  }
/>
<Route
  path="/master/hsn-code"
  element={
    <MasterCRUD
      key="hsn" // 👈 ensures schema/data reload
      endpoint="masters/hs-codes/"
      title="HSN Codes"
    />
  }
/>
<Route
  path="/master/sion-classes"
  element={
    <MasterCRUD
      key="sion"
      endpoint="masters/sion-classes/"
      title="SION Norms"
    />
  }
/>
                    {/* Default redirect */}
                    <Route
                      path="*"
                      element={<Navigate to="/dashboard" replace />}
                    />
                  </Routes>
                </div>
              </div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  );
};

export default App;
