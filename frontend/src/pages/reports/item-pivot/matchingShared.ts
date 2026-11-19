/** Product-matching types, band labels and the shared query (Item Pivot). */
import api from "@/api/axios";
import type { Tone } from "@/components/shared";

export type Band = "CLASSIFIED" | "APPROVED" | "HIGH" | "STRONG" | "REVIEW" | "UNCLASSIFIED" | "CONFLICT" | "UNMATCHED";
export type Candidate = { item_id: number; name: string; score?: number; similarity?: number };
export type MatchCheck = { ok: boolean; detail: string };
export type MatchSuggestion = {
    source_key: string; product_key?: string; product_keys?: string[]; kind: string; description: string; aliases: string[]; hsn_code: string; hsn_codes: string[]; sion: string | null;
    import_item_ids: number[]; license_numbers: string[]; band: Band; action: string; confidence: number; matcher?: string;
    suggestion: { item_id: number; name: string } | null; explanation: string; conflicts: string[];
    checks: Partial<Record<"sion" | "hsn" | "entitlement" | "planning_rule", MatchCheck>>; candidates: Candidate[]; ai_candidates?: Candidate[];
    semantic?: { model_version: string; similarity: number | null; candidates: Candidate[] };
    model?: { version: string; algorithm: string; probability: number; top_features: [string, number][] } | null; alias_match?: boolean;
    segments?: DetectedProduct[]; classification?: { item_id: number; name: string; phrase: string }[];
    history: { id: number; decision: string; item: string | null; by: string | null; on: string }[];
};
export type Job = { id: number; status: string; total: number; processed: number; batch_size: number; model_version: string; metrics: Record<string, unknown>; error: string; pause_requested: boolean } | null;
export type MatchingResponse = { matcher: string; can_approve: boolean; summary: Partial<Record<Band, number>>; suggestions: MatchSuggestion[]; latest_job: Job;
    decisions: { id: number; decision: string; source_description: string; hsn_code: string; sion: string | null; chosen_item: string | null; suggested_item: string | null; confidence: number; decided_by: string | null; decided_on: string }[] };
export type Health = { model: { ok: boolean; version?: string; variant?: string; error?: string }; worker: { ok: boolean; consumers?: string[]; error?: string }; available_memory_mb: number | null };

export const BAND: Record<Band, { tone: Tone; label: string }> = {
    CLASSIFIED: { tone: "success", label: "Multi-product classified" },
    APPROVED: { tone: "success", label: "Approved mapping" }, HIGH: { tone: "primary", label: "Strong ≥95%" }, STRONG: { tone: "info", label: "Probable 90–94%" },
    REVIEW: { tone: "warning", label: "Probable 80–89%" }, UNCLASSIFIED: { tone: "neutral", label: "Below 80% — kept separate" },
    CONFLICT: { tone: "danger", label: "Conflict" }, UNMATCHED: { tone: "neutral", label: "No candidate" },
};
export const ORDER: Band[] = ["CLASSIFIED", "HIGH", "STRONG", "REVIEW", "CONFLICT", "UNCLASSIFIED", "UNMATCHED", "APPROVED"];

/** Shared with Product Analysis so the per-product match status reuses the same cached payload. */
export const matchingQuery = (query: string) => ({
    queryKey: ["item-pivot-matching", query],
    queryFn: async ({ signal }: { signal: AbortSignal }) => (await api.get(`item-pivot/matching/?${query}`, { signal })).data as MatchingResponse,
    staleTime: 60_000,
});


export type IntelModel = {
    id: number; version: string; status: "CANDIDATE" | "ACTIVE" | "RETIRED" | "REJECTED" | "INSUFFICIENT_LABELS"; algorithm: string; dataset: string;
    metrics: { holdout?: Record<string, unknown> & { precision?: number | null; recall?: number | null; false_merge_rate?: number | null; ece?: number; n?: number };
        gate?: { passed: boolean; failures: string[] }; labels?: number; positives?: number; negatives?: number };
    comparison: { version?: string; holdout?: { precision?: number | null } }; notes: string; trained_on: string; promoted_on: string | null; trained_by: string | null;
};
export type InventoryRow = {
    source: string; records: number; unique_normalised?: number; duplicate_observations?: number; missing_description?: number; missing_hsn?: number | null;
    first?: string | null; last?: string | null; labels?: Record<string, number>; master_links?: Record<string, number>; trust: string;
};
export type IntelAdmin = {
    can_manage: boolean; inventory: InventoryRow[];
    labels: { verified: number; positive: number; negative: number; required: { total: number; per_class: number }; new_since_last_dataset: number };
    active_model: IntelModel | null; promotion_gate: Record<string, number>; models: IntelModel[];
    datasets: { id: number; version: string; observations: number; unique: number; labels: number; sha256: string; created_on: string }[];
    aliases: number; events: { id: number; action: string; detail: Record<string, unknown>; user: string | null; on: string }[];
};
export type AliasRow = { id: number; alias: string; normalised: string; item_id: number; item: string; sion: string | null; source: string; created_by: string | null; created_on: string };

/** Server message from an API error (``detail`` or the first field error), else the fallback. */
export function errorText(err: unknown, fallback: string): string {
    const data = (err as { response?: { data?: unknown } })?.response?.data;
    if (data && typeof data === "object") {
        const record = data as Record<string, unknown>;
        if (typeof record.detail === "string") return record.detail;
        const first = Object.values(record).find((v) => typeof v === "string");
        if (typeof first === "string") return first;
    }
    return fallback;
}

export type DetectedProduct = {
    index: number; phrase: string; normalized: string; hsn_code: string; suggestion: { item_id: number; name: string } | null; confidence: number;
    band: "HIGH" | "REVIEW" | "LOW" | "CONFLICT" | "UNMATCHED"; compatible: boolean; conflicts: string[];
    checks: Partial<Record<"sion" | "hsn" | "entitlement", MatchCheck>>; explanation: string; candidates: Candidate[]; entitlement: string | null;
    approved: { item_id: number; name: string; by: string | null; on: string } | null;
};
export type SelectionResult = { index: number | null; phrase: string; item_id: number | null; item: string | null; ok: boolean; reasons: string[] };

/** Remount key for the multi-product panel: changes when the detected products themselves change (not when approvals do). */
export const segmentSignature = (s: MatchSuggestion): string =>
    `${s.source_key}:${(s.segments ?? []).map((x) => `${x.index}=${x.phrase}=${x.suggestion?.item_id ?? ""}`).join("|")}`;
