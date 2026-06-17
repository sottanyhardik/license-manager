import { Check, CheckCircle2, FileText, Paperclip, QrCode, RefreshCw, TriangleAlert, Wand2 } from "lucide-react";

interface LicenseParsePanelProps {
    licensePdfFile: File | null;
    setLicensePdfFile: (f: File | null) => void;
    licenseParsing: boolean;
    licenseParseSummary: any;
    setLicenseParseSummary: (s: any) => void;
    existingLicenseCopy: any;
    existingLicenseCopyName: string;
    handleParseLicensePdf: () => void;
    handleReparseExistingCopy: () => void;
}

/** "Import from Licence Copy" parse/upload panel — extracted verbatim from MasterForm. */
export default function LicenseParsePanel({
    licensePdfFile, setLicensePdfFile, licenseParsing, licenseParseSummary,
    setLicenseParseSummary, existingLicenseCopy, existingLicenseCopyName,
    handleParseLicensePdf, handleReparseExistingCopy,
}: LicenseParsePanelProps) {
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
                                        Import from Licence Copy
                                    </div>
                                    <div className="mt-1" style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                                        Upload the DFIA licence PDF and click <strong>Fetch</strong> to prefill the form. Digital PDFs parse instantly; scanned copies with a DGFT QR code are downloaded fresh from DGFT (~10–15s).
                                    </div>
                                    <div className="flex items-center mt-3" style={{ gap: 10, flexWrap: 'wrap' }}>
                                        <input
                                            type="file"
                                            accept=".pdf,application/pdf"
                                            id="licence-pdf-input"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            style={{ maxWidth: 340 }}
                                            onChange={(e) => {
                                                setLicensePdfFile(e.target.files?.[0] || null);
                                                setLicenseParseSummary(null);
                                            }}
                                        />
                                        <button
                                            type="button"
                                            className="flex items-center gap-1.5 rounded bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground cursor-pointer hover:bg-primary/90"
                                            onClick={handleParseLicensePdf}
                                            disabled={!licensePdfFile || licenseParsing}
                                        >
                                            {licenseParsing ? (
                                                <><span className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent" role="status" aria-hidden="true"></span>Fetching…</>
                                            ) : (
                                                <><Wand2 className="size-4" aria-hidden="true" />Fetch</>
                                            )}
                                        </button>
                                    </div>

                                    {existingLicenseCopy && (
                                        <div
                                            className="flex items-center mt-2"
                                            style={{
                                                gap: 10,
                                                flexWrap: 'wrap',
                                                background: 'var(--surface-sunken)',
                                                border: '1px solid var(--border-subtle)',
                                                borderRadius: 'var(--radius-md)',
                                                padding: '8px 12px',
                                                fontSize: '0.8125rem',
                                            }}
                                        >
                                            <Paperclip className="size-4" aria-hidden="true" />
                                            <span style={{ color: 'var(--text-primary)', minWidth: 0 }}>
                                                Saved Licence Copy:&nbsp;
                                                <a
                                                    href={existingLicenseCopy.file}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    style={{ fontWeight: 600, wordBreak: 'break-all' }}
                                                >
                                                    {existingLicenseCopyName}
                                                </a>
                                            </span>
                                            <button
                                                type="button"
                                                className="flex items-center gap-1.5 rounded border border-primary/30 bg-primary/5 px-2.5 py-1.5 text-xs font-medium text-primary cursor-pointer hover:bg-primary/10"
                                                onClick={handleReparseExistingCopy}
                                                disabled={licenseParsing}
                                                style={{ marginLeft: 'auto' }}
                                                title="Re-fetch & parse the saved Licence Copy"
                                            >
                                                {licenseParsing ? (
                                                    <><span className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent" role="status" aria-hidden="true"></span>Re-fetching…</>
                                                ) : (
                                                    <><RefreshCw className="size-4" aria-hidden="true" />Re-fetch &amp; parse</>
                                                )}
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                            {licenseParseSummary && (
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
                                        <strong>{licenseParseSummary.license_number}</strong>
                                        <span style={{ color: 'var(--text-tertiary)' }}> · </span>{licenseParseSummary.license_date} → {licenseParseSummary.license_expiry_date}
                                        <span style={{ color: 'var(--text-tertiary)' }}> · </span>port <code>{licenseParseSummary.port_code}</code>
                                        <span style={{ color: 'var(--text-tertiary)' }}> · </span>notification {licenseParseSummary.notification_number}
                                        <span style={{ color: 'var(--text-tertiary)' }}> · </span>file <code>{licenseParseSummary.file_number}</code>
                                    </div>
                                    {licenseParseSummary.source_kind === 'dgft_qr' && (
                                        <div className="mt-1" style={{ color: 'var(--tb-success-text)' }}>
                                            <QrCode className="size-4" aria-hidden="true" />
                                            Fetched fresh digital copy from DGFT via QR code on uploaded scan.
                                        </div>
                                    )}
                                    {licenseParseSummary.source_kind === 'ocr' && (
                                        <div className="mt-1" style={{ color: 'var(--tb-warning-text)' }}>
                                            <TriangleAlert className="size-4" aria-hidden="true" />
                                            Scanned PDF — header fields recovered via OCR. Items table is unreliable; please review/add manually.
                                        </div>
                                    )}
                                    {licenseParseSummary.company_created && (
                                        <div className="mt-1" style={{ color: 'var(--tb-success-text)' }}>
                                            <CheckCircle2 className="size-4" aria-hidden="true" />
                                            New company created ({licenseParseSummary.company_name}).
                                        </div>
                                    )}
                                    {!licenseParseSummary.company_created && licenseParseSummary.matched_company_id && (
                                        <div className="mt-1" style={{ color: 'var(--text-secondary)' }}>
                                            <Check className="size-4" aria-hidden="true" />
                                            Matched existing company ({licenseParseSummary.company_name}).
                                        </div>
                                    )}
                                    {!licenseParseSummary.matched_port_id && licenseParseSummary.port_code && (
                                        <div className="mt-1" style={{ color: 'var(--tb-warning-text)' }}>
                                            <TriangleAlert className="size-4" aria-hidden="true" />
                                            Port code <code>{licenseParseSummary.port_code}</code> not found in master — please add and re-select.
                                        </div>
                                    )}
                                    {licenseParseSummary.items?.length > 0 && (
                                        <details className="mt-2">
                                            <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)' }}>
                                                {licenseParseSummary.items.length} import item(s) — {licenseParseSummary.unmatchedHsn} HSN(s) not in master
                                            </summary>
                                            <ul className="mb-0 mt-2" style={{ paddingLeft: '1.1rem', color: 'var(--text-secondary)' }}>
                                                {licenseParseSummary.items.map((it, i) => (
                                                    <li key={i} style={{ padding: '2px 0' }}>
                                                        sl#{it.serial_number} · HSN <code>{it.hsn}</code> · qty {it.quantity} {it.uom} · CIF ₹{it.cif_inr} / ${it.cif_fc}
                                                        {it.matched_hs_code_id
                                                            ? <span style={{ color: 'var(--tb-success-text)', marginLeft: 6 }}>✓ HSN matched</span>
                                                            : <span style={{ color: 'var(--tb-warning-text)', marginLeft: 6 }}>⚠ HSN not in master</span>}
                                                    </li>
                                                ))}
                                            </ul>
                                        </details>
                                    )}
                                </div>
                            )}
                        </section>
    );
}
