import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
    AlertTriangle, CheckCircle2, Copy, FileText, FileX, IndianRupee, Loader2, ReceiptText, RefreshCw,
} from "lucide-react";

import api from "@/api/axios";
import PageHeader from "@/components/PageHeader";
import StatCard from "@/components/StatCard";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { useConfirmDialog } from "@/hooks/useConfirmDialog";
import { getErrorMessage } from "@/utils/errorUtils";

import MissingBoeTab from "./reconciliation/MissingBoeTab";
import MissingInvoiceTab from "./reconciliation/MissingInvoiceTab";
import DuplicateDebitsTab from "./reconciliation/DuplicateDebitsTab";
import DuplicateBoesTab from "./reconciliation/DuplicateBoesTab";
import ComparisonTab from "./reconciliation/ComparisonTab";
import MultiLinkTab from "./reconciliation/MultiLinkTab";
import ReconciliationAuditLog from "./reconciliation/ReconciliationAuditLog";
import { pick, reconKeys } from "./reconciliation/reconciliationHelpers";

type TabValue =
    | "missing-boe" | "missing-invoice" | "duplicate-debits" | "duplicate-boes"
    | "cif-comparison" | "qty-comparison" | "multi-boe" | "multi-invoice";

// Recalculation polling: mirrors the existing pattern in
// reports/ItemPivotReport.tsx (`handleUpdateBalance` / `pollUpdateStatus`) —
// fire-and-poll a Celery task_id every ~2.5s via a recursive setTimeout,
// capped so a stuck task doesn't poll forever. `recalculate` reuses the
// EXISTING task-status endpoint verbatim (no new one was added):
// GET /api/item-pivot/task-status/<task_id>/ — confirmed against
// `backend/apps/license/views/item_pivot_report.py:1752` and its router
// registration (`item-pivot`) in `backend/apps/license/urls.py`.
const POLL_INTERVAL_MS = 2500;
const MAX_POLL_ATTEMPTS = 80; // ~3.3 minutes

