import {Link, useLocation} from "react-router-dom";
import {useContext, useState} from "react";
import {AuthContext} from "../context/AuthContext";
import {routes, masterEntities} from "../routes/config";

export default function Sidebar() {
    const {hasRole} = useContext(AuthContext);
    const location = useLocation();
    const [mastersOpen, setMastersOpen] = useState(false);

    const isActive = (path) => {
        return location.pathname === path || location.pathname.startsWith(path);
    };

    return (
        <div className="bg-dark text-white sidebar p-3" style={{width: "240px", minHeight: "100vh"}}>
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
