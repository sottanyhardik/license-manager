import api from "@/api/axios";

export type RuleCondition = {
    field: "HSN" | "HSN_DIGITS" | "PRODUCT_DESCRIPTION" | "ITEM_KEY" | string;
    comparator?: string;
    operator?: string;
    value: string;
};
export type RuleGroup = { operator: "AND" | "OR"; conditions: Array<RuleCondition | RuleGroup> };

export type PlanningStrategy = "STANDARD" | "SPLIT_BY_UNIT_VALUE" | "SPLIT_BY_PERCENT";
export type SplitAllocationBucket = { code: string; min_price: string; max_price: string; reference_price: string };
export type SplitAllocationConfig = { algorithm: "SPLIT_BY_UNIT_VALUE"; basis: "BALANCE_CIF_PER_QUANTITY"; buckets: SplitAllocationBucket[] };
export type RuleAllocationStrategy = {
    strategy?: PlanningStrategy;
    import_item?: number | null;
    unit_value_rows?: UnitValueRow[];
    percentage_rows?: PercentageRow[];
    config?: SplitAllocationConfig | Record<string, unknown>;
};

export type UnitValueRow = {
    id?: number;
    import_item: number;
    min_unit_price: string;
    max_unit_price: string;
    preferred_unit_price: string;
    priority?: number;
};

export type PercentageRow = {
    id?: number;
    import_item: number;
    percentage: string;
    unit_price: string;
    max_quantity?: string | null;
    priority?: number;
};

export type SionPlanningRule = {
    id?: number;
    sion: number;
    name: string;
    expression: RuleGroup;
    max_unit_price: string;
    unit: string;
    priority: number;
    is_active: boolean;
    execution_output?: string;
    strategy?: PlanningStrategy;
    import_item?: number | null;
    standard_item_name?: string | null;
    unit_value_rows?: UnitValueRow[];
    percentage_rows?: PercentageRow[];
    percentage_constraint?: string | number | null;
    rule_type?: string;
    output_item?: number | null;
    version?: number;
    modified_on?: string;
    modified_by_username?: string;
};

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
export async function deleteSionPlanningRule(id: number): Promise<void> {
    await api.delete(`sion-planning-rules/${id}/`);
}
export type ImportItemOption = { id: number; name: string; unit?: string; sionCode?: string };
export type ImportItemPage = { items: ImportItemOption[]; nextPage: number | null };

function normalizeImportItems(data: unknown): ImportItemPage {
    const payload = data as { results?: unknown[]; next?: string | null } | unknown[] | null;
    const rows = Array.isArray(payload) ? payload : Array.isArray(payload?.results) ? payload.results : [];
    const items = rows.flatMap((raw) => {
        if (!raw || typeof raw !== "object") return [];
        const item = raw as Record<string, unknown>;
        const id = Number(item.id);
        const name = typeof item.name === "string" ? item.name : "";
        if (!Number.isInteger(id) || !name) return [];
        return [{ id, name, unit: typeof item.unit === "string" ? item.unit : undefined,
            sionCode: typeof item.sion_code === "string" ? item.sion_code : undefined }];
    });
    const next = !Array.isArray(payload) && payload?.next ? new URL(payload.next, window.location.origin).searchParams.get("page") : null;
    return { items, nextPage: next ? Number(next) : null };
}

export async function searchSionImportItems(sionId: number, search = "", page = 1): Promise<ImportItemPage> {
    const { data } = await api.get("sion-planning-rules/import-items/", { params: { sion_id: sionId, search, page } });
    return normalizeImportItems(data);
}

export async function fetchSionImportItem(sionId: number, itemId: number): Promise<ImportItemOption | null> {
    const { data } = await api.get("sion-planning-rules/import-items/", { params: { sion_id: sionId, item_id: itemId } });
    return normalizeImportItems(data).items[0] ?? null;
}
/** @deprecated Retained for older planning surfaces during their migration. */
export async function fetchRuleAllocationStrategy(id: number): Promise<RuleAllocationStrategy> {
    return (await api.get(`sion-planning-rules/${id}/allocation-strategy/`)).data;
}
/** @deprecated Retained for older planning surfaces during their migration. */
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
export type SplitAllocationPreviewLine = { bucket: string; quantity: string; unit_price: string; cif: string };
export type SplitAllocationPreview = {
    strategy: "SPLIT_BY_UNIT_VALUE"; status: string; total_quantity: string; balance_cif: string;
    effective_unit_price?: string; quantity_remaining: string; cif_remaining: string; reason?: string;
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
    sion?: string; sion_code?: string; mode?: SionPlanningMode; rules_processed?: number | unknown[]; rules_executed?: unknown[];
    total_results?: { sions_executed?: number; total_lines_written?: number }; total_lines_written?: number;
    summary?: { licenses_matched?: number; licenses_new?: number; licenses_changed?: number; licenses_unchanged?: number; licenses_shortage?: number; licenses_skipped?: number; rules_processed?: number };
    licenses?: SionPlanningPreviewLicense[]; conflicts?: unknown[];
    diagnostics?: { skip_reasons?: Array<{ item_key: string; reason: string }> };
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

/** Exact URL-scoped planning contract.  Values are calculated only on the server. */
export type ScopedPlanPreview = { licence_number: string; licence_id: number; SION: string; lines: any[]; unresolved_rows: any[]; save_allowed: boolean; preview_version: string; grand_totals: Record<string, string>; balance_cif?: string };
export async function previewScopedSionPlan(license_number: string, sion: string): Promise<ScopedPlanPreview> {
    return (await api.post("sion-planning-rules/preview-scoped/", { license_number, sion })).data;
}
export async function saveScopedSionPlan(license_number: string, sion: string, preview_version: string): Promise<ScopedPlanPreview> {
    return (await api.post("sion-planning-rules/save-scoped/", { license_number, sion, preview_version })).data;
}
export async function reorderSionPlanningRules(sionId: number, ruleOrder: number[]): Promise<SionPlanningRule[]> {
    return (await api.post("sion-planning-rules/reorder/", { sion_id: sionId, rule_order: ruleOrder })).data;
}
export async function planLicense(licenseId: number, mode: SionPlanningMode = "NEW"): Promise<SionPlanningPreview> {
    return (await api.post("sion-planning-rules/plan-license/", { license_id: licenseId, mode })).data;
}

/** Result of the synchronous canonical Auto Plan action. */
export type AutoPlanResponse = {
    license_id: number;
    license_number: string;
    planning_state: "CURRENT";
    message: string;
    result: { write_results?: number; sion_ids?: number[] };
};

/**
 * Execute a forced canonical Auto Plan for one licence.  This is deliberately
 * the only browser entry point: the server remains authoritative and resolves
 * only after its transaction has committed.
 */
export async function autoPlanLicense(licenseId: number): Promise<AutoPlanResponse> {
    try {
        const response = await api.post<AutoPlanResponse>(`licenses/${licenseId}/auto-plan/`, { force: true });
        return response.data;
    } catch (error) {
        console.error('[autoPlanLicense] Error:', error);
        throw error;
    }
}
