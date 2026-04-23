import {Link, useLocation} from "react-router-dom";
import {useState} from "react";
import {masterEntities, routes, reportEntities} from "../routes/config";

export default function Sidebar() {
    const location = useLocation();
    const [mastersOpen, setMastersOpen] = useState(false);
    const [reportsOpen, setReportsOpen] = useState(false);

    const isActive = (path) => {
        return location.pathname === path || location.pathname.startsWith(path);
    };

    const navLinkStyle = (active, sub = false) => ({
        borderRadius: sub ? '6px' : '8px',
        padding: sub ? '0.5rem 1rem' : '0.65rem 1rem',
        fontSize: sub ? '0.85rem' : '0.9rem',
        transition: 'all 0.2s ease',
        backgroundColor: active ? 'var(--primary-color)' : 'transparent',
        color: 'white',
    });

    const handleMouseEnter = (active) => (e) => {
        if (!active) e.currentTarget.style.backgroundColor = 'rgba(79, 70, 229, 0.12)';
    };

    const handleMouseLeave = (active) => (e) => {
        if (!active) e.currentTarget.style.backgroundColor = 'transparent';
    };

    return (
        <div className="text-white sidebar p-3" style={{
            width: "260px",
            minHeight: "100vh",
            background: 'linear-gradient(180deg, #1e293b 0%, #0f172a 100%)',
            boxShadow: '2px 0 8px rgba(0, 0, 0, 0.1)'
        }}>
            <div className="d-flex align-items-center justify-content-center mb-4 mt-2">
                <i className="bi bi-grid-3x3-gap-fill me-2" style={{color: 'var(--primary-light)', fontSize: '1.5rem'}}></i>
                <h5 className="mb-0 fw-bold">Dashboard</h5>
            </div>

            <ul className="nav flex-column">
                {routes
                    .filter((r) => !r.protected)
                    .map((r) => (
                        <li key={r.path} className="nav-item mb-1">
                            <Link
                                className={`nav-link d-flex align-items-center ${isActive(r.path) ? "active" : ""}`}
                                to={r.path}
                                style={navLinkStyle(isActive(r.path))}
                                onMouseEnter={handleMouseEnter(isActive(r.path))}
                                onMouseLeave={handleMouseLeave(isActive(r.path))}
                            >
                                <i className={`bi bi-${r.icon} me-2`} style={{fontSize: '1.1rem'}}/>
                                <span>{r.label}</span>
                            </Link>
                        </li>
                    ))}

                {/* Reports Dropdown */}
                <li className="nav-item mb-1">
                    <button
                        className={`nav-link w-100 text-start d-flex align-items-center justify-content-between ${isActive("/reports") ? "active" : ""}`}
                        onClick={() => setReportsOpen(!reportsOpen)}
                        style={{ ...navLinkStyle(isActive("/reports")), border: 'none' }}
                        onMouseEnter={handleMouseEnter(isActive("/reports"))}
                        onMouseLeave={handleMouseLeave(isActive("/reports"))}
                    >
                        <div className="d-flex align-items-center">
                            <i className="bi bi-file-earmark-bar-graph me-2" style={{fontSize: '1.1rem'}}/>
                            <span>Reports</span>
                        </div>
                        <i className={`bi bi-chevron-${reportsOpen ? "up" : "down"}`} style={{fontSize: '0.8rem'}}/>
                    </button>

                    {reportsOpen && (
                        <ul className="nav flex-column ms-2 mt-1">
                            {reportEntities.map((report) => (
                                <li key={report.path} className="nav-item mb-1">
                                    <Link
                                        className={`nav-link ${isActive(report.path) ? "active" : ""}`}
                                        to={report.path}
                                        style={navLinkStyle(isActive(report.path), true)}
                                        onMouseEnter={handleMouseEnter(isActive(report.path))}
                                        onMouseLeave={handleMouseLeave(isActive(report.path))}
                                    >
                                        <i className={`bi bi-${report.icon} me-2`} style={{fontSize: '0.9rem'}}/>
                                        {report.label}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    )}
                </li>

                {/* Masters Dropdown */}
                <li className="nav-item mb-1">
                    <button
                        className={`nav-link w-100 text-start d-flex align-items-center justify-content-between ${isActive("/masters") ? "active" : ""}`}
                        onClick={() => setMastersOpen(!mastersOpen)}
                        style={{ ...navLinkStyle(isActive("/masters")), border: 'none' }}
                        onMouseEnter={handleMouseEnter(isActive("/masters"))}
                        onMouseLeave={handleMouseLeave(isActive("/masters"))}
                    >
                        <div className="d-flex align-items-center">
                            <i className="bi bi-database me-2" style={{fontSize: '1.1rem'}}/>
                            <span>Masters</span>
                        </div>
                        <i className={`bi bi-chevron-${mastersOpen ? "up" : "down"}`} style={{fontSize: '0.8rem'}}/>
                    </button>

                    {mastersOpen && (
                        <ul className="nav flex-column ms-2 mt-1">
                            {masterEntities.map((master) => (
                                <li key={master.path} className="nav-item mb-1">
                                    <Link
                                        className={`nav-link ${isActive(master.path) ? "active" : ""}`}
                                        to={master.path}
                                        style={navLinkStyle(isActive(master.path), true)}
                                        onMouseEnter={handleMouseEnter(isActive(master.path))}
                                        onMouseLeave={handleMouseLeave(isActive(master.path))}
                                    >
                                        <i className={`bi bi-${master.icon} me-2`} style={{fontSize: '0.9rem'}}/>
                                        {master.label}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    )}
                </li>
            </ul>
        </div>
    );
}
