import {Link, useLocation} from "react-router-dom";
import {useContext, useState} from "react";
import {AuthContext} from "../context/AuthContext";
import {masterEntities, routes} from "../routes/config";

export default function Sidebar() {
    const {hasRole} = useContext(AuthContext);
    const location = useLocation();
    const [mastersOpen, setMastersOpen] = useState(false);
    const [reportsOpen, setReportsOpen] = useState(false);
    const [parleOpen, setParleOpen] = useState(false);

    const isActive = (path) => {
        return location.pathname === path || location.pathname.startsWith(path);
    };

    return (
        <div className="bg-dark text-white sidebar p-12" style={{width: "240px", minHeight: "100vh"}}>
            <h4 className="text-center mb-4">Admin Panel</h4>

            <ul className="nav nav-pills flex-column">
                {routes
                    .filter((r) => !r.protected || hasRole(r.roles))
                    .map((r) => (
                        <li key={r.path} className="nav-item mb-2">
                            <Link
                                className={`nav-link text-white ${isActive(r.path) ? "active" : ""}`}
                                to={r.path}
                            >
                                <i className={`bi bi-${r.icon} me-2`}/>
                                {r.label}
                            </Link>
                        </li>
                    ))}

                {/* Reports Dropdown */}
                {hasRole(["admin", "manager"]) && (
                    <li className="nav-item mb-2">
                        <button
                            className={`nav-link text-white w-100 text-start ${isActive("/reports") ? "active" : ""}`}
                            onClick={() => setReportsOpen(!reportsOpen)}
                        >
                            <i className="bi bi-file-earmark-bar-graph me-2"/>
                            Reports
                            <i className={`bi bi-chevron-${reportsOpen ? "up" : "down"} float-end`}/>
                        </button>

                        {reportsOpen && (
                            <ul className="nav flex-column ms-3 mt-2">
                                {/* Parle Submenu */}
                                <li className="nav-item mb-1">
                                    <button
                                        className={`nav-link text-white w-100 text-start py-1 ${isActive("/reports/parle") ? "active" : ""}`}
                                        onClick={() => setParleOpen(!parleOpen)}
                                        style={{fontSize: '0.9rem'}}
                                    >
                                        <i className="bi bi-building me-2"/>
                                        Parle
                                        <i className={`bi bi-chevron-${parleOpen ? "up" : "down"} float-end`}/>
                                    </button>

                                    {parleOpen && (
                                        <ul className="nav flex-column ms-3 mt-1">
                                            <li className="nav-item mb-1">
                                                <Link
                                                    className={`nav-link text-white py-1 ${isActive("/reports/parle/sion-e1") ? "active" : ""}`}
                                                    to="/reports/parle/sion-e1"
                                                    style={{fontSize: '0.85rem'}}
                                                >
                                                    <i className="bi bi-dot me-1"/>
                                                    SION Norm E1
                                                </Link>
                                            </li>
                                            <li className="nav-item mb-1">
                                                <Link
                                                    className={`nav-link text-white py-1 ${isActive("/reports/parle/sion-e5") ? "active" : ""}`}
                                                    to="/reports/parle/sion-e5"
                                                    style={{fontSize: '0.85rem'}}
                                                >
                                                    <i className="bi bi-dot me-1"/>
                                                    SION Norm E5
                                                </Link>
                                            </li>
                                            <li className="nav-item mb-1">
                                                <Link
                                                    className={`nav-link text-white py-1 ${isActive("/reports/parle/sion-e126") ? "active" : ""}`}
                                                    to="/reports/parle/sion-e126"
                                                    style={{fontSize: '0.85rem'}}
                                                >
                                                    <i className="bi bi-dot me-1"/>
                                                    SION Norm E126
                                                </Link>
                                            </li>
                                            <li className="nav-item mb-1">
                                                <Link
                                                    className={`nav-link text-white py-1 ${isActive("/reports/parle/sion-e132") ? "active" : ""}`}
                                                    to="/reports/parle/sion-e132"
                                                    style={{fontSize: '0.85rem'}}
                                                >
                                                    <i className="bi bi-dot me-1"/>
                                                    SION Norm E132
                                                </Link>
                                            </li>
                                        </ul>
                                    )}
                                </li>

                                <li className="nav-item mb-1">
                                    <Link
                                        className={`nav-link text-white py-1 ${isActive("/reports/parle-licenses") ? "active" : ""}`}
                                        to="/reports/parle-licenses"
                                    >
                                        <i className="bi bi-file-text me-2"/>
                                        All Notifications
                                    </Link>
                                </li>
                                <li className="nav-item mb-1">
                                    <Link
                                        className={`nav-link text-white py-1 ${isActive("/reports/notification/019-2015") ? "active" : ""}`}
                                        to="/reports/notification/019-2015"
                                    >
                                        <i className="bi bi-file-text me-2"/>
                                        019/2015
                                    </Link>
                                </li>
                                <li className="nav-item mb-1">
                                    <Link
                                        className={`nav-link text-white py-1 ${isActive("/reports/notification/098-2009") ? "active" : ""}`}
                                        to="/reports/notification/098-2009"
                                    >
                                        <i className="bi bi-file-text me-2"/>
                                        098/2009
                                    </Link>
                                </li>
                                <li className="nav-item mb-1">
                                    <Link
                                        className={`nav-link text-white py-1 ${isActive("/reports/notification/025-2023") ? "active" : ""}`}
                                        to="/reports/notification/025-2023"
                                    >
                                        <i className="bi bi-file-text me-2"/>
                                        025/2023
                                    </Link>
                                </li>
                                <li className="nav-item mb-1">
                                    <Link
                                        className={`nav-link text-white py-1 ${isActive("/reports/active-dfia") ? "active" : ""}`}
                                        to="/reports/active-dfia"
                                    >
                                        <i className="bi bi-file-earmark-spreadsheet me-2"/>
                                        Active DFIA
                                    </Link>
                                </li>
                            </ul>
                        )}
                    </li>
                )}

                {/* Masters Dropdown */}
                {hasRole(["admin", "manager"]) && (
                    <li className="nav-item mb-2">
                        <button
                            className={`nav-link text-white w-100 text-start ${isActive("/masters") ? "active" : ""}`}
                            onClick={() => setMastersOpen(!mastersOpen)}
                        >
                            <i className="bi bi-database me-2"/>
                            Masters
                            <i className={`bi bi-chevron-${mastersOpen ? "up" : "down"} float-end`}/>
                        </button>

                        {mastersOpen && (
                            <ul className="nav flex-column ms-3 mt-2">
                                {masterEntities.map((master) => (
                                    <li key={master.path} className="nav-item mb-1">
                                        <Link
                                            className={`nav-link text-white py-1 ${isActive(master.path) ? "active" : ""}`}
                                            to={master.path}
                                        >
                                            <i className={`bi bi-${master.icon} me-2`}/>
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
