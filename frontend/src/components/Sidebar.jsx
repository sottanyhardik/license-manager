import React from "react";
import { NavLink } from "react-router-dom";

const Sidebar = () => {
  return (
    <div className="sidebar-custom d-flex flex-column">
      <h5 className="text-white mb-3">📁 Navigation</h5>

      <NavLink to="/dashboard" className="nav-link">
        <i className="bi bi-speedometer2 me-2"></i>Dashboard
      </NavLink>

      <NavLink to="/license" className="nav-link">
        <i className="bi bi-card-checklist me-2"></i>License
      </NavLink>

      <NavLink to="/allotment" className="nav-link">
        <i className="bi bi-diagram-3 me-2"></i>Allotment
      </NavLink>

      <NavLink to="/bill-of-entry" className="nav-link">
        <i className="bi bi-file-earmark-text me-2"></i>Bill of Entry
      </NavLink>

      <NavLink to="/trade" className="nav-link">
        <i className="bi bi-cash-coin me-2"></i>Trade
      </NavLink>

      <hr className="border-light" />

      <h6 className="text-white-50 mt-2">Master Data</h6>
      <NavLink to="/master/company" className="nav-link">
        <i className="bi bi-building me-2"></i>Company
      </NavLink>
      <NavLink to="/master/port" className="nav-link">
        <i className="bi bi-geo-alt me-2"></i>Port
      </NavLink>
      <NavLink to="/master/hsn-code" className="nav-link">
        <i className="bi bi-upc-scan me-2"></i>HSN Code
      </NavLink>
      <NavLink to="/master/sion-norms" className="nav-link">
        <i className="bi bi-list-check me-2"></i>SION Norms
      </NavLink>
    </div>
  );
};

export default Sidebar;
