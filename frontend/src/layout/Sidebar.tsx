import {Link, useLocation} from "react-router-dom";
import {useContext, useState} from "react";
import {masterEntities, routes, reportEntities} from "../routes/config";
import {AuthContext} from "../context/AuthContext";
import { BarChart3, ChevronDown, Database, Grid3x3, Users } from "lucide-react";
import Icon from "@/components/Icon";

export default function Sidebar() {
    const location = useLocation();
    const {canManageUsers} = useContext(AuthContext);
    const [mastersOpen, setMastersOpen] = useState(false);
    const [reportsOpen, setReportsOpen] = useState(false);

    const isActive = (path) => {
        return location.pathname === path || location.pathname.startsWith(path);
    };

    return (
        <div className="sidebar flex flex-col border-r border-border bg-card text-foreground" style={{
            width: "260px",
            minHeight: "100vh",
        }}>
            {/* Header section */}
            <div className="flex items-center gap-2 px-3 py-4 border-b border-border shrink-0">
                <Grid3x3 className="size-4 flex-shrink-0" aria-hidden="true" />
                <h5 className="text-sm font-semibold truncate">Dashboard</h5>
            </div>

            {/* Navigation section */}
            <nav className="flex-1 overflow-y-auto px-2 py-2">
                <ul className="flex flex-col gap-1">
                    {/* Main navigation links */}
                    {routes
                        .filter((r) => !r.protected)
                        .map((r) => (
                            <li key={r.path}>
                                <Link
                                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                                        isActive(r.path)
                                            ? "bg-blue-50 text-blue-700 border-l-2 border-blue-600"
                                            : "text-slate-700 hover:bg-slate-50"
                                    }`}
                                    to={r.path}
                                >
                                    <Icon name={r.icon} className="size-4 flex-shrink-0" />
                                    <span className="truncate">{r.label}</span>
                                </Link>
                            </li>
                        ))}

                    {/* Reports Dropdown */}
                    <li>
                        <button
                            className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                                isActive("/reports")
                                    ? "bg-blue-50 text-blue-700 border-l-2 border-blue-600"
                                    : "text-slate-700 hover:bg-slate-50"
                            }`}
                            onClick={() => setReportsOpen(!reportsOpen)}
                        >
                            <div className="flex items-center gap-2 min-w-0">
                                <BarChart3 className="size-4 flex-shrink-0" aria-hidden="true" />
                                <span className="truncate">Reports</span>
                            </div>
                            <ChevronDown
                                className="size-4 flex-shrink-0 transition-transform"
                                style={{
                                    transform: reportsOpen ? "rotate(180deg)" : "rotate(0deg)",
                                }}
                                aria-hidden="true"
                            />
                        </button>

                        {reportsOpen && (
                            <ul className="flex flex-col gap-1 mt-1 ml-2">
                                {reportEntities.map((report) => (
                                    <li key={report.path}>
                                        <Link
                                            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
                                                isActive(report.path)
                                                    ? "bg-blue-50 text-blue-700 border-l-2 border-blue-600"
                                                    : "text-slate-700 hover:bg-slate-50"
                                            }`}
                                            to={report.path}
                                        >
                                            <Icon name={report.icon} className="size-3.5 flex-shrink-0" />
                                            <span className="truncate text-xs font-medium">{report.label}</span>
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </li>

                    {/* User Management — superusers and USER_MANAGER role only */}
                    {canManageUsers && canManageUsers() && (
                        <li>
                            <Link
                                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                                    isActive("/admin/users")
                                        ? "bg-blue-50 text-blue-700 border-l-2 border-blue-600"
                                        : "text-slate-700 hover:bg-slate-50"
                                }`}
                                to="/admin/users"
                            >
                                <Users className="size-4 flex-shrink-0" aria-hidden="true" />
                                <span className="truncate">Users</span>
                            </Link>
                        </li>
                    )}

                    {/* Masters Dropdown */}
                    <li>
                        <button
                            className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                                isActive("/masters")
                                    ? "bg-blue-50 text-blue-700 border-l-2 border-blue-600"
                                    : "text-slate-700 hover:bg-slate-50"
                            }`}
                            onClick={() => setMastersOpen(!mastersOpen)}
                        >
                            <div className="flex items-center gap-2 min-w-0">
                                <Database className="size-4 flex-shrink-0" aria-hidden="true" />
                                <span className="truncate">Masters</span>
                            </div>
                            <ChevronDown
                                className="size-4 flex-shrink-0 transition-transform"
                                style={{
                                    transform: mastersOpen ? "rotate(180deg)" : "rotate(0deg)",
                                }}
                                aria-hidden="true"
                            />
                        </button>

                        {mastersOpen && (
                            <ul className="flex flex-col gap-1 mt-1 ml-2">
                                {masterEntities
                                    .filter(m => !m.deprecated)
                                    .map((master) => (
                                        <li key={master.path}>
                                            <Link
                                                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
                                                    isActive(master.path)
                                                        ? "bg-blue-50 text-blue-700 border-l-2 border-blue-600"
                                                        : "text-slate-700 hover:bg-slate-50"
                                                }`}
                                                to={master.path}
                                            >
                                                <Icon name={master.icon} className="size-3.5 flex-shrink-0" />
                                                <span className="truncate text-xs font-medium">{master.label}</span>
                                            </Link>
                                        </li>
                                    ))}
                            </ul>
                        )}
                    </li>
                </ul>
            </nav>
        </div>
    );
}
