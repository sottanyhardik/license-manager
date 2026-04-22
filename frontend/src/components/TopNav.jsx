import {useContext} from "react";
import {Link, useLocation} from "react-router-dom";
import {AuthContext} from "../context/AuthContext";
import {reportEntities, masterEntities} from "../routes/config";

const NAV_GROUPS = [
    {
        label: 'Licenses',
        icon: 'file-earmark-text',
        items: [
            { path: '/licenses',           label: 'Licenses',           icon: 'file-earmark-text' },
            { path: '/incentive-licenses', label: 'Incentive Licenses', icon: 'award' },
        ],
    },
    {
        label: 'Operations',
        icon: 'arrow-left-right',
        items: [
            { path: '/allotments',      label: 'Allotments',     icon: 'box-seam' },
            { path: '/bill-of-entries', label: 'Bill of Entry',  icon: 'receipt' },
            { path: '/trades',          label: 'Trade In & Out', icon: 'arrow-left-right' },
        ],
    },
];

export default function TopNav() {
    const {user, logout} = useContext(AuthContext);
    const location = useLocation();

    const isPathActive = (path) =>
        location.pathname === path || location.pathname.startsWith(path + '/');

    const isGroupActive = (items) =>
        items.some(i => isPathActive(i.path));

    const navBtnStyle = (active) => ({
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        color: active ? '#ffffff' : 'rgba(255,255,255,0.72)',
        fontWeight: active ? 600 : 400,
        fontSize: '0.84rem',
        letterSpacing: '0.15px',
        padding: '6px 11px',
        paddingBottom: active ? '4px' : '6px',
        borderRadius: '7px',
        whiteSpace: 'nowrap',
        background: active ? 'rgba(165,180,252,0.18)' : 'transparent',
        border: 'none',
        borderBottom: active ? '2px solid #a5b4fc' : '2px solid transparent',
        cursor: 'pointer',
        transition: 'all 150ms ease',
    });

    const activeIconStyle = { fontSize: '0.9rem', color: '#a5b4fc' };
    const inactiveIconStyle = { fontSize: '0.9rem', opacity: 0.8 };

    const dropdownMenuStyle = {
        borderRadius: '10px',
        boxShadow: '0 8px 28px rgba(0,0,0,0.18)',
        border: '1px solid rgba(0,0,0,0.07)',
        padding: '6px',
        minWidth: '210px',
        marginTop: '6px',
    };

    const dropdownItemStyle = {
        borderRadius: '6px',
        padding: '9px 12px',
        fontSize: '0.855rem',
        display: 'flex',
        alignItems: 'center',
        gap: '9px',
    };

    const hoverOn  = (e) => { e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)'; e.currentTarget.style.color = '#ffffff'; };
    const hoverOff = (e, active) => { e.currentTarget.style.backgroundColor = active ? 'rgba(255,255,255,0.14)' : 'transparent'; e.currentTarget.style.color = active ? '#ffffff' : 'rgba(255,255,255,0.75)'; };

    return (
        <nav style={{
            background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 60%, #3730a3 100%)',
            boxShadow: '0 2px 12px rgba(0,0,0,0.35)',
            padding: '0 24px',
            height: '56px',
            display: 'flex',
            alignItems: 'center',
            position: 'sticky',
            top: 0,
            zIndex: 1030,
        }}>
            {/* Brand */}
            <Link to="/" style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                textDecoration: 'none', marginRight: '20px', flexShrink: 0,
            }}>
                <div style={{
                    width: '34px', height: '34px', borderRadius: '8px',
                    background: 'rgba(255,255,255,0.18)',
                    border: '1px solid rgba(255,255,255,0.25)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                    <i className="bi bi-shield-check" style={{color: 'white', fontSize: '1rem'}}></i>
                </div>
                <span style={{color: 'white', fontWeight: 700, fontSize: '1rem', letterSpacing: '0.3px', whiteSpace: 'nowrap'}}>
                    License Manager
                </span>
            </Link>

            <div style={{width: '1px', height: '24px', background: 'rgba(255,255,255,0.15)', marginRight: '16px', flexShrink: 0}} />

            {/* Nav Items */}
            <div style={{display: 'flex', alignItems: 'center', gap: '2px', flex: 1}}>

                {/* Dashboard — standalone */}
                {(() => {
                    const active = isPathActive('/dashboard');
                    return (
                        <Link to="/dashboard" style={navBtnStyle(active)}
                            onMouseEnter={hoverOn}
                            onMouseLeave={e => hoverOff(e, active)}
                        >
                            <i className="bi bi-speedometer2" style={active ? activeIconStyle : inactiveIconStyle}></i>
                            Dashboard
                        </Link>
                    );
                })()}

                {/* Grouped Dropdowns */}

                {NAV_GROUPS.map(group => {
                    const active = isGroupActive(group.items);
                    return (
                        <div className="dropdown" key={group.label}>
                            <button
                                className="dropdown-toggle"
                                data-bs-toggle="dropdown"
                                style={navBtnStyle(active)}
                                onMouseEnter={hoverOn}
                                onMouseLeave={e => hoverOff(e, active)}
                            >
                                <i className={`bi bi-${group.icon}`} style={active ? activeIconStyle : inactiveIconStyle}></i>
                                {group.label}
                            </button>
                            <ul className="dropdown-menu" style={dropdownMenuStyle}>
                                {group.items.map(item => {
                                    const itemActive = isPathActive(item.path);
                                    return (
                                        <li key={item.path}>
                                            <Link
                                                className={`dropdown-item ${itemActive ? 'active' : ''}`}
                                                to={item.path}
                                                style={dropdownItemStyle}
                                            >
                                                {!itemActive && <i className={`bi bi-${item.icon}`} style={{color: 'var(--primary-color)', fontSize: '0.9rem'}}></i>}
                                                {item.label}
                                            </Link>
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    );
                })}

                {/* Reports Dropdown */}
                {(() => {
                    const active = isGroupActive(reportEntities);
                    return (
                        <div className="dropdown">
                            <button className="dropdown-toggle" data-bs-toggle="dropdown"
                                style={navBtnStyle(active)}
                                onMouseEnter={hoverOn}
                                onMouseLeave={e => hoverOff(e, active)}
                            >
                                <i className="bi bi-bar-chart-line" style={active ? activeIconStyle : inactiveIconStyle}></i>
                                Reports
                            </button>
                            <ul className="dropdown-menu" style={dropdownMenuStyle}>
                                {reportEntities.map(r => {
                                    const itemActive = isPathActive(r.path);
                                    return (
                                        <li key={r.path}>
                                            <Link className={`dropdown-item ${itemActive ? 'active' : ''}`}
                                                to={r.path} style={dropdownItemStyle}>
                                                {!itemActive && <i className={`bi bi-${r.icon}`} style={{color: 'var(--primary-color)', fontSize: '0.9rem'}}></i>}
                                                {r.label}
                                            </Link>
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    );
                })()}

                {/* Masters Dropdown */}
                {(() => {
                    const active = isGroupActive(masterEntities);
                    return (
                        <div className="dropdown">
                            <button className="dropdown-toggle" data-bs-toggle="dropdown"
                                style={navBtnStyle(active)}
                                onMouseEnter={hoverOn}
                                onMouseLeave={e => hoverOff(e, active)}
                            >
                                <i className="bi bi-database" style={active ? activeIconStyle : inactiveIconStyle}></i>
                                Masters
                            </button>
                            <ul className="dropdown-menu" style={dropdownMenuStyle}>
                                {masterEntities.filter(m => !m.deprecated).map(m => {
                                    const itemActive = isPathActive(m.path);
                                    return (
                                        <li key={m.path}>
                                            <Link className={`dropdown-item ${itemActive ? 'active' : ''}`}
                                                to={m.path} style={dropdownItemStyle}>
                                                {!itemActive && <i className={`bi bi-${m.icon}`} style={{color: 'var(--primary-color)', fontSize: '0.9rem'}}></i>}
                                                {m.label}
                                            </Link>
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    );
                })()}

            </div>

            {/* Right — User Dropdown */}
            {user && (
                <div className="dropdown" style={{flexShrink: 0, marginLeft: '12px'}}>
                    <button className="dropdown-toggle" data-bs-toggle="dropdown" style={{
                        display: 'flex', alignItems: 'center', gap: '8px',
                        background: 'rgba(255,255,255,0.12)',
                        border: '1px solid rgba(255,255,255,0.2)',
                        borderRadius: '8px',
                        color: 'white', fontWeight: 500, fontSize: '0.85rem',
                        padding: '6px 14px', cursor: 'pointer', whiteSpace: 'nowrap',
                    }}>
                        <div style={{
                            width: '26px', height: '26px', borderRadius: '50%',
                            background: 'linear-gradient(135deg, var(--primary-light) 0%, var(--primary-color) 100%)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '0.75rem', fontWeight: 700, color: 'white',
                        }}>
                            {user.username?.charAt(0).toUpperCase()}
                        </div>
                        {user.username}
                    </button>
                    <ul className="dropdown-menu dropdown-menu-end" style={{...dropdownMenuStyle, marginTop: '6px'}}>
                        <li style={{padding: '8px 12px 6px'}}>
                            <div style={{fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.5px'}}>Signed in as</div>
                            <div style={{fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-dark)'}}>{user.username}</div>
                        </li>
                        <li><hr className="dropdown-divider" style={{margin: '4px 0'}} /></li>
                        <li>
                            <Link className="dropdown-item" to="/profile" style={dropdownItemStyle}>
                                <i className="bi bi-person" style={{color: 'var(--primary-color)'}}></i>
                                Profile
                            </Link>
                        </li>
                        <li>
                            <Link className="dropdown-item" to="/settings" style={dropdownItemStyle}>
                                <i className="bi bi-gear" style={{color: 'var(--text-secondary)'}}></i>
                                Settings
                            </Link>
                        </li>
                        <li><hr className="dropdown-divider" style={{margin: '4px 0'}} /></li>
                        <li>
                            <button className="dropdown-item" onClick={logout} style={{
                                ...dropdownItemStyle,
                                color: 'var(--danger-color)',
                                width: '100%', background: 'none', border: 'none', cursor: 'pointer',
                            }}>
                                <i className="bi bi-box-arrow-right"></i>
                                Sign out
                            </button>
                        </li>
                    </ul>
                </div>
            )}
        </nav>
    );
}
