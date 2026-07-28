import { useContext, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, Loader2, MoreVertical } from "lucide-react";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { licenseBalanceKeys } from "./useLicenseBalanceLedger";
import { extractApiError, fmtDateTime } from "./licenseBalanceHelpers";
import type { LicenseBalanceWarning } from "./types";

interface WarningsPanelProps {
    licenseId: string | number;
    warnings: LicenseBalanceWarning[];
}

type WarningTab = "active" | "ignored" | "all";

/** Mirrors `LicenseBalanceLedgerPermission.write_action_roles['ignore_warning'
 * / 'restore_warning']` exactly — any one of these roles can ignore/restore. */
const MANAGER_ROLES = ["LICENSE_MANAGER", "BOE_MANAGER", "TRADE_MANAGER", "ALLOTMENT_MANAGER"];

function warningKey(w: LicenseBalanceWarning): string {
    return `${w.warning_type}:${w.entity_type}:${w.entity_id}`;
}

/**
 * Warning Management panel — full rebuild of the old dismiss-only warning
 * banner. Tabs partition the SAME `data.warnings` array client-side by
 * `.ignored` (no extra fetch — the array already carries everything);
 * ignore/restore round-trip through `ignore-warning`/`restore-warning` and
 * simply invalidate the ledger query so the tabs refresh from the fresh
 * `ignored`/`ignored_by`/`ignored_at` fields the backend returns.
 */
