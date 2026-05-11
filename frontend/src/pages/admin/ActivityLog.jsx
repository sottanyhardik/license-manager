import {useCallback, useContext, useEffect, useRef, useState} from 'react';
import {toast} from 'react-toastify';
import api from '../../api/axios';
import {AuthContext} from '../../context/AuthContext';
import {getErrorMessage} from '../../utils/errorUtils';

const ACTION_COLORS = {
    LOGIN:    {bg: '#dcfce7', color: '#166534', icon: 'bi-box-arrow-in-right'},
    LOGOUT:   {bg: '#fee2e2', color: '#991b1b', icon: 'bi-box-arrow-right'},
    VIEW:     {bg: '#f0f9ff', color: '#0369a1', icon: 'bi-eye'},
    CREATE:   {bg: '#f0fdf4', color: '#15803d', icon: 'bi-plus-circle'},
    UPDATE:   {bg: '#fef9c3', color: '#854d0e', icon: 'bi-pencil'},
    DELETE:   {bg: '#fff1f2', color: '#be123c', icon: 'bi-trash'},
    DOWNLOAD: {bg: '#faf5ff', color: '#6d28d9', icon: 'bi-download'},
    UPLOAD:   {bg: '#fdf4ff', color: '#a21caf', icon: 'bi-upload'},
    EXPORT:   {bg: '#ecfdf5', color: '#065f46', icon: 'bi-file-earmark-arrow-down'},
    SEARCH:   {bg: '#f8fafc', color: '#475569', icon: 'bi-search'},
};

const ACTIONS = ['LOGIN','LOGOUT','VIEW','CREATE','UPDATE','DELETE','DOWNLOAD','UPLOAD','EXPORT','SEARCH'];

const fmtDate = (ts) => {
    if (!ts) return '—';
    const d = new Date(ts);
    return d.toLocaleString('en-IN', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    });
};

