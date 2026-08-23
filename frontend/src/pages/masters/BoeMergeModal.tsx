import { Layers, MapPin, X } from "lucide-react";
import { formatTruthyInr } from "./masterDisplayFormatters";
import { cn } from "@/lib/utils";

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
                <div className="fixed inset-0 z-[1060] flex items-center justify-center bg-black/45 p-3" onClick={closeMergeModal}>
                    <div role="dialog" aria-modal="true" aria-labelledby="merge-boe-title" className="max-h-[calc(100dvh-1.5rem)] w-[560px] max-w-[95vw] overflow-y-auto rounded-lg border border-border bg-card p-4 shadow-[0_8px_32px_rgba(0,0,0,0.18)]" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between mb-4">
                            <h2 id="merge-boe-title" className="m-0 flex items-center gap-1.5 text-sm font-bold text-foreground">
                                <Layers className="size-4" aria-hidden="true" />
                                Merge BOE: <span className="text-violet-600">{mergeBoeTarget.bill_of_entry_number}</span>
                            </h2>
                            <button type="button" onClick={closeMergeModal} aria-label="Close merge BOE dialog" className="flex size-8 items-center justify-center rounded bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                                <X className="size-4" aria-hidden="true" />
                            </button>
                        </div>

                        {/* Target BOE info */}
                        <div className="rounded-xl border border-[#86efac] bg-emerald-50 px-3.5 py-2.5 mb-4 text-[13.5px]">
                            <div className="font-semibold text-emerald-700 mb-1">Target BOE (will be kept &amp; updated)</div>
                            <div className="flex items-center gap-1"><MapPin className="size-4" aria-hidden="true" />{mergeBoeTarget.port_name}</div>
                            <div className="text-muted-foreground text-xs">
                                {mergeBoeTarget.item_details?.length || 0} item(s) · {mergeBoeTarget.licenses || 'No licenses'}
                            </div>
                        </div>

                        <div className="font-semibold text-xs text-muted-foreground uppercase tracking-[0.5px] mb-2">
                            Select source BOE to merge from (port replaces target, items moved, source deleted):
                        </div>

                        {mergeCandidatesLoading && (
                            <div className="text-center py-5 text-muted-foreground/70">
                                <span className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" aria-hidden="true" />Loading candidates...
                            </div>
                        )}

                        {!mergeCandidatesLoading && mergeCandidates.length === 0 && (
                            <div className="text-center py-5 text-muted-foreground/70 text-sm">
                                No other BOEs found with number {mergeBoeTarget.bill_of_entry_number}
                            </div>
                        )}

                        {mergeCandidates.map(candidate => {
                            const isSelected = mergeBoeSource?.id === candidate.id;
                            return (
                                <button
                                    type="button"
                                    key={candidate.id}
                                    onClick={() => setMergeBoeSource((prev: any) => prev?.id === candidate.id ? null : candidate)}
                                    aria-pressed={isSelected}
                                    className={cn(
                                        "mb-2 flex w-full items-center justify-between rounded-lg border-2 px-3 py-2 text-left transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                        isSelected
                                            ? "border-violet-500 bg-muted/60"
                                            : "border-border bg-card"
                                    )}
                                >
                                    <div>
                                        <div className="font-semibold text-sm text-foreground flex items-center gap-1">
                                            <MapPin className="size-4" aria-hidden="true" />{candidate.port_name}
                                        </div>
                                        <div className="text-xs text-muted-foreground">
                                            {candidate.item_details?.length || 0} item(s) · {candidate.licenses || 'No licenses'}
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        {candidate.total_inr && (
                                            <div className="font-bold text-sm text-foreground">
                                                {formatTruthyInr(candidate.total_inr)}
                                            </div>
                                        )}
                                        {isSelected && (
                                            <span className="text-[11px] text-violet-600 font-bold">✓ Selected</span>
                                        )}
                                    </div>
                                </button>
                            );
                        })}

                        {mergeBoeSource && (
                            <div className="rounded-xl border border-violet-300 bg-muted/60 px-3.5 py-2.5 my-3 text-[0.82rem] text-violet-600">
                                <strong>What will happen:</strong>
                                <ul className="mt-1.5 mb-0 pl-5">
                                    <li>Target port will change to <strong>{mergeBoeSource.port_name}</strong></li>
                                    <li>Items from source will be moved to target (duplicates skipped)</li>
                                    <li>Source BOE ({mergeBoeSource.port_name}) will be permanently deleted</li>
                                </ul>
                            </div>
                        )}

                        <div className="flex justify-end gap-2 mt-4">
                            <button
                                onClick={closeMergeModal}
                                className="px-4 py-1.5 rounded-md border border-border bg-muted/60 cursor-pointer text-sm hover:bg-muted"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={doMerge}
                                disabled={!mergeBoeSource || mergeBoeLoading}
                                className={cn(
                                    "flex items-center gap-1.5 px-4 py-1.5 rounded-md border-none text-white text-sm font-semibold",
                                    mergeBoeSource && !mergeBoeLoading
                                        ? "bg-violet-600 cursor-pointer hover:bg-violet-700"
                                        : "bg-violet-300 cursor-not-allowed"
                                )}
                            >
                                {mergeBoeLoading
                                    ? <><span className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true"></span>Merging...</>
                                    : <><Layers className="size-4" aria-hidden="true" />Confirm Merge</>
                                }
                            </button>
                        </div>
                    </div>
                </div>
    );
}
