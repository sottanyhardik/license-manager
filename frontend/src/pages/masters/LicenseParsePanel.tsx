import { Check, CheckCircle2, FileText, Paperclip, QrCode, RefreshCw, TriangleAlert, Wand2 } from "lucide-react";
import { openDocument } from "../../utils/documentDownload";

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
                        <section className="rounded-lg border border-border bg-card mb-4 p-5">
                            <div className="flex items-start gap-4 flex-wrap">
                                <span
                                    aria-hidden="true"
                                    className="inline-flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-primary/5 text-primary"
                                >
                                    <FileText className="size-4" aria-hidden="true" />
                                </span>
                                <div className="flex-1 min-w-0">
                                    <div className="text-[15px] font-semibold text-foreground tracking-tight">
                                        Import from Licence Copy
                                    </div>
                                    <div className="mt-1 text-[0.8125rem] text-muted-foreground">
                                        Upload the DFIA licence PDF and click <strong>Fetch</strong> to prefill the form. Digital PDFs parse instantly; scanned copies with a DGFT QR code are downloaded fresh from DGFT (~10–15s).
                                    </div>
                                    <div className="flex items-center mt-3 gap-2.5 flex-wrap">
                                        <input
                                            type="file"
                                            accept=".pdf,application/pdf"
                                            id="licence-pdf-input"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring max-w-[340px]"
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
                                        <div className="flex items-center mt-2 gap-2.5 flex-wrap rounded-md border border-border bg-muted/40 px-3 py-2 text-[0.8125rem]">
                                            <Paperclip className="size-4" aria-hidden="true" />
                                            <span className="text-foreground min-w-0">
                                                Saved Licence Copy:&nbsp;
                                                <a
                                                    onClick={() => openDocument(existingLicenseCopy.file, existingLicenseCopyName)}
                                                    className="font-semibold break-all cursor-pointer"
                                                >
                                                    {existingLicenseCopyName}
                                                </a>
                                            </span>
                                            <button
                                                type="button"
                                                className="flex items-center gap-1.5 rounded border border-primary/30 bg-primary/5 px-2.5 py-1.5 text-xs font-medium text-primary cursor-pointer hover:bg-primary/10 ml-auto"
                                                onClick={handleReparseExistingCopy}
                                                disabled={licenseParsing}
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
                                <div className="mt-3 rounded-lg border bg-muted/40 px-4 py-3 text-[0.8125rem]">
                                    <div className="text-foreground">
                                        <strong>{licenseParseSummary.license_number}</strong>
                                        <span className="text-muted-foreground/70"> · </span>{licenseParseSummary.license_date} → {licenseParseSummary.license_expiry_date}
                                        <span className="text-muted-foreground/70"> · </span>port <code>{licenseParseSummary.port_code}</code>
                                        <span className="text-muted-foreground/70"> · </span>notification {licenseParseSummary.notification_number}
                                        <span className="text-muted-foreground/70"> · </span>file <code>{licenseParseSummary.file_number}</code>
                                    </div>
                                    {licenseParseSummary.source_kind === 'dgft_qr' && (
                                        <div className="mt-1 text-emerald-700">
                                            <QrCode className="size-4" aria-hidden="true" />
                                            Fetched fresh digital copy from DGFT via QR code on uploaded scan.
                                        </div>
                                    )}
                                    {licenseParseSummary.source_kind === 'ocr' && (
                                        <div className="mt-1 text-amber-700">
                                            <TriangleAlert className="size-4" aria-hidden="true" />
                                            Scanned PDF — header fields recovered via OCR. Items table is unreliable; please review/add manually.
                                        </div>
                                    )}
                                    {licenseParseSummary.company_created && (
                                        <div className="mt-1 text-emerald-700">
                                            <CheckCircle2 className="size-4" aria-hidden="true" />
                                            New company created ({licenseParseSummary.company_name}).
                                        </div>
                                    )}
                                    {!licenseParseSummary.company_created && licenseParseSummary.matched_company_id && (
                                        <div className="mt-1 text-muted-foreground">
                                            <Check className="size-4" aria-hidden="true" />
                                            Matched existing company ({licenseParseSummary.company_name}).
                                        </div>
                                    )}
                                    {!licenseParseSummary.matched_port_id && licenseParseSummary.port_code && (
                                        <div className="mt-1 text-amber-700">
                                            <TriangleAlert className="size-4" aria-hidden="true" />
                                            Port code <code>{licenseParseSummary.port_code}</code> not found in master — please add and re-select.
                                        </div>
                                    )}
                                    {licenseParseSummary.items?.length > 0 && (
                                        <details className="mt-2">
                                            <summary className="cursor-pointer text-muted-foreground">
                                                {licenseParseSummary.items.length} import item(s) — {licenseParseSummary.unmatchedHsn} HSN(s) not in master
                                            </summary>
                                            <ul className="mb-0 mt-2 pl-[1.1rem] text-muted-foreground">
                                                {licenseParseSummary.items.map((it, i) => (
                                                    <li key={i} style={{ padding: '2px 0' }}>
                                                        sl#{it.serial_number} · HSN <code>{it.hsn}</code> · qty {it.quantity} {it.uom} · CIF ₹{it.cif_inr} / ${it.cif_fc}
                                                        {it.matched_hs_code_id
                                                            ? <span className="text-emerald-700 ml-1.5">✓ HSN matched</span>
                                                            : <span className="text-amber-700 ml-1.5">⚠ HSN not in master</span>}
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