export default function ReconciliationPanel() {
    const queryClient = useQueryClient();
    const { confirmDangerousAction, confirmDialog } = useConfirmDialog();
    const [activeTab, setActiveTab] = useState<TabValue>("missing-boe");
    const [recalculating, setRecalculating] = useState(false);
    const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const pollAttemptsRef = useRef(0);

    useEffect(() => () => {
        if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    }, []);

    const { data: summary, isLoading: summaryLoading } = useQuery({
        queryKey: reconKeys.summary,
        queryFn: async () => {
            const { data } = await api.get("reconciliation/summary/");
            return data ?? {};
        },
    });

    const invalidateAll = useCallback(() => {
        queryClient.invalidateQueries({ queryKey: ["reconciliation"] });
    }, [queryClient]);

    const pollRecalcStatus = useCallback((taskId: string | number) => {
        pollTimeoutRef.current = setTimeout(async () => {
            try {
                const { data } = await api.get(`item-pivot/task-status/${taskId}/`);
                const state = data?.state;
                if (state === "SUCCESS") {
                    toast.success("Licence balances recalculated successfully.");
                    setRecalculating(false);
                    invalidateAll();
                    return;
                }
                if (state === "FAILURE") {
                    toast.error("Balance recalculation failed. Please try again.");
                    setRecalculating(false);
                    return;
                }
                if (pollAttemptsRef.current >= MAX_POLL_ATTEMPTS) {
                    toast.warning("Recalculation is taking longer than expected — check back later.");
                    setRecalculating(false);
                    return;
                }
                pollAttemptsRef.current += 1;
                pollRecalcStatus(taskId);
            } catch {
                if (pollAttemptsRef.current >= MAX_POLL_ATTEMPTS) {
                    setRecalculating(false);
                    return;
                }
                pollAttemptsRef.current += 1;
                pollRecalcStatus(taskId);
            }
        }, POLL_INTERVAL_MS);
    }, [invalidateAll]);

    const handleRecalculate = async () => {
        const confirmed = await confirmDangerousAction(
            "Recalculate Licence Balances",
            "This triggers a full balance recalculation across licences and may take a while to complete. Continue?",
        );
        if (!confirmed) return;

        setRecalculating(true);
        try {
            const { data } = await api.post("reconciliation/recalculate/", {});
            const taskId = data?.task_id;
            if (!taskId) {
                toast.error("Recalculation did not return a task id.");
                setRecalculating(false);
                return;
            }
            toast.info("Balance recalculation started. You'll be notified when it completes.");
            pollAttemptsRef.current = 0;
            pollRecalcStatus(taskId);
        } catch (err) {
            toast.error(getErrorMessage(err));
            setRecalculating(false);
        }
    };

    const val = (key: string) => (summary ? pick(summary as Record<string, unknown>, key) : null);

    return (
        <div className="reconciliation-page space-y-3">
            <PageHeader
                pretitle="Operations"
                title="BOE / Invoice Reconciliation"
                description="Find and manually fix mismatches between Bills of Entry and trade invoices."
                actions={
                    <Button onClick={handleRecalculate} disabled={recalculating}>
                        {recalculating
                            ? <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                            : <RefreshCw className="size-4" aria-hidden="true" />}
                        {recalculating ? "Recalculating…" : "Recalculate Licence Balance"}
                    </Button>
                }
            />

            <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-5">
                <StatCard label="Total BOE" value={val("total_boe") as ReactNode} icon={ReceiptText} tone="primary" loading={summaryLoading} />
                <StatCard label="Total Import Invoices" value={val("total_import_invoices") as ReactNode} icon={FileText} tone="info" loading={summaryLoading} />
                <StatCard label="Matched" value={val("matched") as ReactNode} icon={CheckCircle2} tone="success" loading={summaryLoading} />
                <StatCard label="Unmatched BOE" value={val("unmatched_boe") as ReactNode} icon={AlertTriangle} tone="warning" loading={summaryLoading} onClick={() => setActiveTab("missing-boe")} />
                <StatCard label="Unmatched Invoice" value={val("unmatched_invoice") as ReactNode} icon={FileX} tone="warning" loading={summaryLoading} onClick={() => setActiveTab("missing-invoice")} />
                <StatCard label="Duplicate Debits" value={val("duplicate_debits") as ReactNode} icon={Copy} tone="danger" loading={summaryLoading} onClick={() => setActiveTab("duplicate-debits")} />
                <StatCard label="CIF Difference" value={val("cif_difference") as ReactNode} icon={IndianRupee} tone="danger" loading={summaryLoading} onClick={() => setActiveTab("cif-comparison")} />
            </div>

            <Card className="overflow-hidden border-border/80 shadow-sm shadow-primary/5">
                <CardContent className="p-2 sm:p-3">
                    <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabValue)}>
                        <div className="overflow-x-auto pb-1">
                        <TabsList className="flex h-9 min-w-max justify-start gap-1" aria-label="Reconciliation work queues">
                            <TabsTrigger value="missing-boe">Missing BOE</TabsTrigger>
                            <TabsTrigger value="missing-invoice">Missing Invoice</TabsTrigger>
                            <TabsTrigger value="duplicate-debits">Duplicate Debits</TabsTrigger>
                            <TabsTrigger value="duplicate-boes">Duplicate BOEs (Merge)</TabsTrigger>
                            <TabsTrigger value="cif-comparison">CIF Comparison</TabsTrigger>
                            <TabsTrigger value="qty-comparison">Quantity Comparison</TabsTrigger>
                            <TabsTrigger value="multi-boe">Multiple BOEs</TabsTrigger>
                            <TabsTrigger value="multi-invoice">Multiple Invoices</TabsTrigger>
                        </TabsList>
                        </div>

                        <TabsContent value="missing-boe" className="mt-2">
                            <MissingBoeTab />
                        </TabsContent>
                        <TabsContent value="missing-invoice" className="mt-2">
                            <MissingInvoiceTab />
                        </TabsContent>
                        <TabsContent value="duplicate-debits" className="mt-2">
                            <DuplicateDebitsTab />
                        </TabsContent>
                        <TabsContent value="duplicate-boes" className="mt-2">
                            <DuplicateBoesTab confirmDangerousAction={confirmDangerousAction} />
                        </TabsContent>
                        <TabsContent value="cif-comparison" className="mt-2">
                            <ComparisonTab kind="cif" />
                        </TabsContent>
                        <TabsContent value="qty-comparison" className="mt-2">
                            <ComparisonTab kind="qty" />
                        </TabsContent>
                        <TabsContent value="multi-boe" className="mt-2">
                            <MultiLinkTab kind="boe" />
                        </TabsContent>
                        <TabsContent value="multi-invoice" className="mt-2">
                            <MultiLinkTab kind="invoice" />
                        </TabsContent>
                    </Tabs>
                </CardContent>
            </Card>

            <ReconciliationAuditLog />

            {confirmDialog}
        </div>
    );
}
