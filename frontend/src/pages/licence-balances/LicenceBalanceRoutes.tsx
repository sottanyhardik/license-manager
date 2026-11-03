import { Navigate, Route, Routes } from "react-router-dom";
import LicenceBalanceDetail from "./LicenceBalanceDetail";
import LicenceBalancePage from "./LicenceBalancePage";

/**
 * Child routes for `/licence-balances/*`. AppRoutes mounts this once behind
 * the licence-role guard, so the list and the detail share the same access rule.
 */
export default function LicenceBalanceRoutes() {
  return (
    <Routes>
      <Route index element={<LicenceBalancePage />} />
      <Route path=":licenceId" element={<LicenceBalanceDetail />} />
      <Route path="*" element={<Navigate to="/licence-balances" replace />} />
    </Routes>
  );
}
