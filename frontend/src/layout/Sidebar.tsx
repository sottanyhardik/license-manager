import {Link, useLocation} from "react-router-dom";
import {useContext, useState} from "react";
import {masterEntities, routes, reportEntities} from "../routes/config";
import {AuthContext} from "../context/AuthContext";
import { BarChart3, Database, Grid3x3, Users } from "lucide-react";
import Icon from "@/components/Icon";

export default function Sidebar() {
    const location = useLocation();
    const {canManageUsers} = useContext(AuthContext);
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
        color: '#fff',
    });

    const handleMouseEnter = (active) => (e) => {
        if (!active) e.currentTarget.style.backgroundColor = 'var(--tb-brand-50)';
    };

    const handleMouseLeave = (active) => (e) => {
        if (!active) e.currentTarget.style.backgroundColor = 'transparent';
    };

    return (
        <div className="text-white sidebar p-3" style={{
            width: "260px",
            minHeight: "100vh",
            background: 'var(--tb-card-bg)',
            boxShadow: '2px 0 8px rgba(0, 0, 0, 0.1)'
        }}>
            <div className="flex items-center justify-center mb-4 mt-2">
                <Grid3x3 className="size-4" aria-hidden="true" />
                <h5 className="mb-0 font-bold">Dashboard</h5>
            </div>

            <ul className="nav flex-col">
                {routes
                    .filter((r) => !r.protected)
                    .map((r) => (
                        <li key={r.path} className="nav-item mb-1">
                            <Link
                                className={`nav-link flex items-center ${isActive(r.path) ? "active" : ""}`}
                                to={r.path}
                                style={navLinkStyle(isActive(r.path))}
                                onMouseEnter={handleMouseEnter(isActive(r.path))}
                                onMouseLeave={handleMouseLeave(isActive(r.path))}
                            >
                                <Icon name={r.icon} className="mr-2 size-4" />
                                <span>{r.label}</span>
                            </Link>
                        </li>
                    ))}

                {/* Reports Dropdown */}
                <li className="nav-item mb-1">
                    <button
                        className={`nav-link w-full text-start flex items-center justify-between ${isActive("/reports") ? "active" : ""}`}
                        onClick={() => setReportsOpen(!reportsOpen)}
                        style={{ ...navLinkStyle(isActive("/reports")), border: 'none' }}
                        onMouseEnter={handleMouseEnter(isActive("/reports"))}
                        onMouseLeave={handleMouseLeave(isActive("/reports"))}
                    >
                        <div className="flex items-center">
                            <BarChart3 className="size-4" aria-hidden="true" />
                            <span>Reports</span>
                        </div>
                        <span className="ml-auto" style={{fontSize: 12.5}}>{ reportsOpen ? "▲" : "▼" }</span>
                    </button>

                    {reportsOpen && (
                        <ul className="nav flex-col ml-2 mt-1">
                            {reportEntities.map((report) => (
                                <li key={report.path} className="nav-item mb-1">
                                    <Link
                                        className={`nav-link ${isActive(report.path) ? "active" : ""}`}
                                        to={report.path}
                                        style={navLinkStyle(isActive(report.path), true)}
                                        onMouseEnter={handleMouseEnter(isActive(report.path))}
                                        onMouseLeave={handleMouseLeave(isActive(report.path))}
                                    >
                                        <Icon name={report.icon} className="mr-2 size-3.5" />
                                        {report.label}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    )}
                </li>

                {/* User Management — superusers and USER_MANAGER role only */}
                {canManageUsers && canManageUsers() && (
                    <li className="nav-item mb-1">
                        <Link
                            className={`nav-link flex items-center ${isActive('/admin/users') ? 'active' : ''}`}
                            to="/admin/users"
                            style={navLinkStyle(isActive('/admin/users'))}
                            onMouseEnter={handleMouseEnter(isActive('/admin/users'))}
                            onMouseLeave={handleMouseLeave(isActive('/admin/users'))}
                        >
                            <Users className="size-4" aria-hidden="true" />
                            <span>Users</span>
                        </Link>
                    </li>
                )}

                {/* Masters Dropdown */}
                <li className="nav-item mb-1">
                    <button
                        className={`nav-link w-full text-start flex items-center justify-between ${isActive("/masters") ? "active" : ""}`}
                        onClick={() => setMastersOpen(!mastersOpen)}
                        style={{ ...navLinkStyle(isActive("/masters")), border: 'none' }}
                        onMouseEnter={handleMouseEnter(isActive("/masters"))}
                        onMouseLeave={handleMouseLeave(isActive("/masters"))}
                    >
                        <div className="flex items-center">
                            <Database className="size-4" aria-hidden="true" />
                            <span>Masters</span>
                        </div>
                        <span className="ml-auto" style={{fontSize: 12.5}}>{ mastersOpen ? "▲" : "▼" }</span>
                    </button>

                    {mastersOpen && (
                        <ul className="nav flex-col ml-2 mt-1">
                            {masterEntities.map((master) => (
                                <li key={master.path} className="nav-item mb-1">
                                    <Link
                                        className={`nav-link ${isActive(master.path) ? "active" : ""}`}
                                        to={master.path}
                                        style={navLinkStyle(isActive(master.path), true)}
                                        onMouseEnter={handleMouseEnter(isActive(master.path))}
                                        onMouseLeave={handleMouseLeave(isActive(master.path))}
                                    >
                                        <Icon name={master.icon} className="mr-2 size-3.5" />
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
