import {useContext} from "react";
import {Link} from "react-router-dom";
import {AuthContext} from "../context/AuthContext";
import {routes, reportEntities, masterEntities, ledgerEntities, commissionEntities} from "../routes/config";

export default function TopNav() {
    const {user, logout} = useContext(AuthContext);

    return (
        <nav className="navbar navbar-expand-lg navbar-dark px-3" style={{
            background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
            boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)'
        }}>
            <Link className="navbar-brand fw-bold" to="/" style={{
                fontSize: '1.25rem',
                letterSpacing: '0.5px'
            }}>
                <i className="bi bi-shield-check me-2" style={{color: '#3b82f6'}}></i>
                License Manager
            </Link>

            <button
                className="navbar-toggler"
                type="button"
                data-bs-toggle="collapse"
                data-bs-target="#navbarMenu"
            >
                <span className="navbar-toggler-icon"></span>
            </button>

            <div className="collapse navbar-collapse" id="navbarMenu">
                {/* Left Links */}
                <ul className="navbar-nav me-auto mb-2 mb-lg-0">
                    {routes
                        .filter((r) => !r.protected)
                        .map((r) => (
                            <li className="nav-item" key={r.path}>
                                <Link className="nav-link" to={r.path}>
                                    {r.label}
                                </Link>
                            </li>
                        ))}

                    {/* Reports Dropdown */}
                    <li className="nav-item dropdown">
                            <a
                                className="nav-link dropdown-toggle"
                                href="#"
                                role="button"
                                data-bs-toggle="dropdown"
                                aria-expanded="false"
                            >
                                <i className="bi bi-file-earmark-bar-graph me-1"></i>
                                Reports
                            </a>
                            <ul className="dropdown-menu">
                                {reportEntities.map((report) => (
                                    <li key={report.path}>
                                        <Link className="dropdown-item" to={report.path}>
                                            <i className={`bi bi-${report.icon} me-2`}></i>
                                            {report.label}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </li>

                    {/* Masters Dropdown */}
                    <li className="nav-item dropdown">
                            <a
                                className="nav-link dropdown-toggle"
                                href="#"
                                role="button"
                                data-bs-toggle="dropdown"
                                aria-expanded="false"
                            >
                                <i className="bi bi-database me-1"></i>
                                Masters
                            </a>
                            <ul className="dropdown-menu">
                                {masterEntities
                                    .filter((master) => !master.deprecated)
                                    .map((master) => (
                                        <li key={master.path}>
                                            <Link className="dropdown-item" to={master.path}>
                                                <i className={`bi bi-${master.icon} me-2`}></i>
                                                {master.label}
                                            </Link>
                                        </li>
                                    ))}
                            </ul>
                        </li>

                </ul>

                {/* Right User Dropdown */}
                {user && (
                    <div className="dropdown">
                        <button
                            className="btn btn-primary dropdown-toggle"
                            type="button"
                            data-bs-toggle="dropdown"
                        >
                            {user.username}
                        </button>
                        <ul className="dropdown-menu dropdown-menu-end">
                            <li>
                                <Link className="dropdown-item" to="/profile">
                                    Profile
                                </Link>
                            </li>
                            <li>
                                <button className="dropdown-item text-danger" onClick={logout}>
                                    Logout
                                </button>
                            </li>
                        </ul>
                    </div>
                )}
            </div>
        </nav>
    );
}
