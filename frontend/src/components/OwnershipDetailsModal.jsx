import { useState, useEffect } from 'react';
import api from '../api/axios';
import { toast } from 'react-toastify';

function fmtDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function CompanyLabel({ iec, name }) {
    if (!iec && !name) return <span style={{ color: '#9ca3af' }}>—</span>;
    return (
        <span>
            <span style={{ fontFamily: 'monospace' }}>{iec || '—'}</span>
            {name ? <span style={{ color: '#475569' }}> ({name})</span> : null}
        </span>
    );
}

export default function OwnershipDetailsModal({ show, onHide, licenseId, licenseNumber }) {
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!show || !licenseId) return;
        let cancelled = false;
        setLoading(true);
        setError(null);
        setData(null);
        api.get(`license-actions/${licenseId}/ownership-data/`)
            .then((r) => {
                if (cancelled) return;
                setData(r.data);
            })
            .catch((err) => {
                if (cancelled) return;
                const msg = err?.response?.data?.error || err?.message || 'Failed to load ownership data';
                setError(msg);
                toast.error(msg);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => { cancelled = true; };
    }, [show, licenseId]);

    if (!show) return null;

    const owner = data?.current_owner;
    const transfers = data?.transfers || [];

    return (
        <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.6)' }} onClick={onHide}>
            <div className="modal-dialog modal-xl" style={{ maxWidth: '95%' }} onClick={(e) => e.stopPropagation()}>
                <div className="modal-content" style={{ borderRadius: '12px', boxShadow: '0 10px 40px rgba(0,0,0,0.2)', border: 'none' }}>
                    <div className="modal-header" style={{
                        background: 'linear-gradient(135deg, #3730a3 0%, #1e1b4b 100%)',
                        color: 'white', borderTopLeftRadius: '12px', borderTopRightRadius: '12px',
                        padding: '1rem 1.5rem', borderBottom: 'none',
                    }}>
                        <h5 className="modal-title" style={{ fontWeight: 600, fontSize: '1.1rem', flex: 1 }}>
                            <i className="bi bi-diagram-3 me-2"></i>
                            Ownership Details{licenseNumber ? ` — ${licenseNumber}` : ''}
                        </h5>
                        <button type="button" onClick={onHide} aria-label="Close" style={{ background: 'transparent', border: 'none', color: 'white', fontSize: '1.25rem', cursor: 'pointer' }}>
                            <i className="bi bi-x-lg"></i>
                        </button>
                    </div>

                    <div className="modal-body" style={{ padding: '1.5rem', maxHeight: '75vh', overflowY: 'auto' }}>
                        {loading && (
                            <div style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>
                                <i className="bi bi-arrow-repeat spinner-border spinner-border-sm me-2"></i>
                                Loading ownership data…
                            </div>
                        )}

                        {!loading && error && (
                            <div className="alert alert-danger" role="alert">{error}</div>
                        )}

                        {!loading && !error && data && (
                            <>
                                {/* Current Owner */}
                                <div style={{ marginBottom: '1.5rem' }}>
                                    <div style={{
                                        background: 'linear-gradient(135deg, #3730a3 0%, #1e1b4b 100%)',
                                        color: 'white', padding: '0.75rem 1rem', borderRadius: '8px 8px 0 0',
                                        fontWeight: 600, fontSize: '0.95rem',
                                    }}>
                                        Current Owner&apos;s Details
                                    </div>
                                    <div style={{ border: '1px solid #e5e7eb', borderTop: 'none', borderRadius: '0 0 8px 8px', padding: '1rem', background: '#fff' }}>
                                        {owner ? (
                                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                                                <div>
                                                    <div style={{ color: '#6b7280', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>IEC</div>
                                                    <div style={{ fontFamily: 'monospace', marginTop: '0.25rem' }}>{owner.iec || '—'}</div>
                                                </div>
                                                <div>
                                                    <div style={{ color: '#6b7280', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Firm / Company</div>
                                                    <div style={{ marginTop: '0.25rem' }}>{owner.name || '—'}</div>
                                                </div>
                                                <div style={{ gridColumn: 'span 2' }}>
                                                    <div style={{ color: '#6b7280', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Address</div>
                                                    <div style={{ marginTop: '0.25rem' }}>{owner.address || '—'}</div>
                                                </div>
                                            </div>
                                        ) : (
                                            <div style={{ color: '#9ca3af' }}>No current owner recorded.</div>
                                        )}
                                        <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px dashed #e5e7eb', display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#6b7280' }}>
                                            <span>Last fetched: {fmtDateTime(data.last_ownership_fetch)}</span>
                                            {data.file_transfer_status && (
                                                <span><strong>File transfer:</strong> {data.file_transfer_status}</span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Transfer Details */}
                                <div>
                                    <div style={{
                                        background: 'linear-gradient(135deg, #3730a3 0%, #1e1b4b 100%)',
                                        color: 'white', padding: '0.75rem 1rem', borderRadius: '8px 8px 0 0',
                                        fontWeight: 600, fontSize: '0.95rem',
                                    }}>
                                        Transfer Details {transfers.length > 0 && <span style={{ fontWeight: 400, opacity: 0.85 }}>({transfers.length})</span>}
                                    </div>
                                    <div style={{ border: '1px solid #e5e7eb', borderTop: 'none', borderRadius: '0 0 8px 8px', background: '#fff', overflowX: 'auto' }}>
                                        {transfers.length === 0 ? (
                                            <div style={{ padding: '1rem', color: '#9ca3af' }}>No transfers recorded.</div>
                                        ) : (
                                            <table className="table table-sm mb-0" style={{ fontSize: '0.85rem' }}>
                                                <thead style={{ background: '#fef2f2' }}>
                                                    <tr>
                                                        <th style={{ padding: '0.75rem' }}>Initiation Date</th>
                                                        <th style={{ padding: '0.75rem' }}>Acceptance Date</th>
                                                        <th style={{ padding: '0.75rem' }}>From IEC</th>
                                                        <th style={{ padding: '0.75rem' }}>To IEC</th>
                                                        <th style={{ padding: '0.75rem' }}>Status</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {transfers.map((t, i) => (
                                                        <tr key={i}>
                                                            <td style={{ padding: '0.65rem 0.75rem' }}>{fmtDateTime(t.transfer_initiation_date)}</td>
                                                            <td style={{ padding: '0.65rem 0.75rem' }}>{fmtDateTime(t.transfer_acceptance_date)}</td>
                                                            <td style={{ padding: '0.65rem 0.75rem' }}><CompanyLabel iec={t.from_iec} name={t.from_name} /></td>
                                                            <td style={{ padding: '0.65rem 0.75rem' }}><CompanyLabel iec={t.to_iec} name={t.to_name} /></td>
                                                            <td style={{ padding: '0.65rem 0.75rem' }}>
                                                                <span style={{
                                                                    display: 'inline-block', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600,
                                                                    background: (t.transfer_status || '').toLowerCase() === 'approved' ? '#dcfce7' : '#fef3c7',
                                                                    color: (t.transfer_status || '').toLowerCase() === 'approved' ? '#166534' : '#92400e',
                                                                }}>
                                                                    {t.transfer_status || '—'}
                                                                </span>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        )}
                                    </div>
                                </div>
                            </>
                        )}
                    </div>

                    <div className="modal-footer" style={{ borderTop: '1px solid #e5e7eb', padding: '0.75rem 1.5rem' }}>
                        <button type="button" className="btn btn-secondary" onClick={onHide}>Close</button>
                    </div>
                </div>
            </div>
        </div>
    );
}
