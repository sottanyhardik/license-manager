import {Link, useLocation} from "react-router-dom";
import {useContext, useState} from "react";
import {AuthContext} from "../context/AuthContext";
import {masterEntities, routes, reportEntities} from "../routes/config";

export default function Sidebar() {
    const {hasRole} = useContext(AuthContext);
    const location = useLocation();
    const [mastersOpen, setMastersOpen] = useState(false);
    const [reportsOpen, setReportsOpen] = useState(false);

    const isActive = (path) => {
        return location.pathname === path || location.pathname.startsWith(path);
    };

    return (
        <div className="text-white sidebar p-3" style={{
            width: "260px",
            minHeight: "100vh",
            background: 'linear-gradient(180deg, #1e293b 0%, #0f172a 100%)',
            boxShadow: '2px 0 8px rgba(0, 0, 0, 0.1)'
        }}>
            <div className="d-flex align-items-center justify-content-center mb-4 mt-2">
                <i className="bi bi-grid-3x3-gap-fill me-2" style={{color: '#3b82f6', fontSize: '1.5rem'}}></i>
                <h5 className="mb-0 fw-bold">Dashboard</h5>
            </div>

            <ul className="nav flex-column">
                {routes
                    .filter((r) => !r.protected || hasRole(r.roles))
                    .map((r) => (
                        <li key={r.path} className="nav-item mb-1">
                            <Link
                                className={`nav-link text-white d-flex align-items-center ${isActive(r.path) ? "active" : ""}`}
                                to={r.path}
                                style={{
                                    borderRadius: '8px',
                                    padding: '0.65rem 1rem',
                                    transition: 'all 0.2s ease',
                                    backgroundColor: isActive(r.path) ? '#2563eb' : 'transparent',
                                }}
                                onMouseEnter={(e) => {
                                    if (!isActive(r.path)) {
                                        e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.15)';
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    if (!isActive(r.path)) {
                                        e.target.style.backgroundColor = 'transparent';
                                    }
                                }}
                            >
                                <i className={`bi bi-${r.icon} me-2`} style={{fontSize: '1.1rem'}}/>
                                <span style={{fontSize: '0.9rem'}}>{r.label}</span>
                            </Link>
                        </li>
                    ))}

                {/* Reports Dropdown */}
                {hasRole(["admin", "manager"]) && (
                    <li className="nav-item mb-1">
                        <button
                            className={`nav-link text-white w-100 text-start d-flex align-items-center justify-content-between ${isActive("/reports") ? "active" : ""}`}
                            onClick={() => setReportsOpen(!reportsOpen)}
                            style={{
                                borderRadius: '8px',
                                padding: '0.65rem 1rem',
                                transition: 'all 0.2s ease',
                                backgroundColor: isActive("/reports") ? '#2563eb' : 'transparent',
                                border: 'none'
                            }}
                            onMouseEnter={(e) => {
                                if (!isActive("/reports")) {
                                    e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.15)';
                                }
                            }}
                            onMouseLeave={(e) => {
                                if (!isActive("/reports")) {
                                    e.target.style.backgroundColor = 'transparent';
                                }
                            }}
                        >
                            <div className="d-flex align-items-center">
                                <i className="bi bi-file-earmark-bar-graph me-2" style={{fontSize: '1.1rem'}}/>
                                <span style={{fontSize: '0.9rem'}}>Reports</span>
                            </div>
                            <i className={`bi bi-chevron-${reportsOpen ? "up" : "down"}`} style={{fontSize: '0.8rem'}}/>
                        </button>

                        {reportsOpen && (
                            <ul className="nav flex-column ms-2 mt-1">
                                {reportEntities.map((report) => (
                                    <li key={report.path} className="nav-item mb-1">
                                        <Link
                                            className={`nav-link text-white ${isActive(report.path) ? "active" : ""}`}
                                            to={report.path}
                                            style={{
                                                borderRadius: '6px',
                                                padding: '0.5rem 1rem',
                                                fontSize: '0.85rem',
                                                transition: 'all 0.2s ease',
                                                backgroundColor: isActive(report.path) ? '#2563eb' : 'transparent',
                                            }}
                                            onMouseEnter={(e) => {
                                                if (!isActive(report.path)) {
                                                    e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
                                                }
                                            }}
                                            onMouseLeave={(e) => {
                                                if (!isActive(report.path)) {
                                                    e.target.style.backgroundColor = 'transparent';
                                                }
                                            }}
                                        >
                                            <i className={`bi bi-${report.icon} me-2`} style={{fontSize: '0.9rem'}}/>
                                            {report.label}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </li>
                )}

                {/* Masters Dropdown */}
                {hasRole(["admin", "manager"]) && (
                    <li className="nav-item mb-1">
                        <button
                            className={`nav-link text-white w-100 text-start d-flex align-items-center justify-content-between ${isActive("/masters") ? "active" : ""}`}
                            onClick={() => setMastersOpen(!mastersOpen)}
                            style={{
                                borderRadius: '8px',
                                padding: '0.65rem 1rem',
                                transition: 'all 0.2s ease',
                                backgroundColor: isActive("/masters") ? '#2563eb' : 'transparent',
                                border: 'none'
                            }}
                            onMouseEnter={(e) => {
                                if (!isActive("/masters")) {
                                    e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.15)';
                                }
                            }}
                            onMouseLeave={(e) => {
                                if (!isActive("/masters")) {
                                    e.target.style.backgroundColor = 'transparent';
                                }
                            }}
                        >
                            <div className="d-flex align-items-center">
                                <i className="bi bi-database me-2" style={{fontSize: '1.1rem'}}/>
                                <span style={{fontSize: '0.9rem'}}>Masters</span>
                            </div>
                            <i className={`bi bi-chevron-${mastersOpen ? "up" : "down"}`} style={{fontSize: '0.8rem'}}/>
                        </button>

                        {mastersOpen && (
                            <ul className="nav flex-column ms-2 mt-1">
                                {masterEntities.map((master) => (
                                    <li key={master.path} className="nav-item mb-1">
                                        <Link
                                            className={`nav-link text-white ${isActive(master.path) ? "active" : ""}`}
                                            to={master.path}
                                            style={{
                                                borderRadius: '6px',
                                                padding: '0.5rem 1rem',
                                                fontSize: '0.85rem',
                                                transition: 'all 0.2s ease',
                                                backgroundColor: isActive(master.path) ? '#2563eb' : 'transparent',
                                            }}
                                            onMouseEnter={(e) => {
                                                if (!isActive(master.path)) {
                                                    e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
                                                }
                                            }}
                                            onMouseLeave={(e) => {
                                                if (!isActive(master.path)) {
                                                    e.target.style.backgroundColor = 'transparent';
                                                }
                                            }}
                                        >
                                            <i className={`bi bi-${master.icon} me-2`} style={{fontSize: '0.9rem'}}/>
                                            {master.label}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </li>
                )}
            </ul>
        </div>
    );
}
