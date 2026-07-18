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
                                        Import from BOE PDF
                                    </div>
                                    <div className="mt-1 text-[0.8125rem] text-muted-foreground">
                                        Upload an ICEGATE BOE, then click <strong>Fetch</strong> to prefill the form and item rows.
                                    </div>
                                    <div className="flex items-center mt-3 gap-2.5 flex-wrap">
                                        <input
                                            type="file"
                                            accept=".pdf,application/pdf"
                                            id="boe-pdf-input"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring max-w-[340px]"
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
                                <div className="mt-3 rounded-lg border bg-muted/40 px-4 py-3 text-[0.8125rem]">
                                    <div className="text-foreground">
                                        <strong>BE {boeParseSummary.be_number}</strong>
                                        <span className="text-muted-foreground/70"> · </span>{boeParseSummary.be_date}
                                        <span className="text-muted-foreground/70"> · </span>port <code>{boeParseSummary.port_code}</code>
                                        <span className="text-muted-foreground/70"> · </span>1 {boeParseSummary.currency || 'USD'} = ₹{boeParseSummary.exchange_rate}
                                    </div>
                                    {boeParseSummary.company_created && (
                                        <div className="mt-1 text-emerald-700">
                                            <CheckCircle2 className="size-4" aria-hidden="true" />
                                            New company created from buyer details ({boeParseSummary.buyer_name}).
                                        </div>
                                    )}
                                    {!boeParseSummary.company_created && boeParseSummary.matched_company_id && (
                                        <div className="mt-1 text-muted-foreground">
                                            <Check className="size-4" aria-hidden="true" />
                                            Matched existing company ({boeParseSummary.buyer_name}).
                                        </div>
                                    )}
                                    {boeParseSummary.matched_allotment_id && (
                                        <div className="mt-1 text-primary">
                                            <Info className="size-4" aria-hidden="true" />
                                            Matched existing allotment <strong>#{boeParseSummary.matched_allotment_id}</strong> by invoice number.
                                        </div>
                                    )}
                                    {boeParseSummary.licences?.length > 0 && (
                                        <details className="mt-2">
                                            <summary className="cursor-pointer text-muted-foreground">
                                                {boeParseSummary.licences.length} licence row(s) — {boeParseSummary.unmatched} unmatched
                                            </summary>
                                            <ul className="mb-0 mt-2 pl-[1.1rem] text-muted-foreground">
                                                {boeParseSummary.licences.map((l, i) => {
                                                    const badge = l.match_status === 'matched'
                                                        ? <span className="text-emerald-700 ml-1.5">✓ prefill item</span>
                                                        : l.match_status === 'license_only'
                                                            ? <span className="text-amber-700 ml-1.5">⚠ license found, sl#{l.licence_slno} missing</span>
                                                            : l.match_status === 'license_missing'
                                                                ? <span className="text-red-700 ml-1.5">✗ license not in DB</span>
                                                                : <span className="text-muted-foreground/70 ml-1.5">— no data</span>;
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
