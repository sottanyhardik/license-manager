import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2, RotateCw } from "lucide-react";

import api from "@/api/axios";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

type ReplanStatusResponse = {
    planning_state: "CURRENT" | "REPLAN_PENDING" | "REPLAN_RUNNING" | "REPLAN_FAILED";
    source_revision: number;
    planned_revision: number;
    replan_request: null | {
        id: number;
        status: string;
        last_error_code?: string | null;
        last_error_message?: string | null;
    };
};

/** Lightweight, read-only polling surface for background planning work. */
export default function ReplanStatus({ licenseId }: { licenseId: string | number }) {
    const queryClient = useQueryClient();
    const queryKey = ["license-replan-status", String(licenseId)];
    const status = useQuery<ReplanStatusResponse>({
        queryKey,
        queryFn: async () => (await api.get(`licenses/${licenseId}/replan-status/`)).data,
        refetchInterval: (query) => {
            const state = query.state.data?.planning_state;
            return state === "REPLAN_PENDING" || state === "REPLAN_RUNNING" ? 2000 : false;
        },
    });
    const retry = useMutation({
        mutationFn: async () => (await api.post(`licenses/${licenseId}/replan-status/`)).data,
        onSuccess: () => void queryClient.invalidateQueries({ queryKey }),
    });

    if (!status.data || status.data.planning_state === "CURRENT") return null;
    const state = status.data.planning_state;
    const failed = state === "REPLAN_FAILED";
    const running = state === "REPLAN_RUNNING";
    const detail = status.data.replan_request?.last_error_message || status.data.replan_request?.last_error_code;
    return <div role={failed ? "alert" : "status"} className={`mb-4 flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm ${failed ? "border-destructive/50 bg-destructive/5" : "border-amber-400/50 bg-amber-50"}`}>
        {failed ? <AlertTriangle className="size-4 text-destructive" /> : running ? <Loader2 className="size-4 animate-spin" /> : <CheckCircle2 className="size-4 text-amber-700" />}
        <Badge variant={failed ? "destructive" : "secondary"}>{failed ? "Replan failed" : running ? "Replan running" : "Replan pending"}</Badge>
        <span>{failed ? detail || "The planning worker reported a failure." : "Your update was saved; planning continues in the background."}</span>
        {failed && <Button type="button" size="sm" variant="outline" className="ml-auto" disabled={retry.isPending} onClick={() => retry.mutate()}><RotateCw className="size-3.5" />Retry replan</Button>}
    </div>;
}
