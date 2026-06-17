import { Layers, MapPin, X } from "lucide-react";

interface BoeMergeModalProps {
    mergeBoeTarget: any;
    closeMergeModal: () => void;
    mergeCandidatesLoading: boolean;
    mergeCandidates: any[];
    mergeBoeSource: any;
    setMergeBoeSource: (updater: any) => void;
    mergeBoeLoading: boolean;
    doMerge: () => void;
}

/** BOE merge modal — extracted verbatim from MasterList. */
export default function BoeMergeModal({ mergeBoeTarget, closeMergeModal, mergeCandidatesLoading, mergeCandidates, mergeBoeSource, setMergeBoeSource, mergeBoeLoading, doMerge }: BoeMergeModalProps) {
    return (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 1060, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={closeMergeModal}>
                    <div style={{ background: 'var(--tb-card-bg)', borderRadius: 'var(--tb-r-md)', padding: '24px', width: '560px', maxWidth: '95vw', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }} onClick={e => e.stopPropagation()}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                            <h6 style={{ margin: 0, fontWeight: '700', color: 'var(--tb-brand-active)' }}>
                                <Layers className="size-4" aria-hidden="true" />
                                Merge BOE: <span style={{ color: 'var(--accent-color)' }}>{mergeBoeTarget.bill_of_entry_number}</span>
                            </h6>
                            <button onClick={closeMergeModal} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: 'var(--tb-text-tertiary)' }}>
                                <X className="size-4" aria-hidden="true" />
                            </button>
                        </div>

                        {/* Target BOE info */}
                        <div style={{ background: 'var(--tb-success-soft)', border: '1px solid #86efac', borderRadius: 'var(--tb-r-md)', padding: '10px 14px', marginBottom: '16px', fontSize: 13.5 }}>
                            <div style={{ fontWeight: '600', color: 'var(--tb-success-text)', marginBottom: '4px' }}>Target BOE (will be kept &amp; updated)</div>
                            <div><MapPin className="size-4" aria-hidden="true" />{mergeBoeTarget.port_name}</div>
                            <div style={{ color: 'var(--tb-text-secondary)', fontSize: 12 }}>
                                {mergeBoeTarget.item_details?.length || 0} item(s) · {mergeBoeTarget.licenses || 'No licenses'}
                            </div>
                        </div>

                        <div style={{ fontWeight: '600', fontSize: 12, color: 'var(--tb-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                            Select source BOE to merge from (port replaces target, items moved, source deleted):
                        </div>

                        {mergeCandidatesLoading && (
                            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--tb-text-tertiary)' }}>
                                <span className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" aria-hidden="true" />Loading candidates...
                            </div>
                        )}

                        {!mergeCandidatesLoading && mergeCandidates.length === 0 && (
                            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--tb-text-tertiary)', fontSize: 14 }}>
                                No other BOEs found with number {mergeBoeTarget.bill_of_entry_number}
                            </div>
                        )}

                        {mergeCandidates.map(candidate => (
                            <div
                                key={candidate.id}
                                onClick={() => setMergeBoeSource(prev => prev?.id === candidate.id ? null : candidate)}
                                style={{
                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                    padding: '10px 14px', border: `2px solid ${mergeBoeSource?.id === candidate.id ? 'var(--accent-color)' : 'var(--tb-border-soft)'}`,
                                    borderRadius: 'var(--tb-r-md)', marginBottom: '8px', cursor: 'pointer',
                                    background: mergeBoeSource?.id === candidate.id ? 'var(--tb-sunken)' : 'var(--tb-card-bg)',
                                    transition: 'all 0.15s'
                                }}
                            >
                                <div>
                                    <div style={{ fontWeight: '600', fontSize: 14, color: 'var(--tb-text)' }}>
                                        <MapPin className="size-4" aria-hidden="true" />{candidate.port_name}
                                    </div>
                                    <div style={{ fontSize: 12, color: 'var(--tb-text-secondary)' }}>
                                        {candidate.item_details?.length || 0} item(s) · {candidate.licenses || 'No licenses'}
                                    </div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    {candidate.total_inr && (
                                        <div style={{ fontWeight: '700', fontSize: 14, color: 'var(--tb-text)' }}>
                                            ₹{Number(candidate.total_inr).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                        </div>
                                    )}
                                    {mergeBoeSource?.id === candidate.id && (
                                        <span style={{ fontSize: 11, color: 'var(--accent-color)', fontWeight: '700' }}>✓ Selected</span>
                                    )}
                                </div>
                            </div>
                        ))}

                        {mergeBoeSource && (
                            <div style={{ background: 'var(--tb-sunken)', border: '1px solid #c4b5fd', borderRadius: 'var(--tb-r-md)', padding: '10px 14px', margin: '12px 0', fontSize: '0.82rem', color: 'var(--accent-color)' }}>
                                <strong>What will happen:</strong>
                                <ul style={{ margin: '6px 0 0 0', paddingLeft: '20px' }}>
                                    <li>Target port will change to <strong>{mergeBoeSource.port_name}</strong></li>
                                    <li>Items from source will be moved to target (duplicates skipped)</li>
                                    <li>Source BOE ({mergeBoeSource.port_name}) will be permanently deleted</li>
                                </ul>
                            </div>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                            <button onClick={closeMergeModal} style={{ padding: '6px 16px', borderRadius: 'var(--tb-r-sm)', border: '1px solid var(--tb-border)', background: 'var(--tb-sunken)', cursor: 'pointer', fontSize: 14 }}>
                                Cancel
                            </button>
                            <button
                                onClick={doMerge}
                                disabled={!mergeBoeSource || mergeBoeLoading}
                                style={{ padding: '6px 16px', borderRadius: 'var(--tb-r-sm)', border: 'none', background: mergeBoeSource && !mergeBoeLoading ? 'var(--accent-color)' : 'var(--accent-light)', color: '#fff', cursor: mergeBoeSource && !mergeBoeLoading ? 'pointer' : 'not-allowed', fontSize: 14, fontWeight: '600', display: 'flex', alignItems: 'center', gap: '6px' }}
                            >
                                {mergeBoeLoading
                                    ? <><div className="" style={{ width: '14px', height: '14px', borderWidth: '2px' }}></div>Merging...</>
                                    : <><Layers className="size-4" aria-hidden="true" />Confirm Merge</>
                                }
                            </button>
                        </div>
                    </div>
                </div>
    );
}
