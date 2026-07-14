import { Check, CheckCircle2, FileText, Info, Wand2 } from "lucide-react";

interface BoeParsePanelProps {
    boePdfFile: File | null;
    setBoePdfFile: (f: File | null) => void;
    boeParsing: boolean;
    boeParseSummary: any;
    setBoeParseSummary: (s: any) => void;
    handleParseBoePdf: () => void;
}

/** "Import from BOE PDF" parse/upload panel (create mode) — extracted from MasterForm. */
export default function BoeParsePanel({
    boePdfFile, setBoePdfFile, boeParsing, boeParseSummary,
    setBoeParseSummary, handleParseBoePdf,
}: BoeParsePanelProps) {
    return (
                        <section className="surface-card mb-4" style={{ padding: 20 }}>
                            <div className="flex items-start" style={{ gap: 16, flexWrap: 'wrap' }}>
                                <div
                                    aria-hidden="true"
                                    style={{
                                        width: 44, height: 44, borderRadius: 12,
                                        background: 'var(--indigo-50)', color: 'var(--primary-color)',
                                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                        flexShrink: 0,
                                    }}
                                >
                                    <FileText className="size-4" aria-hidden="true" />
                                </div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
                                        Import from BOE PDF
                                    </div>
                                    <div className="mt-1" style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                                        Upload an ICEGATE BOE, then click <strong>Fetch</strong> to prefill the form and item rows.
                                    </div>
                                    <div className="flex items-center mt-3" style={{ gap: 10, flexWrap: 'wrap' }}>
                                        <input
                                            type="file"
                                            accept=".pdf,application/pdf"
                                            id="boe-pdf-input"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            style={{ maxWidth: 340 }}
                                            onChange={(e) => {
                                                setBoePdfFile(e.target.files?.[0] || null);
                                                setBoeParseSummary(null);
                                            }}
                                        />
                                        <button
                                            type="button"
                                            className="flex items-center gap-1.5 rounded bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground cursor-pointer hover:bg-primary/90"
                                            onClick={handleParseBoePdf}
                                            disabled={!boePdfFile || boeParsing}
                                        >
                                            {boeParsing ? (
                                                <><span className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent" role="status" aria-hidden="true"></span>Fetching…</>
                                            ) : (
                                                <><Wand2 className="size-4" aria-hidden="true" />Fetch</>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            </div>
                            {boeParseSummary && (
                                <div
                                    className="mt-3"
                                    style={{
                                        background: 'var(--surface-sunken)',
                                        border: '1px solid var(--border-subtle)',
                                        borderRadius: 'var(--radius-md)',
                                        padding: '12px 14px',
                                        fontSize: '0.8125rem',
                                    }}
                                >
                                    <div style={{ color: 'var(--text-primary)' }}>
                                        <strong>BE {boeParseSummary.be_number}</strong>
                                        <span style={{ color: 'var(--text-tertiary)' }}> · </span>{boeParseSummary.be_date}
                                        <span style={{ color: 'var(--text-tertiary)' }}> · </span>port <code>{boeParseSummary.port_code}</code>
                                        <span style={{ color: 'var(--text-tertiary)' }}> · </span>1 {boeParseSummary.currency || 'USD'} = ₹{boeParseSummary.exchange_rate}
                                    </div>
                                    {boeParseSummary.company_created && (
                                        <div className="mt-1" style={{ color: 'var(--tb-success-text)' }}>
                                            <CheckCircle2 className="size-4" aria-hidden="true" />
                                            New company created from buyer details ({boeParseSummary.buyer_name}).
                                        </div>
                                    )}
                                    {!boeParseSummary.company_created && boeParseSummary.matched_company_id && (
                                        <div className="mt-1" style={{ color: 'var(--text-secondary)' }}>
                                            <Check className="size-4" aria-hidden="true" />
                                            Matched existing company ({boeParseSummary.buyer_name}).
                                        </div>
                                    )}
                                    {boeParseSummary.matched_allotment_id && (
                                        <div className="mt-1" style={{ color: 'var(--primary-deeper)' }}>
                                            <Info className="size-4" aria-hidden="true" />
                                            Matched existing allotment <strong>#{boeParseSummary.matched_allotment_id}</strong> by invoice number.
                                        </div>
                                    )}
                                    {boeParseSummary.licences?.length > 0 && (
                                        <details className="mt-2">
                                            <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)' }}>
                                                {boeParseSummary.licences.length} licence row(s) — {boeParseSummary.unmatched} unmatched
                                            </summary>
                                            <ul className="mb-0 mt-2" style={{ paddingLeft: '1.1rem', color: 'var(--text-secondary)' }}>
                                                {boeParseSummary.licences.map((l, i) => {
                                                    const badge = l.match_status === 'matched'
                                                        ? <span style={{ color: 'var(--tb-success-text)', marginLeft: 6 }}>✓ prefill item</span>
                                                        : l.match_status === 'license_only'
                                                            ? <span style={{ color: 'var(--tb-warning-text)', marginLeft: 6 }}>⚠ license found, sl#{l.licence_slno} missing</span>
                                                            : l.match_status === 'license_missing'
                                                                ? <span style={{ color: 'var(--tb-danger-text)', marginLeft: 6 }}>✗ license not in DB</span>
                                                                : <span style={{ color: 'var(--text-tertiary)', marginLeft: 6 }}>— no data</span>;
                                                    return (
                                                        <li key={i} style={{ padding: '2px 0' }}>
                                                            License <code>{l.licence_number}</code> sl#{l.licence_slno} · CIF ₹{l.cif_inr} · ${l.cif_fc} · qty {l.qty} {l.uqc}
                                                            {badge}
                                                        </li>
                                                    );
                                                })}
                                            </ul>
                                        </details>
                                    )}
                                </div>
                            )}
                        </section>
    );
}
