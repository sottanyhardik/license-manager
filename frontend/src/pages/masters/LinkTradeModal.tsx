import { Link as LinkIcon, X } from "lucide-react";
import { clickable } from "../../utils/clickable";
import { formatTruthyInr } from "./masterDisplayFormatters";

interface LinkTradeModalProps {
    linkModalTrade: any;
    closeLinkModal: () => void;
    linkSearch: string;
    setLinkSearch: (v: string) => void;
    linkSearching: boolean;
    linkResults: any[];
    confirmLink: (t: any) => void;
}

/** "Link Trade" search modal — extracted verbatim from MasterList. */
export default function LinkTradeModal({ linkModalTrade, closeLinkModal, linkSearch, setLinkSearch, linkSearching, linkResults, confirmLink }: LinkTradeModalProps) {
    return (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 1060, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={closeLinkModal}>
                    <div style={{ background: 'var(--tb-card-bg)', borderRadius: 'var(--tb-r-md)', padding: '24px', width: '480px', maxWidth: '95vw', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }} onClick={e => e.stopPropagation()}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                            <h6 style={{ margin: 0, fontWeight: '700', color: 'var(--tb-brand-active)' }}>
                                <LinkIcon className="size-4" aria-hidden="true" />
                                Link Trade: <span style={{ color: 'var(--tb-brand)' }}>{linkModalTrade.invoice_number || 'No Invoice'}</span>
                            </h6>
                            <button onClick={closeLinkModal} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: 'var(--tb-text-tertiary)' }}>
                                <X className="size-4" aria-hidden="true" />
                            </button>
                        </div>
                        <input
                            autoFocus
                            type="text"
                            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                            placeholder="Search by invoice number..."
                            value={linkSearch}
                            onChange={e => setLinkSearch(e.target.value)}
                            style={{ marginBottom: '12px' }}
                        />
                        {linkSearching && <div style={{ textAlign: 'center', color: 'var(--tb-text-tertiary)', padding: '12px' }}><span className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" aria-hidden="true" />Searching...</div>}
                        {!linkSearching && linkSearch && linkResults.length === 0 && (
                            <div style={{ textAlign: 'center', color: 'var(--tb-text-tertiary)', padding: '12px', fontSize: 14 }}>No unlinked trades found for "{linkSearch}"</div>
                        )}
                        {linkResults.map(t => (
                            <div key={t.id} {...clickable(() => confirmLink(t))} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', border: '1px solid var(--tb-border)', borderRadius: 'var(--tb-r-md)', marginBottom: '8px', cursor: 'pointer', transition: 'background 0.15s' }}
                                onMouseEnter={e => e.currentTarget.style.background = 'var(--tb-info-soft)'}
                                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                                <div>
                                    <div style={{ fontWeight: '600', fontSize: 14.5, color: 'var(--tb-text)' }}>{t.invoice_number || 'No Invoice'}</div>
                                    <div style={{ fontSize: 12, color: 'var(--tb-text-secondary)' }}>{t.from_company_label} → {t.to_company_label}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <span style={{ fontSize: 12, fontWeight: '700', color: t.direction.includes('SALE') ? 'var(--tb-success-text)' : 'var(--tb-brand-hover)', background: t.direction.includes('SALE') ? 'var(--tb-success-soft)' : 'var(--tb-brand-100)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)' }}>
                                        {t.direction_label || t.direction}
                                    </span>
                                    <div style={{ fontSize: 12, color: 'var(--tb-text-secondary)', marginTop: '4px' }}>
                                        {formatTruthyInr(t.total_amount, "-")}
                                    </div>
                                </div>
                            </div>
                        ))}
                        {!linkSearch && (
                            <div style={{ textAlign: 'center', color: 'var(--tb-text-tertiary)', fontSize: 14, padding: '8px' }}>Type an invoice number to search</div>
                        )}
                    </div>
                </div>
    );
}
