import api from "@/api/axios";

export type RuleCondition = {
    field: "HSN" | "HSN_DIGITS" | "PRODUCT_DESCRIPTION" | "ITEM_KEY" | string;
    comparator?: string;
    operator?: string;
    value: string;
};
export type RuleGroup = { operator: "AND" | "OR"; conditions: Array<RuleCondition | RuleGroup> };

/**
 * UI representation of the canonical SionPlanningAction.config for a SPLIT
 * action. Prices remain strings so the browser never converts planning
 * decimals to IEEE-754 numbers.
 */
export type SplitAllocationBucket = {
    code: string;
    min_price: string;
    max_price: string;
    reference_price: string;
};
export type SplitAllocationConfig = {
    algorithm: "SPLIT_BY_UNIT_VALUE";
    basis: "BALANCE_CIF_PER_QUANTITY";
    buckets: SplitAllocationBucket[];
};
export type RuleAllocationStrategy =
    | { strategy: "STANDARD"; action_id?: number }
    | { strategy: "SPLIT_BY_UNIT_VALUE"; action_id?: number; config: SplitAllocationConfig };
export type SionPlanningRule = { id?: number; sion: number; name: string; expression: RuleGroup; max_unit_price: string; unit: string; priority: number; is_active: boolean; execution_output?: string; version?: number; modified_on?: string; modified_by_username?: string };

function safeRuleExpression(value: unknown): RuleGroup {
    if (!value || typeof value !== "object") return { operator: "AND", conditions: [] };
    const node = value as Record<string, unknown>;
    const rawChildren = Array.isArray(node.conditions) ? node.conditions : Array.isArray(node.args) ? node.args : null;
    if (rawChildren) {
        const operator = String(node.operator ?? "AND").toUpperCase() === "OR" ? "OR" : "AND";
        return { operator, conditions: rawChildren.filter((child) => child && typeof child === "object").map((child) => {
            const candidate = child as Record<string, unknown>;
            return Array.isArray(candidate.conditions) || Array.isArray(candidate.args) ? safeRuleExpression(candidate) : candidate as RuleCondition;
        }) };
    }
    // Historical rules may contain a single leaf at the root. The editor and
    // read view consistently operate on one canonical root group.
    return node.field ? { operator: "AND", conditions: [node as RuleCondition] } : { operator: "AND", conditions: [] };
}

function normalizeRule(rule: SionPlanningRule): SionPlanningRule {
    return { ...rule, expression: safeRuleExpression(rule.expression) };
}

export async function fetchSionPlanningRules(sion: number): Promise<SionPlanningRule[]> {
    const { data } = await api.get("sion-planning-rules/", { params: { sion, is_active: true } });
    return (data?.results ?? data ?? []).map(normalizeRule);
}
export async function createSionPlanningRule(payload: SionPlanningRule): Promise<SionPlanningRule> {
    return (await api.post("sion-planning-rules/", payload)).data;
}
export async function updateSionPlanningRule(id: number, payload: Partial<SionPlanningRule>): Promise<SionPlanningRule> {
    return (await api.patch(`sion-planning-rules/${id}/`, payload)).data;
}
export async function fetchRuleAllocationStrategy(id: number): Promise<RuleAllocationStrategy> {
    return (await api.get(`sion-planning-rules/${id}/allocation-strategy/`)).data;
}
export async function updateRuleAllocationStrategy(id: number, payload: RuleAllocationStrategy): Promise<RuleAllocationStrategy> {
    return (await api.patch(`sion-planning-rules/${id}/allocation-strategy/`, payload)).data;
}
export type SionPlanningMode = "NEW" | "ALL";
export type SionPlanningChangeStatus = "NEW" | "CHANGE" | "NO_CHANGE" | "SHORTAGE" | "SKIPPED";
export type SionPlanningPreviewItem = {
    id?: number; item_id?: number; import_item_id?: number; rule_id?: number; rule_uid?: string; rule_name?: string; rule_priority?: number;
    item_name?: string; description?: string; product_description?: string; hsn?: string; hsn_code?: string; unit?: string;
    current_unit_price?: string; unit_price?: string; max_unit_price?: string; price_status?: string;
    available_qty?: string; available_quantity?: string; existing_planned_qty?: string; current_planned_quantity?: string;
    proposed_planned_qty?: string; proposed_planned_quantity?: string; quantity_change?: string; shortage_qty?: string; status?: string;
    allocation?: SplitAllocationPreview;
};
export type SplitAllocationPreviewLine = {
    bucket: string;
    quantity: string;
    unit_price: string;
    cif: string;
};
export type SplitAllocationPreview = {
    strategy: "SPLIT_BY_UNIT_VALUE";
    status: "ALLOCATED" | "BLOCKED" | "PRECISION_CONFLICT" | "ZERO_AVAILABLE_QUANTITY" | string;
    total_quantity: string;
    balance_cif: string;
    effective_unit_price?: string;
    quantity_remaining: string;
    cif_remaining: string;
    reason?: string;
    lines: SplitAllocationPreviewLine[];
};
export type SionPlanningPreviewLicense = {
    license_id: number; license_number: string; license_type?: string; sion?: string;
    matched_item_count: number; matched_rule_count: number; matched_rule_priorities?: number[];
    existing_plan?: Record<string, unknown> | null; proposed_plan?: Record<string, unknown> | null;
    existing_plan_summary?: string; proposed_plan_summary?: string;
    change_status: SionPlanningChangeStatus; has_shortage: boolean; shortage_qty?: string;
    status?: string; items: SionPlanningPreviewItem[];
};
export type SionPlanningPreview = {
    sion?: string; mode?: SionPlanningMode; rules_processed?: number | unknown[]; rules_executed?: unknown[];
    summary?: { licenses_matched?: number; licenses_new?: number; licenses_changed?: number; licenses_unchanged?: number; licenses_shortage?: number; licenses_skipped?: number; rules_processed?: number };
    licenses?: SionPlanningPreviewLicense[]; conflicts?: unknown[];
};

function planningPayload(sionId: number, mode: SionPlanningMode, licenseIds?: number[]) {
    return licenseIds?.length ? { sion_id: sionId, mode, license_ids: licenseIds } : { sion_id: sionId, mode };
}

export async function testSionPlanningRule(id: number, licenseIds?: number[]) {
    const payload = licenseIds?.length ? { license_ids: licenseIds } : {};
    return (await api.post(`sion-planning-rules/${id}/test/`, payload)).data;
}
export async function planSavedSionRules(sionId: number, mode: SionPlanningMode = "NEW", licenseIds?: number[]) {
    return (await api.post("sion-planning-rules/plan-sion/", planningPayload(sionId, mode, licenseIds))).data;
}
export async function previewSavedSionRules(sionId: number, mode: SionPlanningMode = "NEW", licenseIds?: number[]): Promise<SionPlanningPreview> {
    return (await api.post("sion-planning-rules/preview-sion/", planningPayload(sionId, mode, licenseIds))).data;
}
export async function reorderSionPlanningRules(sionId: number, ruleOrder: number[]): Promise<SionPlanningRule[]> {
    return (await api.post("sion-planning-rules/reorder/", { sion_id: sionId, rule_order: ruleOrder })).data;
}
