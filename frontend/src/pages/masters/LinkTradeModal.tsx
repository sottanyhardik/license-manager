import { Link as LinkIcon, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
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
        <div className="fixed inset-0 z-[1060] flex items-center justify-center bg-black/45" onClick={closeLinkModal}>
            <div
                className="w-[480px] max-w-[95vw] rounded-xl bg-card p-6 shadow-[0_8px_32px_rgba(0,0,0,0.18)]"
                onClick={e => e.stopPropagation()}
            >
                <div className="mb-4 flex items-center justify-between">
                    <h6 className="m-0 flex items-center gap-1.5 font-bold text-primary">
                        <LinkIcon className="size-4" aria-hidden="true" />
                        Link Trade: <span className="text-primary">{linkModalTrade.invoice_number || 'No Invoice'}</span>
                    </h6>
                    <button
                        type="button"
                        onClick={closeLinkModal}
                        className="inline-flex size-7 cursor-pointer items-center justify-center rounded border-0 bg-transparent text-muted-foreground/70 hover:text-foreground"
                        aria-label="Close"
                    >
                        <X className="size-4" aria-hidden="true" />
                    </button>
                </div>

                <input
                    autoFocus
                    type="text"
                    className="mb-3 flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                    placeholder="Search by invoice number..."
                    value={linkSearch}
                    onChange={e => setLinkSearch(e.target.value)}
                />

                {linkSearching && (
                    <div className="flex items-center justify-center gap-2 py-3 text-sm text-muted-foreground/70">
                        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                        Searching...
                    </div>
                )}

                {!linkSearching && linkSearch && linkResults.length === 0 && (
                    <div className="py-3 text-center text-sm text-muted-foreground/70">
                        No unlinked trades found for &ldquo;{linkSearch}&rdquo;
                    </div>
                )}

                {linkResults.map(t => (
                    <div
                        key={t.id}
                        {...clickable(() => confirmLink(t))}
                        className="mb-2 flex cursor-pointer items-center justify-between rounded-xl border border-border px-3 py-2.5 transition-colors hover:bg-muted/40"
                    >
                        <div>
                            <div className="text-[14.5px] font-semibold text-foreground">{t.invoice_number || 'No Invoice'}</div>
                            <div className="text-xs text-muted-foreground">{t.from_company_label} → {t.to_company_label}</div>
                        </div>
                        <div className="text-right">
                            <span className={cn(
                                "rounded-md px-2 py-0.5 text-xs font-bold",
                                t.direction.includes('SALE') ? "bg-emerald-50 text-emerald-700" : "bg-primary/5 text-primary"
                            )}>
                                {t.direction_label || t.direction}
                            </span>
                            <div className="mt-1 text-xs text-muted-foreground">
                                {formatTruthyInr(t.total_amount, "-")}
                            </div>
                        </div>
                    </div>
                ))}

                {!linkSearch && (
                    <div className="py-2 text-center text-sm text-muted-foreground/70">
                        Type an invoice number to search
                    </div>
                )}
            </div>
        </div>
    );
}
