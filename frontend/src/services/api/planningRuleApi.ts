import api from "@/api/axios";

export type RuleCondition = { field: "HSN" | "PRODUCT_DESCRIPTION"; comparator: "CONTAINS" | "NOT_CONTAINS"; value: string };
export type RuleGroup = { operator: "AND" | "OR"; conditions: Array<RuleCondition | RuleGroup> };
export type SionPlanningRule = { id?: number; sion: number; name: string; expression: RuleGroup; max_unit_price: string; unit: string; priority: number; is_active: boolean; version?: number; modified_on?: string; modified_by_username?: string };

export async function fetchSionPlanningRules(sion: number): Promise<SionPlanningRule[]> {
    const { data } = await api.get("sion-planning-rules/", { params: { sion, is_active: true } });
    return data?.results ?? data ?? [];
}
export async function createSionPlanningRule(payload: SionPlanningRule): Promise<SionPlanningRule> {
    return (await api.post("sion-planning-rules/", payload)).data;
}
export async function updateSionPlanningRule(id: number, payload: Partial<SionPlanningRule>): Promise<SionPlanningRule> {
    return (await api.patch(`sion-planning-rules/${id}/`, payload)).data;
}
export async function testSionPlanningRule(id: number, licenseIds: number[] = []) {
    return (await api.post(`sion-planning-rules/${id}/test/`, { license_ids: licenseIds })).data;
}
export async function planSavedSionRules(sionId: number, licenseIds: number[] = []) {
    return (await api.post("sion-planning-rules/plan-sion/", { sion_id: sionId, license_ids: licenseIds })).data;
}
export async function previewSavedSionRules(sionId: number, licenseIds: number[] = []) {
    return (await api.post("sion-planning-rules/preview-sion/", { sion_id: sionId, license_ids: licenseIds })).data;
}
export async function reorderSionPlanningRules(sionId: number, ruleOrder: number[]): Promise<SionPlanningRule[]> {
    return (await api.post("sion-planning-rules/reorder/", { sion_id: sionId, rule_order: ruleOrder })).data;
}