export default function ActivityLog() {
    const {user} = useContext(AuthContext);

    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [filters, setFilters] = useState({
        username: '', action: '', module: '',
        date_from: '', date_to: '', search: '', limit: '200',
    });

    const abortRef = useRef(null);

    const fetchLogs = useCallback(async () => {
        if (abortRef.current) abortRef.current.abort();
        abortRef.current = new AbortController();

        setLoading(true);
        try {
            const params = Object.fromEntries(
                Object.entries(filters).filter(([, v]) => v !== '')
            );
            const {data} = await api.get('masters/activity-logs/', {
                params,
                signal: abortRef.current.signal,
            });
            setLogs(Array.isArray(data) ? data : data.results ?? []);
        } catch (err) {
            if (err.name !== 'CanceledError' && err.name !== 'AbortError') {
                toast.error(getErrorMessage(err));
            }
        } finally {
            setLoading(false);
        }
    }, [filters]);

    useEffect(() => {
        fetchLogs();
    }, [fetchLogs]);

    const handleFilter = (key, value) =>
        setFilters(prev => ({...prev, [key]: value}));

    return (
        <div className="container-fluid py-4">
            {/* Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h4 className="fw-bold mb-0">
                        <i className="bi bi-journal-text me-2 text-primary"></i>
                        Activity Log
                    </h4>
                    <small className="text-muted">
                        {user?.is_superuser ? 'All user actions across the system' : 'Your recent activity'}
                    </small>
                </div>
                <button className="btn btn-sm btn-outline-primary" onClick={fetchLogs} disabled={loading}>
                    <i className="bi bi-arrow-clockwise me-1"></i>Refresh
                </button>
            </div>

            {/* Filters */}
            <div className="card mb-3">
                <div className="card-body py-2">
                    <div className="row g-2 align-items-end">
                        {user?.is_superuser && (
                            <div className="col-md-2">
                                <label className="form-label small fw-semibold mb-1">Username</label>
                                <input className="form-control form-control-sm" placeholder="Search user…"
                                       value={filters.username}
                                       onChange={e => handleFilter('username', e.target.value)}/>
                            </div>
                        )}
                        <div className="col-md-2">
                            <label className="form-label small fw-semibold mb-1">Action</label>
                            <select className="form-select form-select-sm"
                                    value={filters.action}
                                    onChange={e => handleFilter('action', e.target.value)}>
                                <option value="">All Actions</option>
                                {ACTIONS.map(a => (
                                    <option key={a} value={a}>{a}</option>
                                ))}
                            </select>
                        </div>
                        <div className="col-md-2">
                            <label className="form-label small fw-semibold mb-1">Module</label>
                            <input className="form-control form-control-sm" placeholder="e.g. licenses"
                                   value={filters.module}
                                   onChange={e => handleFilter('module', e.target.value)}/>
                        </div>
                        <div className="col-md-2">
                            <label className="form-label small fw-semibold mb-1">From</label>
                            <input type="date" className="form-control form-control-sm"
                                   value={filters.date_from}
                                   onChange={e => handleFilter('date_from', e.target.value)}/>
                        </div>
                        <div className="col-md-2">
                            <label className="form-label small fw-semibold mb-1">To</label>
                            <input type="date" className="form-control form-control-sm"
                                   value={filters.date_to}
                                   onChange={e => handleFilter('date_to', e.target.value)}/>
                        </div>
                        <div className="col-md-2">
                            <label className="form-label small fw-semibold mb-1">Search</label>
                            <input className="form-control form-control-sm" placeholder="IP, description…"
                                   value={filters.search}
                                   onChange={e => handleFilter('search', e.target.value)}/>
                        </div>
                    </div>
                </div>
            </div>

            {/* Stats row */}
            {!loading && logs.length > 0 && (
                <div className="d-flex gap-2 flex-wrap mb-3">
                    {ACTIONS.filter(a => logs.some(l => l.action === a)).map(a => {
                        const c = ACTION_COLORS[a] ?? {};
                        const count = logs.filter(l => l.action === a).length;
                        return (
                            <span key={a} className="badge"
                                  style={{background: c.bg, color: c.color, fontSize: '0.75rem', padding: '5px 10px', cursor: 'pointer'}}
                                  onClick={() => handleFilter('action', filters.action === a ? '' : a)}>
                                <i className={`bi ${c.icon} me-1`}></i>{a} <strong>{count}</strong>
                            </span>
                        );
                    })}
                    <button className="btn btn-sm btn-link text-muted ms-auto p-0"
                            onClick={() => setFilters(f => ({...f, action: '', username: '', module: '', search: '', date_from: '', date_to: ''}))}>
                        Clear filters
                    </button>
                </div>
            )}

            {/* Table */}
            <div className="card">
                <div className="card-body p-0">
                    {loading ? (
                        <div className="p-5 text-center">
                            <div className="spinner-border text-primary" role="status"/>
                            <div className="mt-2 text-muted small">Loading activity log…</div>
                        </div>
                    ) : logs.length === 0 ? (
                        <div className="p-5 text-center text-muted">
                            <i className="bi bi-journal-x" style={{fontSize: '2rem'}}></i>
                            <div className="mt-2">No activity records found</div>
                        </div>
                    ) : (
                        <div className="table-responsive">
                            <table className="table table-hover table-sm mb-0 align-middle">
                                <thead className="table-light">
                                <tr>
                                    <th style={{width: 160}}>Time</th>
                                    {user?.is_superuser && <th>User</th>}
                                    <th style={{width: 110}}>Action</th>
                                    <th>Module</th>
                                    <th>Description</th>
                                    <th style={{width: 60}}>Status</th>
                                    <th style={{width: 130}}>IP Address</th>
                                </tr>
                                </thead>
                                <tbody>
                                {logs.map(log => {
                                    const ac = ACTION_COLORS[log.action] ?? {bg: '#f8fafc', color: '#475569', icon: 'bi-circle'};
                                    const isError = log.status_code && log.status_code >= 400;
                                    return (
                                        <tr key={log.id} style={isError ? {background: '#fff5f5'} : {}}>
                                            <td className="text-muted" style={{fontSize: '0.78rem', whiteSpace: 'nowrap'}}>
                                                {fmtDate(log.timestamp)}
                                            </td>
                                            {user?.is_superuser && (
                                                <td>
                                                    <div className="d-flex align-items-center gap-2">
                                                        <div style={{
                                                            width: 24, height: 24, borderRadius: '50%',
                                                            background: 'linear-gradient(135deg,#4F46E5,#6366F1)',
                                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                            color: 'white', fontSize: '0.65rem', fontWeight: 700, flexShrink: 0,
                                                        }}>
                                                            {(log.username || '?')[0].toUpperCase()}
                                                        </div>
                                                        <span className="fw-medium small">{log.username || '—'}</span>
                                                    </div>
                                                </td>
                                            )}
                                            <td>
                                                <span className="badge" style={{
                                                    background: ac.bg, color: ac.color,
                                                    fontSize: '0.7rem', padding: '3px 8px',
                                                }}>
                                                    <i className={`bi ${ac.icon} me-1`}></i>{log.action}
                                                </span>
                                            </td>
                                            <td>
                                                <span style={{fontSize: '0.78rem', color: '#475569'}}>
                                                    {log.module || '—'}
                                                </span>
                                                {log.resource_id && (
                                                    <span className="ms-1 text-muted" style={{fontSize: '0.7rem'}}>
                                                        #{log.resource_id}
                                                    </span>
                                                )}
                                            </td>
                                            <td style={{fontSize: '0.78rem', maxWidth: 300}}>
                                                <span className="text-truncate d-block" title={log.description}>
                                                    {log.description || log.endpoint || '—'}
                                                </span>
                                            </td>
                                            <td>
                                                {log.status_code ? (
                                                    <span className={`badge bg-${isError ? 'danger' : 'success'} bg-opacity-${isError ? '100' : '75'}`}
                                                          style={{fontSize: '0.68rem'}}>
                                                        {log.status_code}
                                                    </span>
                                                ) : '—'}
                                            </td>
                                            <td className="text-muted" style={{fontSize: '0.75rem'}}>
                                                {log.ip_address || '—'}
                                            </td>
                                        </tr>
                                    );
                                })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
                {!loading && logs.length > 0 && (
                    <div className="card-footer text-muted small d-flex justify-content-between">
                        <span>Showing {logs.length} records</span>
                        <span>Most recent first</span>
                    </div>
                )}
            </div>
        </div>
    );
}
