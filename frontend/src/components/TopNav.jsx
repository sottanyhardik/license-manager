import {useContext} from "react";
import {Link} from "react-router-dom";
import {AuthContext} from "../context/AuthContext";
import {routes, reportEntities, masterEntities, ledgerEntities, commissionEntities} from "../routes/config";

export default function TopNav() {
    const {user, logout} = useContext(AuthContext);

    return (
        <nav className="navbar navbar-expand-lg navbar-dark px-4" style={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
            padding: '16px 24px'
        }}>
            <Link className="navbar-brand fw-bold" to="/" style={{
                fontSize: '1.3rem',
                letterSpacing: '0.5px',
                display: 'flex',
                alignItems: 'center'
            }}>
                <div style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '10px',
                    background: 'rgba(255, 255, 255, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginRight: '12px',
                    backdropFilter: 'blur(10px)'
                }}>
                    <i className="bi bi-shield-check" style={{color: 'white', fontSize: '1.2rem'}}></i>
                </div>
                <span>License Manager</span>
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
                            className="btn dropdown-toggle"
                            type="button"
                            data-bs-toggle="dropdown"
                            style={{
                                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                                border: '1px solid rgba(255, 255, 255, 0.3)',
                                color: 'white',
                                fontWeight: '500',
                                padding: '8px 20px',
                                backdropFilter: 'blur(10px)'
                            }}
                        >
                            <i className="bi bi-person-circle me-2"></i>
                            {user.username}
                        </button>
                        <ul className="dropdown-menu dropdown-menu-end" style={{
                            borderRadius: '8px',
                            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                            border: 'none',
                            marginTop: '8px'
                        }}>
                            <li>
                                <Link className="dropdown-item" to="/profile" style={{ padding: '10px 20px' }}>
                                    <i className="bi bi-person me-2"></i>
                                    Profile
                                </Link>
                            </li>
                            <li><hr className="dropdown-divider" /></li>
                            <li>
                                <button className="dropdown-item text-danger" onClick={logout} style={{ padding: '10px 20px' }}>
                                    <i className="bi bi-box-arrow-right me-2"></i>
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
