/** Product-matching types and the shared query (Mapping workspace → Licence Import Item). */
import api from "@/api/axios";

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
export type MatchingResponse = { matcher: string; can_approve: boolean; summary: Partial<Record<Band, number>>; suggestions: MatchSuggestion[]; 
    decisions: { id: number; decision: string; source_description: string; hsn_code: string; sion: string | null; chosen_item: string | null; suggested_item: string | null; confidence: number; decided_by: string | null; decided_on: string }[] };
/** Licence Import Item queue (existing matching backend, per SION). */
export const matchingQuery = (query: string) => ({
    queryKey: ["item-pivot-matching", query],
    queryFn: async ({ signal }: { signal: AbortSignal }) => (await api.get(`item-pivot/matching/?${query}`, { signal })).data as MatchingResponse,
    staleTime: 60_000,
});


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
