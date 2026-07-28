import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { TimelineEvent, TimelineEventChild } from "./types";
import { fmtDateTime, fmtNum, timelineColorBadgeVariant, timelineColorDotClass } from "./licenseBalanceHelpers";

interface BalanceTimelineProps {
    events: TimelineEvent[];
}

/** Qty/CIF/Doc/Company/User detail line shared by a top-level event and its children. */
function EventDetails({ event }: { event: TimelineEventChild }) {
    const parts: { label: string; value: string }[] = [];
    if (event.document_number) parts.push({ label: "Doc", value: event.document_number });
    if (event.company) parts.push({ label: "Company", value: event.company });
    if (event.quantity !== null && event.quantity !== undefined) parts.push({ label: "Qty", value: fmtNum(event.quantity) });
    if (event.cif !== null && event.cif !== undefined) parts.push({ label: "CIF", value: fmtNum(event.cif) });
    if (event.user) parts.push({ label: "By", value: event.user });

    if (parts.length === 0) return null;
    return (
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
            {parts.map((p) => (
                <span key={p.label}>
                    {p.label}: <span className="font-medium text-foreground">{p.value}</span>
                </span>
            ))}
        </div>
    );
}

/**
 * Section 4 — Timeline. Consumes the real, backend-built `data.timeline`
 * (`LicenseBalanceLedgerBuilder.build_timeline`) — a flat, chronologically
 * sorted list of REAL business-lifecycle events, never fabricated (no
 * "Purchase Order" step exists in this system, so none is synthesized here
 * either). Hierarchical events (e.g. "Invoice ↔ BOE Reconciled") expand
 * inline to show their per-BOE/per-allotment children, mirroring the PDF's
 * `_build_timeline_elements` "always expanded" layout, with an interactive
 * collapse toggle since this view IS interactive.
 */
export default function BalanceTimeline({ events }: BalanceTimelineProps) {
    const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

    const toggle = (sr: number) => {
        setCollapsed((prev) => {
            const next = new Set(prev);
            if (next.has(sr)) next.delete(sr);
            else next.add(sr);
            return next;
        });
    };

    if (events.length === 0) {
        return (
            <p className="py-6 text-center text-sm text-muted-foreground">
                No timeline events recorded for this licence yet.
            </p>
        );
    }

    return (
        <ol className="relative space-y-5 border-l border-border pl-5">
            {events.map((event) => {
                const hasChildren = event.expandable && event.children.length > 0;
                const isOpen = !collapsed.has(event.sr);
                return (
                    <li key={event.sr} className="relative">
                        <span
                            aria-hidden="true"
                            className={cn(
                                "absolute -left-[1.4rem] top-1 size-2.5 rounded-full ring-4 ring-background",
                                timelineColorDotClass(event.color)
                            )}
                        />
                        <div className="flex flex-wrap items-center gap-2">
                            {hasChildren ? (
                                <button
                                    type="button"
                                    onClick={() => toggle(event.sr)}
                                    className="inline-flex cursor-pointer items-center gap-1 text-sm font-medium text-foreground hover:underline"
                                    aria-label={isOpen ? "Collapse detail" : "Expand detail"}
                                >
                                    {isOpen ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                                    {event.label}
                                </button>
                            ) : (
                                <span className="text-sm font-medium text-foreground">{event.label}</span>
                            )}
                            <Badge variant={timelineColorBadgeVariant(event.color)}>
                                {event.status || event.event_type.replace(/_/g, " ")}
                            </Badge>
                            <span className="text-xs text-muted-foreground">{fmtDateTime(event.date)}</span>
                        </div>
                        <EventDetails event={event} />
                        {event.remarks && <p className="mt-0.5 text-xs text-muted-foreground/80">{event.remarks}</p>}

                        {hasChildren && isOpen && (
                            <ol className="mt-2 space-y-3 border-l border-border/60 pl-4">
                                {event.children.map((child, idx) => (
                                    <li key={`${event.sr}-${idx}`} className="relative">
                                        <span
                                            aria-hidden="true"
                                            className={cn(
                                                "absolute -left-[1.15rem] top-1 size-2 rounded-full ring-2 ring-background",
                                                timelineColorDotClass(child.color)
                                            )}
                                        />
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="text-xs font-medium text-foreground">↳ {child.label}</span>
                                            <span className="text-[11px] text-muted-foreground">{fmtDateTime(child.date)}</span>
                                        </div>
                                        <EventDetails event={child} />
                                        {child.remarks && (
                                            <p className="mt-0.5 text-[11px] text-muted-foreground/80">{child.remarks}</p>
                                        )}
                                    </li>
                                ))}
                            </ol>
                        )}
                    </li>
                );
            })}
        </ol>
    );
}
