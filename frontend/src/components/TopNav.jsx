import {useContext} from "react";
import {Link} from "react-router-dom";
import {AuthContext} from "../context/AuthContext";
import {routes} from "../routes/config";

export default function TopNav() {
    const {user, logout, hasRole} = useContext(AuthContext);

    return (
        <nav className="navbar navbar-expand-lg navbar-dark bg-dark px-3">
            <Link className="navbar-brand fw-bold" to="/">
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
                        .filter((r) => !r.protected || hasRole(r.roles))
                        .map((r) => (
                            <li className="nav-item" key={r.path}>
                                <Link className="nav-link" to={r.path}>
                                    {r.label}
                                </Link>
                            </li>
                        ))}
                </ul>

                {/* Right User Dropdown */}
                {user && (
                    <div className="dropdown">
                        <button
                            className="btn btn-secondary dropdown-toggle"
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