export default function WarningsPanel({ licenseId, warnings }: WarningsPanelProps) {
    const { hasAnyRole } = useContext(AuthContext);
    const queryClient = useQueryClient();
    const canManage = hasAnyRole(MANAGER_ROLES);

    const [tab, setTab] = useState<WarningTab>("active");
    const [expandedDetails, setExpandedDetails] = useState<Set<string>>(new Set());
    const [ignoreTarget, setIgnoreTarget] = useState<LicenseBalanceWarning | null>(null);
    const [ignoreReason, setIgnoreReason] = useState("");
    const [ignoreSubmitting, setIgnoreSubmitting] = useState(false);
    const [restoringKey, setRestoringKey] = useState<string | null>(null);

    const activeWarnings = useMemo(() => warnings.filter((w) => !w.ignored), [warnings]);
    const ignoredWarnings = useMemo(() => warnings.filter((w) => w.ignored), [warnings]);
    const listForTab = tab === "active" ? activeWarnings : tab === "ignored" ? ignoredWarnings : warnings;

    const invalidate = () => queryClient.invalidateQueries({ queryKey: licenseBalanceKeys.ledger(licenseId) });

    const toggleDetails = (key: string) => {
        setExpandedDetails((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    };

    const handleCopyReference = async (w: LicenseBalanceWarning) => {
        try {
            await navigator.clipboard.writeText(warningKey(w));
            toast.success("Reference copied to clipboard.");
        } catch {
            toast.error("Failed to copy reference.");
        }
    };

    const openIgnoreDialog = (w: LicenseBalanceWarning) => {
        setIgnoreReason("");
        setIgnoreTarget(w);
    };

    const handleIgnoreConfirm = async () => {
        if (!ignoreTarget) return;
        setIgnoreSubmitting(true);
        try {
            await api.post(`licenses/${licenseId}/ignore-warning/`, {
                warning_type: ignoreTarget.warning_type,
                entity_type: ignoreTarget.entity_type,
                entity_id: ignoreTarget.entity_id,
                reason: ignoreReason.trim(),
            });
            toast.success("Warning ignored.");
            invalidate();
            setIgnoreTarget(null);
        } catch (err) {
            toast.error(extractApiError(err, "Failed to ignore warning."));
        } finally {
            setIgnoreSubmitting(false);
        }
    };

    const handleRestore = async (w: LicenseBalanceWarning) => {
        const key = warningKey(w);
        setRestoringKey(key);
        try {
            await api.post(`licenses/${licenseId}/restore-warning/`, {
                warning_type: w.warning_type,
                entity_type: w.entity_type,
                entity_id: w.entity_id,
            });
            toast.success("Warning restored to Active.");
            invalidate();
        } catch (err) {
            toast.error(extractApiError(err, "Failed to restore warning."));
        } finally {
            setRestoringKey(null);
        }
    };

    const renderWarningRow = (w: LicenseBalanceWarning) => {
        const key = warningKey(w);
        const detailsOpen = expandedDetails.has(key);
        return (
            <div key={key} className="rounded-lg border border-border/70 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 flex-1 items-start gap-2.5">
                        <AlertTriangle
                            className={cn("mt-0.5 size-4 shrink-0", w.ignored ? "text-muted-foreground" : "text-destructive")}
                        />
                        <div className="min-w-0">
                            <p className={cn("text-sm", w.ignored ? "text-muted-foreground" : "text-foreground")}>
                                {w.message}
                            </p>
                            {w.ignored && (
                                <p className="mt-0.5 text-xs text-muted-foreground">
                                    Ignored{w.ignored_by ? ` by ${w.ignored_by}` : ""}
                                    {w.ignored_at ? ` on ${fmtDateTime(w.ignored_at)}` : ""}
                                    {w.reason ? ` — "${w.reason}"` : ""}
                                </p>
                            )}
                        </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                        <Badge variant={w.ignored ? "secondary" : "destructive"}>{w.ignored ? "Ignored" : "Active"}</Badge>
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button size="icon" variant="ghost" className="size-8" aria-label="More actions">
                                    <MoreVertical className="size-4" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                {!w.ignored && canManage && (
                                    <DropdownMenuItem onSelect={() => openIgnoreDialog(w)}>Ignore Warning</DropdownMenuItem>
                                )}
                                {w.ignored && canManage && (
                                    <DropdownMenuItem onSelect={() => handleRestore(w)} disabled={restoringKey === key}>
                                        {restoringKey === key ? "Restoring…" : "Restore"}
                                    </DropdownMenuItem>
                                )}
                                <DropdownMenuItem onSelect={() => toggleDetails(key)}>
                                    {detailsOpen ? "Hide Details" : "View Details"}
                                </DropdownMenuItem>
                                <DropdownMenuItem onSelect={() => handleCopyReference(w)}>Copy Reference</DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </div>
                {detailsOpen && (
                    <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 rounded-md bg-muted/40 p-2.5 text-xs sm:grid-cols-3">
                        <div>
                            <dt className="text-muted-foreground">Warning Type</dt>
                            <dd className="font-medium text-foreground">{w.warning_type}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Entity Type</dt>
                            <dd className="font-medium text-foreground">{w.entity_type}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Entity ID</dt>
                            <dd className="font-medium text-foreground">{w.entity_id}</dd>
                        </div>
                    </dl>
                )}
            </div>
        );
    };

    return (
        <div>
            <Tabs value={tab} onValueChange={(v) => setTab(v as WarningTab)}>
                <TabsList>
                    <TabsTrigger value="active">Active Warnings ({activeWarnings.length})</TabsTrigger>
                    <TabsTrigger value="ignored">Ignored Warnings ({ignoredWarnings.length})</TabsTrigger>
                    <TabsTrigger value="all">All Warnings ({warnings.length})</TabsTrigger>
                </TabsList>
                <TabsContent value={tab} className="mt-3 space-y-2">
                    {listForTab.length === 0 ? (
                        <div className="flex items-center gap-2 rounded-lg border border-border/70 px-4 py-6 text-sm text-muted-foreground">
                            <CheckCircle2 className="size-4 text-success" />
                            {tab === "active" ? "No active warnings — this licence looks clean." : "No warnings here."}
                        </div>
                    ) : (
                        listForTab.map(renderWarningRow)
                    )}
                </TabsContent>
            </Tabs>

            <Dialog open={ignoreTarget !== null} onOpenChange={(open) => !ignoreSubmitting && !open && setIgnoreTarget(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Ignore Warning?</DialogTitle>
                        <DialogDescription>
                            You are about to ignore this warning. Ignored warnings will not appear in Active Warnings
                            until restored. Ignoring does NOT resolve the issue. No financial data will be modified.
                        </DialogDescription>
                    </DialogHeader>
                    <div>
                        <label className="mb-1 block text-xs font-medium text-muted-foreground">Reason (optional)</label>
                        <Textarea
                            value={ignoreReason}
                            onChange={(e) => setIgnoreReason(e.target.value)}
                            placeholder="Why is this warning being ignored?"
                            rows={3}
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIgnoreTarget(null)} disabled={ignoreSubmitting}>
                            Cancel
                        </Button>
                        <Button variant="destructive" onClick={handleIgnoreConfirm} disabled={ignoreSubmitting}>
                            {ignoreSubmitting && <Loader2 className="size-4 animate-spin" />}
                            Ignore Warning
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
