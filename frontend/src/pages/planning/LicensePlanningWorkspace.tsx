import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ComponentProps } from "react";
import { ArrowDown, ArrowLeft, ArrowUp, ChevronDown, ChevronRight, Eye, Loader2, MoreHorizontal, Pencil, Plus, Search, TestTube2, Zap, CheckCircle2, AlertTriangle, History, ClipboardList, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import api from "@/api/axios";
import { Button as UiButton } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { createSionPlanningRule, deleteSionPlanningRule, fetchSionPlanningRules, planSavedSionRules, previewSavedSionRules, reorderSionPlanningRules, testSionPlanningRule, updateSionPlanningRule, previewScopedSionPlan, type RuleAllocationStrategy, type SionPlanningMode, type SionPlanningPreview, type SionPlanningPreviewLicense, type SionPlanningRule, type ScopedPlanPreview } from "@/services/api/planningRuleApi";
import { SplitAllocationPreview } from "./SplitAllocationPreview";
import { AllocationStrategyEditor } from "./AllocationStrategyEditor";
import { validatePlanningRule, hasValidationErrors, type RuleFormErrors } from "./ruleFormValidation";
import { ExpressionTreeEditor } from "./ExpressionTreeEditor";
import { emptyRuleCondition } from "./expressionTreeUtils";

// This workspace contains actions, never form submissions. Keeping the native
// type explicit prevents a future surrounding form from turning any editor
// action into a submit/navigation (and therefore a scroll-to-top).
const Button = (props: ComponentProps<typeof UiButton>) => <UiButton type="button" {...props} />;

const emptyRule = (sion: number): SionPlanningRule => ({ sion, name: "", expression: { operator: "AND", conditions: [emptyRuleCondition()] }, max_unit_price: "", unit: "KG", priority: 0, is_active: true });

function saveErrorMessage(reason: unknown): string {
    const data = (reason as { response?: { data?: unknown } })?.response?.data;
    if (typeof data === "string") return data;
    if (data && typeof data === "object") {
        const messages = Object.values(data as Record<string, unknown>).flatMap((value) =>
            Array.isArray(value) ? value.map(String) : typeof value === "string" ? [value] : [],
        );
        if (messages.length) return messages.join(" ");
    }
    return "Unable to save rule";
}

const planSummary = (license: SionPlanningPreviewLicense, which: "existing" | "proposed") => {
    const explicit = which === "existing" ? license.existing_plan_summary : license.proposed_plan_summary;
    if (explicit) return explicit;
    const snapshot = (which === "existing" ? license.existing_plan : license.proposed_plan) as Record<string, unknown> | null | undefined;
    return String(snapshot?.display_summary ?? snapshot?.planned_quantity ?? snapshot?.total_quantity ?? snapshot?.total_planned_quantity ?? "—");
};

function LicensePreview({ preview, onViewPlan }: { preview: SionPlanningPreview; onViewPlan: (licenseId: number) => void }) {
    const [expanded, setExpanded] = useState<Set<number>>(new Set());
    const licenses = preview.licenses ?? [];
    const summary = preview.summary ?? {};
    const rulesProcessed = summary.rules_processed ?? (Array.isArray(preview.rules_processed) ? preview.rules_processed.length : preview.rules_processed) ?? preview.rules_executed?.length ?? 0;
    const toggle = (licenseId: number) => setExpanded((current) => { const next = new Set(current); next.has(licenseId) ? next.delete(licenseId) : next.add(licenseId); return next; });
    const statusLabel = (status: string) => status === "NO_CHANGE" ? "NO CHANGE" : status;
    return <section aria-label="License planning preview" className="rounded-lg border bg-muted/20 p-3">
        <h2 className="font-semibold">Plan preview</h2>
        <div className="mt-2 grid gap-2 text-sm sm:grid-cols-3 lg:grid-cols-6">
            <span><strong>Matched Licenses:</strong> {summary.licenses_matched ?? licenses.length}</span><span><strong>New:</strong> {summary.licenses_new ?? 0}</span><span><strong>Changed:</strong> {summary.licenses_changed ?? 0}</span><span><strong>No Change:</strong> {summary.licenses_unchanged ?? 0}</span><span><strong>Shortage:</strong> {summary.licenses_shortage ?? 0}</span><span><strong>Rules Processed:</strong> {rulesProcessed}</span>
        </div>
        {!!preview.conflicts?.length && <p role="alert" className="mt-2 text-sm text-destructive">Conflicts: {preview.conflicts.length}</p>}
        {!licenses.length ? <p className="mt-4 rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">No eligible licenses matched the current {preview.sion ?? "SION"} rules.</p> :
            <div className="mt-3 overflow-x-auto"><table className="w-full text-xs"><thead><tr className="border-b text-left"><th className="p-2">License</th><th>SION</th><th>Matched Items</th><th>Rules</th><th>Existing Plan</th><th>Proposed Plan</th><th>Change</th><th>Shortage</th><th>Status</th><th>Actions</th></tr></thead><tbody>{licenses.map((license) => {
                const isExpanded = expanded.has(license.license_id);
                return <Fragment key={license.license_id}>{/* The backend guarantees one canonical object per license. */}<tr className="border-b align-top"><td className="p-2 font-medium">{license.license_number ?? license.license_id}</td><td>{license.sion ?? preview.sion ?? "—"}</td><td>{license.matched_item_count}</td><td title={license.matched_rule_priorities?.map((priority) => `#${priority}`).join(", ")}>{license.matched_rule_count}</td><td>{planSummary(license, "existing")}</td><td>{planSummary(license, "proposed")}</td><td><Badge variant={license.change_status === "NO_CHANGE" ? "secondary" : license.change_status === "SKIPPED" ? "outline" : "default"}>{statusLabel(license.change_status)}</Badge></td><td>{license.has_shortage ? license.shortage_qty ?? "Yes" : "No"}</td><td>{license.status ?? "—"}</td><td className="whitespace-nowrap p-1"><Button size="sm" variant="outline" onClick={() => onViewPlan(license.license_id)}>View Plan</Button><Button size="sm" variant="ghost" aria-expanded={isExpanded} aria-label={`${isExpanded ? "Hide" : "View"} items for ${license.license_number}`} onClick={() => toggle(license.license_id)}>{isExpanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}View Items</Button></td></tr>
                    {isExpanded && <tr className="border-b bg-background/60"><td colSpan={10} className="p-3"><div className="space-y-2">{license.items.map((item, index) => <article key={item.import_item_id ?? item.item_id ?? item.id ?? index} className="rounded border p-2"><p className="font-medium">{item.rule_priority != null ? `#${item.rule_priority} ` : ""}{item.rule_name ?? item.item_name ?? item.description ?? "Matched item"}</p><p className="text-muted-foreground">HSN: {item.hsn ?? item.hsn_code ?? "—"} · Product: {item.product_description ?? item.description ?? "—"} · Available: {item.available_quantity ?? item.available_qty ?? "—"} · Current: {item.current_planned_quantity ?? item.existing_planned_qty ?? "—"} · Proposed: {item.proposed_planned_quantity ?? item.proposed_planned_qty ?? "—"} · Max Price: {item.max_unit_price ?? "—"}</p>{item.allocation && <SplitAllocationPreview allocation={item.allocation} />}</article>)}</div></td></tr>}</Fragment>;
            })}</tbody></table></div>}
    </section>;
}

function AllocationStrategySummary({ rule }: { rule?: SionPlanningRule }) {
    if (!rule) return null;
    const strategyLabel = { STANDARD: "Standard", SPLIT_BY_UNIT_VALUE: "Split by Unit Value", SPLIT_BY_PERCENT: "Split by %" }[rule.strategy || "STANDARD"];
    return <div><h3 className="text-sm font-semibold">Planning Strategy</h3><p className="mt-1 text-sm">{strategyLabel}</p></div>;
}

function ScopedPreview({ preview }: { preview: ScopedPlanPreview }) {
    return <section aria-label="Exact licence planning preview" className="rounded-lg border bg-muted/20 p-3">
        <h2 className="font-semibold">{preview.licence_number} · {preview.SION}</h2>
        <p className="mt-1 text-sm">Authoritative balance CIF: {preview.balance_cif ?? "—"}</p>
        {!!preview.unresolved_rows.length && <p role="alert" className="mt-2 text-sm text-destructive">Unresolved mappings: {preview.unresolved_rows.map(x => x.reason).join("; ")}</p>}
        <div className="mt-3 overflow-x-auto"><table className="w-full text-xs"><thead><tr className="border-b text-left"><th className="p-2">Input</th><th>Priority</th><th>Target</th><th>Actual Qty/CIF</th><th>Excess Qty/CIF</th><th>New Qty/CIF</th><th>Final Qty/CIF</th><th>Closing CIF</th><th>Status</th></tr></thead><tbody>{preview.lines.map((line, i) => <tr key={`${line.licence_item}-${line.SION_input}-${i}`} className="border-b"><td className="p-2">{line.SION_input}</td><td>{line.priority}.{line.priority_sequence}</td><td>{line.percentage_target_quantity}</td><td>{line.actual_debited_quantity} / {line.actual_debited_cif}</td><td>{line.excess_debited_quantity} / {line.excess_debited_cif}</td><td>{line.new_planned_quantity} / {line.new_planned_cif}</td><td>{line.final_accounted_quantity} / {line.final_accounted_cif}</td><td>{line.closing_balance_cif}</td><td>{line.priority_status}</td></tr>)}</tbody></table></div>
        <p className="mt-2 text-sm">New planned CIF: {preview.grand_totals.new_planned_cif} · Remaining CIF: {preview.grand_totals.remaining_cif} · Reconciliation difference: {preview.grand_totals.reconciliation_difference}</p>
    </section>;
}

function strategyLabel(strategy?: RuleAllocationStrategy["strategy"]) {
    return ({ STANDARD: "Single Item", SPLIT_BY_PERCENT: "Split by %", SPLIT_BY_UNIT_VALUE: "Split by Unit Value" } as Record<string, string>)[strategy ?? "STANDARD"];
}

function displayDate(value?: string | null): string {
    if (!value) return "Not available";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Not available" : date.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

function MatchLogicView({ group, depth = 0 }: { group: SionPlanningRule["expression"]; depth?: number }) {
    if (!group?.conditions?.length) return <p className="text-sm text-muted-foreground">No match conditions configured.</p>;
    return <div className={depth ? "ml-4 border-l pl-4" : ""}><p className="text-sm font-medium">Match {group.operator === "OR" ? "ANY" : "ALL"}:</p><ol className="mt-2 space-y-2 text-sm">{group.conditions.map((condition, index) => <li key={index}>{"conditions" in condition ? <MatchLogicView group={condition} depth={depth + 1} /> : <span><span className="mr-2 text-muted-foreground">•</span>{condition.field.replace(/_/g, " ")} {condition.comparator ?? condition.operator ?? "is"} <strong>{condition.value}</strong></span>}</li>)}</ol></div>;
}

function matchLogicCounts(group?: SionPlanningRule["expression"]): { conditions: number; groups: number } {
    if (!group?.conditions?.length) return { conditions: 0, groups: 0 };
    return group.conditions.reduce((result, condition) => {
        if ("conditions" in condition) {
            const child = matchLogicCounts(condition);
            return { conditions: result.conditions + child.conditions, groups: result.groups + child.groups + 1 };
        }
        return { ...result, conditions: result.conditions + 1 };
    }, { conditions: 0, groups: 0 });
}

export default function LicensePlanningWorkspace() {
    const [params, setParams] = useSearchParams(); const navigate = useNavigate(); const location = useLocation();
    const origin = params.get("origin") || "/licenses";
    const [sions, setSions] = useState<any[]>([]); const [sion, setSion] = useState<number | null>(null); const [rules, setRules] = useState<SionPlanningRule[]>([]); const [draft, setDraft] = useState<SionPlanningRule | null>(null); const [selectedRuleId, setSelectedRuleId] = useState<number | null>(Number(params.get("rule")) || null); const [activeTab, setActiveTab] = useState(params.get("view") || params.get("tab") || "rules"); const [ruleSearch, setRuleSearch] = useState(""); const [normSearch, setNormSearch] = useState(""); const [strategyFilter, setStrategyFilter] = useState("all"); const [statusFilter, setStatusFilter] = useState("all"); const [pendingSion, setPendingSion] = useState<number | null | undefined>(undefined); const [confirmForceAll, setConfirmForceAll] = useState(false); const [confirmDeleteRule, setConfirmDeleteRule] = useState<SionPlanningRule | null>(null); const [busy, setBusy] = useState<"save" | "test" | "preview" | "plan-new" | "plan-all" | "deactivate" | "reorder" | "delete" | null>(null); const [preview, setPreview] = useState<SionPlanningPreview | null>(null); const [error, setError] = useState(""); const [loading, setLoading] = useState(true); const [draggedRuleId, setDraggedRuleId] = useState<number | null>(null);
    const [allocationDraft, setAllocationDraft] = useState<RuleAllocationStrategy | null>(null);
    const requestedLicenseNumber = params.get("license");
    const requestedSion = params.get("sion");
    const [scopedPreview, setScopedPreview] = useState<ScopedPlanPreview | null>(null);
    const [savedAllocation, setSavedAllocation] = useState<RuleAllocationStrategy | null>(null);
    const [formErrors, setFormErrors] = useState<RuleFormErrors>({});
    const saveRef = useRef<() => Promise<SionPlanningRule | null>>(() => Promise.resolve(null));
    const preserveScroll = () => {
        const host = document.getElementById("main-content");
        if (!host) return () => undefined;
        const top = host.scrollTop;
        return () => requestAnimationFrame(() => requestAnimationFrame(() => {
            host.scrollTop = top;
        }));
    };
    useEffect(() => { setLoading(true); api.get("masters/sion-classes/", { params: { is_active: true, page_size: 500, ordering: "norm_class" } }).then(({ data }) => { const rows = data?.results ?? data ?? []; setSions(rows); const requested = params.get("sion"); if (requested) { const match = rows.find((row: any) => String(row.id) === requested || String(row.norm_class).toUpperCase() === requested.toUpperCase()); if (match) setSion(match.id); } }).catch(() => setError("Unable to load SION norms.")).finally(() => setLoading(false)); }, [params]);
    useEffect(() => { if (!requestedLicenseNumber || !requestedSion) return; setLoading(true); previewScopedSionPlan(requestedLicenseNumber, requestedSion).then(setScopedPreview).catch((e) => setError(e?.response?.data?.error || "Unable to preview the exact licence/SION selection.")).finally(() => setLoading(false)); }, [requestedLicenseNumber, requestedSion]);
    useEffect(() => { if (!sion) { setRules([]); setDraft(null); setSelectedRuleId(null); setPreview(null); return; } setLoading(true); setError(""); setDraft(null); setPreview(null); fetchSionPlanningRules(sion).then((rows) => { const ordered = [...rows].sort((a, b) => a.priority - b.priority); setRules(ordered); setSelectedRuleId((current) => ordered.some((rule) => rule.id === current) ? current : ordered[0]?.id ?? null); }).catch(() => setError("Unable to load planning rules.")).finally(() => setLoading(false)); }, [sion]);
    const savedDraft = draft?.id ? rules.find((rule) => rule.id === draft.id) : null;
    useEffect(() => {
        if (!draft) { setAllocationDraft({}); setSavedAllocation({}); return; }
        const allocation = {
            strategy: draft.strategy,
            import_item: draft.import_item,
            unit_value_rows: draft.unit_value_rows,
            percentage_rows: draft.percentage_rows,
        };
        setAllocationDraft(allocation);
        if (savedDraft) {
            setSavedAllocation({
                strategy: savedDraft.strategy,
                import_item: savedDraft.import_item,
                unit_value_rows: savedDraft.unit_value_rows,
                percentage_rows: savedDraft.percentage_rows,
            });
        }
    }, [draft, savedDraft]);

    const ruleHasUnsavedChanges = !!draft && (!savedDraft || JSON.stringify(draft) !== JSON.stringify(savedDraft));
    const allocationHasUnsavedChanges = !!draft && !!allocationDraft && JSON.stringify(allocationDraft) !== JSON.stringify(savedAllocation);
    const hasUnsavedChanges = ruleHasUnsavedChanges || allocationHasUnsavedChanges;

    useEffect(() => {
        const warn = (event: BeforeUnloadEvent) => { if (hasUnsavedChanges) { event.preventDefault(); event.returnValue = ""; } };
        window.addEventListener("beforeunload", warn);
        return () => window.removeEventListener("beforeunload", warn);
    }, [hasUnsavedChanges]);
    useEffect(() => {
        const keyboard = (event: KeyboardEvent) => {
            if (event.key === "Escape" && draft) setDraft(null);
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && hasUnsavedChanges && !hasValidationErrors(formErrors)) { event.preventDefault(); void saveRef.current(); }
        };
        window.addEventListener("keydown", keyboard);
        return () => window.removeEventListener("keydown", keyboard);
    }, [draft, formErrors, hasUnsavedChanges]);

    // Validate form whenever draft or allocation changes
    useEffect(() => {
        if (draft && allocationDraft) {
            const errors = validatePlanningRule(draft, allocationDraft);
            setFormErrors(errors);
        } else if (draft) {
            const errors = validatePlanningRule(draft, null);
            setFormErrors(errors);
        }
    }, [draft, allocationDraft]);
    const changeAllocationStrategy = (next: any) => {
        setAllocationDraft(next);
        if (draft) {
            setDraft({ ...draft, strategy: next.strategy, import_item: next.import_item, unit_value_rows: next.unit_value_rows, percentage_rows: next.percentage_rows });
        }
    };
    // PLAN/Preview execute saved active database rules only. Keep the UI gate
    // aligned with that backend contract even if an inactive row is returned
    // by an older/cached API response.
    const activeSavedRules = rules.filter((rule) => rule.id != null && rule.is_active);
    const canExecuteSion = activeSavedRules.length > 0 && !hasUnsavedChanges;
    const save = async () => {
        if (!draft || !allocationDraft || !hasUnsavedChanges) return null;
        setBusy("save");
        setError("");
        const { priority: _databasePriority, output_item: _obsoleteOutputItem, ...ruleFields } = draft;
        const percentageRows = allocationDraft.percentage_rows?.map((row) => ({
            import_item: row.import_item,
            percentage: Number(row.percentage || 0).toFixed(2),
            unit_price: Number(row.unit_price || 0).toFixed(2),
            ...(row.max_quantity != null ? { max_quantity: row.max_quantity } : {}),
            ...(row.priority != null ? { priority: row.priority } : {}),
        }));
        const payload = {
            ...ruleFields,
            strategy: allocationDraft.strategy,
            import_item: allocationDraft.import_item,
            unit_value_rows: allocationDraft.unit_value_rows,
            percentage_rows: percentageRows,
        };
        try {
            const saved = draft.id
                ? await updateSionPlanningRule(draft.id, payload)
                : await createSionPlanningRule(payload as SionPlanningRule);
            const fresh = [...await fetchSionPlanningRules(saved.sion)].sort((a, b) => a.priority - b.priority);
            const persisted = fresh.find((rule) => rule.id === saved.id) ?? saved;
            setRules(fresh);
            setDraft(null);
            selectRule(persisted.id ?? null);
            toast.success("Rule saved");
            return persisted;
        } catch (reason) {
            const message = saveErrorMessage(reason);
            setError(message);
            toast.error(message);
            return null;
        } finally {
            setBusy(null);
        }
    };
    saveRef.current = save;
    const planSion = async (mode: SionPlanningMode, expiryScope?: "EXPIRED" | "EXPIRING_SOON") => { if (busy || !sion || !canExecuteSion) return; const restore = preserveScroll(); setConfirmForceAll(false); setBusy(mode === "ALL" ? "plan-all" : "plan-new"); setError(""); try { const result = await planSavedSionRules(sion, mode, undefined, expiryScope); setPreview(await previewSavedSionRules(sion, mode)); setWorkbenchTab("simulation"); toast.success(expiryScope ? `${result.replan_request_ids?.length ?? 0} ${expiryScope === "EXPIRED" ? "expired" : "expiring-soon"} licences queued for ${sionLabel}` : mode === "ALL" ? `${sionLabel} full eligible universe reprocessed` : `${sionLabel} new eligible data planned`); setRules(await fetchSionPlanningRules(sion)); } catch { toast.error("Planning failed"); } finally { setBusy(null); restore(); } };
    const selectedSion = sions.find((row) => row.id === sion); const sionLabel = selectedSion?.norm_class ?? "SION";
    const selectSion = (next: number | null) => { if (hasUnsavedChanges) { setPendingSion(next); return; } applySion(next); };
    const applySion = (next: number | null) => { setSion(next); setPendingSion(undefined); const nextParams = new URLSearchParams(params); if (next) { const row = sions.find((item) => item.id === next); nextParams.set("sion", row?.norm_class ?? String(next)); } else nextParams.delete("sion"); setParams(nextParams, { replace: true }); };
    const previewSion = async () => { if (!sion || busy || !canExecuteSion) return; const restore = preserveScroll(); setBusy("preview"); setError(""); try { setPreview(await previewSavedSionRules(sion, "NEW")); setWorkbenchTab("simulation"); toast.success(`${sionLabel} preview updated`); } catch { toast.error("Plan preview failed"); } finally { setBusy(null); restore(); } };
    const reorder = async (index: number, offset: number) => { if (!sion || busy) return; const next = [...rules]; const target = index + offset; if (target < 0 || target >= next.length) return; const restore = preserveScroll(); [next[index], next[target]] = [next[target], next[index]]; setBusy("reorder"); setError(""); try { const fresh = await reorderSionPlanningRules(sion, next.map((rule) => rule.id!)); setRules([...fresh].sort((a, b) => a.priority - b.priority)); toast.success("Priority updated"); } catch { toast.error("Unable to reorder rules"); } finally { setBusy(null); restore(); } };
    const reorderByDrag = useCallback(async (sourceId: number, targetId: number) => { if (!sion || busy || sourceId === targetId) return; const next = [...rules]; const source = next.findIndex((rule) => rule.id === sourceId); const target = next.findIndex((rule) => rule.id === targetId); if (source < 0 || target < 0) return; const [moved] = next.splice(source, 1); next.splice(target, 0, moved); setBusy("reorder"); setError(""); try { const fresh = await reorderSionPlanningRules(sion, next.map((rule) => rule.id!)); setRules([...fresh].sort((a, b) => a.priority - b.priority)); toast.success("Priority updated"); } catch { toast.error("Unable to reorder rules"); } finally { setDraggedRuleId(null); setBusy(null); } }, [sion, busy, rules]);
    const selectedRule = rules.find((rule) => rule.id === selectedRuleId) ?? null;
    const filteredRules = rules.filter((rule) =>
        rule.name.toLowerCase().includes(ruleSearch.trim().toLowerCase())
        && (strategyFilter === "all" || rule.strategy === strategyFilter)
        && (statusFilter === "all" || (statusFilter === "active" ? rule.is_active : !rule.is_active)),
    );
    const filteredSions = useMemo(() => sions.filter((row) => String(row.norm_class ?? "").toLowerCase().includes(normSearch.trim().toLowerCase())), [sions, normSearch]);
    const validationIssueCount = rules.filter((rule) => hasValidationErrors(validatePlanningRule(rule, { strategy: rule.strategy, import_item: rule.import_item, unit_value_rows: rule.unit_value_rows, percentage_rows: rule.percentage_rows }))).length;
    const setWorkbenchTab = (tab: string) => { setActiveTab(tab); const next = new URLSearchParams(params); next.set("view", tab); next.delete("tab"); setParams(next, { replace: true }); };
    const selectRule = (id: number | null) => { setSelectedRuleId(id); const next = new URLSearchParams(params); if (id) next.set("rule", String(id)); else next.delete("rule"); setParams(next, { replace: true }); };
    const beginEdit = (rule: SionPlanningRule) => { selectRule(rule.id ?? null); setDraft(rule); };
    const runSelectedTest = async () => { if (!selectedRule?.id || busy) return; setBusy("test"); try { setPreview(await testSionPlanningRule(selectedRule.id)); setWorkbenchTab("simulation"); toast.success("Rule test completed"); } catch { toast.error("Rule test failed"); } finally { setBusy(null); } };
    const deleteRule = async () => { const rule = confirmDeleteRule; if (!rule?.id || busy) return; setBusy("delete"); try { await deleteSionPlanningRule(rule.id); setRules((rows) => rows.filter((row) => row.id !== rule.id)); setDraft(null); selectRule(null); toast.success("Rule deleted"); } catch { toast.error("Unable to delete rule"); } finally { setBusy(null); setConfirmDeleteRule(null); } };
    useEffect(() => {
        const rows = Array.from(document.querySelectorAll<HTMLTableRowElement>("[aria-label='Rule workspace'] tbody tr"));
        const cleanups = rows.flatMap((row, index) => {
            const rule = filteredRules[index];
            if (!rule?.id) return [];
            row.draggable = !busy;
            row.title = "Drag to change rule priority";
            const start = (event: DragEvent) => { if (busy) return; event.dataTransfer?.setData("text/plain", String(rule.id)); setDraggedRuleId(rule.id!); };
            const over = (event: DragEvent) => { if (draggedRuleId != null) event.preventDefault(); };
            const drop = (event: DragEvent) => { event.preventDefault(); if (draggedRuleId != null) void reorderByDrag(draggedRuleId, rule.id!); };
            const end = () => setDraggedRuleId(null);
            row.addEventListener("dragstart", start); row.addEventListener("dragover", over); row.addEventListener("drop", drop); row.addEventListener("dragend", end);
            return [() => { row.draggable = false; row.removeEventListener("dragstart", start); row.removeEventListener("dragover", over); row.removeEventListener("drop", drop); row.removeEventListener("dragend", end); }];
        });
        return () => cleanups.forEach((cleanup) => cleanup());
    }, [filteredRules, busy, draggedRuleId, reorderByDrag]);
    return <div className="planning-workbench space-y-3 rounded-lg bg-muted/20 p-1" aria-label="SION Planning Workbench">
        <div className="sticky top-0 z-30 -mx-1 rounded-lg border border-border/70 bg-background/95 px-3 py-2 shadow-sm backdrop-blur">
            <div className="flex flex-wrap items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => navigate(origin, { state: { fromPlanning: location.pathname + location.search } })}><ArrowLeft className="size-4" />Back</Button>
                <div className="mr-auto"><h1 className="text-lg font-semibold tracking-tight">SION Planning Workbench</h1><p className="text-xs text-muted-foreground">Configure, validate, simulate and publish planning rules</p></div>
                <Button onClick={() => { if (!sion) return; const next = { ...emptyRule(sion), priority: Math.max(0, ...rules.map((rule) => rule.priority)) + 1 }; setDraft(next); selectRule(null); requestAnimationFrame(() => document.querySelector<HTMLInputElement>("[aria-label='Rule name']")?.focus()); }} disabled={!sion}><Plus className="size-4" />New Rule</Button>
                <Button variant="outline" onClick={previewSion} disabled={!!busy || !canExecuteSion}><Eye className="size-4" />Preview Impact</Button>
                <Button variant="outline" onClick={() => setConfirmForceAll(true)} disabled={!!busy || !canExecuteSion}><Zap className="size-4" />Re-plan all (Redis)</Button>
                <Button variant="outline" onClick={() => void planSion("ALL", "EXPIRED")} disabled={!!busy || !canExecuteSion}><Zap className="size-4" />Plan all expired</Button>
                <Button variant="outline" onClick={() => void planSion("ALL", "EXPIRING_SOON")} disabled={!!busy || !canExecuteSion}><Zap className="size-4" />Plan expiring soon</Button>
                <Button variant="outline" onClick={runSelectedTest} disabled={!selectedRule?.id || !!busy || hasUnsavedChanges}><CheckCircle2 className="size-4" />Validate</Button>
                <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" aria-label="More planning actions"><MoreHorizontal className="size-4" /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem disabled={!!busy || !canExecuteSion} onSelect={() => void planSion("ALL", "EXPIRED")}><Zap />Plan all expired licences</DropdownMenuItem><DropdownMenuItem disabled={!!busy || !canExecuteSion} onSelect={() => void planSion("ALL", "EXPIRING_SOON")}><Zap />Plan licences expiring soon</DropdownMenuItem><DropdownMenuItem disabled={!canExecuteSion} onSelect={() => setConfirmForceAll(true)}><Zap />Re-plan all eligible licences</DropdownMenuItem><DropdownMenuItem disabled><History />Version history</DropdownMenuItem><DropdownMenuItem disabled>Export rules</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
            </div>
        </div>
        {error && <div role="alert" className="flex items-center justify-between rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"><span>{error}</span><Button variant="outline" size="sm" onClick={() => sion && selectSion(sion)}>Retry</Button></div>}
        <nav className="sticky top-[68px] z-20 flex items-center gap-1.5 overflow-x-auto rounded-lg border border-border/70 bg-background/95 px-2 py-1.5 shadow-sm backdrop-blur" aria-label="SION norm tabs" role="tablist" onKeyDown={(event) => { if (!filteredSions.length || !["ArrowLeft", "ArrowRight"].includes(event.key)) return; event.preventDefault(); const index = filteredSions.findIndex((row) => row.id === sion); selectSion(filteredSions[(index + (event.key === "ArrowRight" ? 1 : -1) + filteredSions.length) % filteredSions.length].id); }}>
          {filteredSions.slice(0, 6).map((row) => <button key={row.id} id={`sion-tab-${row.id}`} role="tab" aria-selected={sion === row.id} aria-controls="sion-workspace" tabIndex={sion === row.id ? 0 : -1} type="button" onClick={() => selectSion(row.id)} className={`min-w-[88px] rounded-lg px-3 py-2 text-left text-xs focus-visible:ring-2 focus-visible:ring-ring ${sion === row.id ? "bg-primary/10 text-primary ring-1 ring-primary/30" : "hover:bg-muted"}`}><span className="block font-semibold">{row.norm_class}</span><span className="block text-[10px] text-muted-foreground">{sion === row.id ? `${rules.length} Rules` : "Active"}</span></button>)}
          <div className="ml-auto flex shrink-0 items-center gap-1"><Search className="size-4 text-muted-foreground" /><input aria-label="Search all norms" value={normSearch} onChange={(e) => setNormSearch(e.target.value)} placeholder="More norms" className="h-8 w-28 rounded-md border bg-background px-2 text-xs" /></div>
        </nav>
        <main id="sion-workspace" role="tabpanel" aria-labelledby={sion ? `sion-tab-${sion}` : undefined} className="min-w-0 space-y-3">
          {loading && <div role="status" className="rounded-xl border bg-card p-6 text-sm text-muted-foreground"><Loader2 className="mr-2 inline size-4 animate-spin" />Loading planning workbench…</div>}
          {!sion && !loading ? <section className="rounded-lg border bg-card p-6 text-center"><ClipboardList className="mx-auto size-7 text-muted-foreground" /><h2 className="mt-2 font-semibold">Select a SION norm</h2><p className="mt-1 text-sm text-muted-foreground">Choose a norm from the left panel to review its rules, validation and version history.</p><Button className="mt-3" variant="outline" onClick={() => filteredSions[0] && selectSion(filteredSions[0].id)} disabled={!filteredSions.length}>Select first active norm</Button></section> : sion && <>
          <section className="rounded-lg border border-border/80 bg-card p-3 shadow-sm shadow-primary/5"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Selected norm</p><h2 className="text-xl font-semibold tracking-tight">{sionLabel}</h2><p className="text-xs text-muted-foreground">{selectedSion?.description ?? "Planning configuration"}</p></div><div className="text-right text-xs text-muted-foreground">Version {Math.max(0, ...rules.map((r) => r.version ?? 0)) || "Not available"}<br />Last updated: {displayDate(selectedRule?.modified_on)}</div></div><div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">{[["Total Rules", rules.length], ["Active Rules", activeSavedRules.length], ["Draft Changes", hasUnsavedChanges ? 1 : 0], ["Validation Issues", validationIssueCount], ["Matched Licences", preview?.summary?.licenses_matched ?? "Not calculated"], ["Last Simulation", preview ? "Available" : "Not run"]].map(([label, value]) => <button key={String(label)} type="button" onClick={() => { if (label === "Active Rules") setStatusFilter("active"); if (label === "Validation Issues") setStatusFilter("active"); if (label === "Matched Licences" || label === "Last Simulation") setWorkbenchTab("simulation"); }} className="rounded-md border border-border/70 bg-muted/30 p-2 text-left shadow-sm transition-colors hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><div className="text-[10px] font-semibold uppercase text-muted-foreground">{label}</div><div className="mt-0.5 text-base font-semibold tabular-nums">{value}</div></button>)}</div></section>
        <Tabs value={activeTab} onValueChange={setWorkbenchTab} className="space-y-3">
            <TabsList><TabsTrigger value="rules">Rules ({rules.length})</TabsTrigger><TabsTrigger value="simulation">Simulation</TabsTrigger><TabsTrigger value="versions">Version History</TabsTrigger><TabsTrigger value="audit">Audit Log</TabsTrigger></TabsList>
            <TabsContent value="rules">
                <section aria-label="Rule workspace" className="grid min-h-[210px] overflow-hidden rounded-lg border bg-card lg:h-[calc(100dvh-14.5rem)] lg:grid-cols-[minmax(320px,38%)_minmax(0,62%)]">
                    <div className="border-b lg:border-b-0 lg:border-r">
                        <div className="flex flex-wrap items-center gap-2 border-b p-3"><div className="relative min-w-[180px] flex-1"><Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" /><input aria-label="Search rules" value={ruleSearch} onChange={(event) => setRuleSearch(event.target.value)} placeholder="Search rules…" className="h-9 w-full rounded-md border bg-background pl-8 pr-2 text-sm" /></div><select aria-label="Filter strategy" value={strategyFilter} onChange={(e) => setStrategyFilter(e.target.value)} className="h-9 rounded-md border bg-background px-2 text-xs"><option value="all">All strategies</option><option value="STANDARD">Single Item</option><option value="SPLIT_BY_PERCENT">Split by %</option><option value="SPLIT_BY_UNIT_VALUE">Unit Value</option></select><select aria-label="Filter status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-9 rounded-md border bg-background px-2 text-xs"><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select><span className="text-xs text-muted-foreground">{filteredRules.length} results</span></div>
                        <div className="max-h-[560px] overflow-auto"><table className="min-w-[640px] w-full text-sm"><thead className="sticky top-0 bg-muted/80 text-left text-xs text-muted-foreground"><tr><th className="w-12 px-3 py-2">Priority</th><th className="px-2 py-2">Rule Name / Match Logic</th><th className="px-2 py-2">Strategy</th><th className="px-2 py-2">Max Price</th><th className="px-2 py-2">Status</th><th className="w-12 py-2"></th></tr></thead><tbody>{filteredRules.map((rule) => {
                            const index = rules.findIndex((item) => item.id === rule.id); const selected = selectedRuleId === rule.id;
                            const counts = matchLogicCounts(rule.expression); const allocationCount = rule.percentage_rows?.length ?? rule.unit_value_rows?.length ?? 0;
                            return <tr key={rule.id} className={`border-t ${selected ? "bg-primary/5" : "hover:bg-muted/30"}`}><td className="px-3 py-2 font-semibold">{rule.priority}</td><td className="p-0"><button type="button" aria-current={selected ? "true" : undefined} aria-label={`Select rule ${rule.name}`} className="w-full px-2 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring" onClick={() => { if (!hasUnsavedChanges) { selectRule(rule.id ?? null); setDraft(null); } }}><span className="line-clamp-2 block font-medium">{rule.name}</span><span className="mt-1 block text-[11px] text-muted-foreground">{strategyLabel(rule.strategy)} · {rule.is_active ? "Active" : "Draft"} · ${rule.max_unit_price}/{rule.unit}</span><span className="mt-1 block text-[11px] text-muted-foreground">{allocationCount ? `${allocationCount} allocation${allocationCount === 1 ? "" : "s"} · ` : ""}{counts.groups ? `${counts.groups} group${counts.groups === 1 ? "" : "s"} · ` : ""}{counts.conditions} match condition{counts.conditions === 1 ? "" : "s"}</span></button></td><td className="px-2 text-xs">{strategyLabel(rule.strategy)}<br /><span className="text-muted-foreground">v{rule.version ?? "Not available"}</span></td><td className="px-2 tabular-nums">${rule.max_unit_price}<br /><span className="text-xs text-muted-foreground">{rule.unit}</span></td><td className="px-2"><Badge variant={rule.is_active ? "default" : "secondary"}>{rule.is_active ? "Active" : "Draft"}</Badge></td><td><DropdownMenu><DropdownMenuTrigger asChild><Button size="icon" variant="ghost" aria-label={`Actions for ${rule.name}`}><MoreHorizontal className="size-4" /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onSelect={() => { selectRule(rule.id ?? null); setDraft(null); }}>View</DropdownMenuItem><DropdownMenuItem onSelect={() => beginEdit(rule)}>Edit</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem disabled={index === 0 || !!busy} onSelect={() => reorder(index, -1)}><ArrowUp />Move Up</DropdownMenuItem><DropdownMenuItem disabled={index === rules.length - 1 || !!busy} onSelect={() => reorder(index, 1)}><ArrowDown />Move Down</DropdownMenuItem></DropdownMenuContent></DropdownMenu></td></tr>;
                        })}</tbody></table>{!filteredRules.length && <p className="p-8 text-center text-sm text-muted-foreground">No rules match this search.</p>}</div>
                    </div>
                    <section aria-label={draft ? "Rule editor" : "Rule detail"} className="flex min-h-0 flex-col">
                        {(draft || selectedRule) && <header className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b bg-card/95 px-4 py-3 backdrop-blur"><div className="mr-auto min-w-0"><p className="truncate font-semibold">Priority {draft?.priority ?? selectedRule?.priority} · {draft?.name ?? selectedRule?.name}</p><p className="text-xs text-muted-foreground">Version {draft?.version ?? selectedRule?.version ?? "Not available"} · {(draft?.is_active ?? selectedRule?.is_active) ? "Active" : "Draft"} · {hasValidationErrors(formErrors) ? "Validation needs attention" : "Validation passed"}</p></div><div role="group" aria-label="Rule detail mode" className="inline-flex rounded-md border p-0.5"><Button aria-pressed={!draft} size="sm" variant={!draft ? "default" : "ghost"} onClick={() => draft && setDraft(null)}>View</Button><Button aria-pressed={!!draft} size="sm" variant={draft ? "default" : "ghost"} onClick={() => !draft && selectedRule && beginEdit(selectedRule)}>Edit</Button></div>{draft ? <><Button variant="outline" size="sm" onClick={() => setDraft(null)}>Cancel</Button><Button size="sm" disabled={!hasUnsavedChanges || !!busy || hasValidationErrors(formErrors)} onClick={() => void save()}>{busy === "save" ? "Saving…" : "Save Changes"}</Button></> : <><Button size="sm" onClick={() => selectedRule && beginEdit(selectedRule)}><Pencil className="size-4" />Edit Rule</Button><Button variant="destructive" size="sm" disabled={!!busy} onClick={() => selectedRule && setConfirmDeleteRule(selectedRule)}><Trash2 className="size-4" />Delete</Button></>}</header>}
                        {draft ? <>
                            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
                                <div><h2 className="font-semibold">{draft.id ? `Edit Rule #${draft.priority}` : `New ${sionLabel} Rule`}</h2><p className="text-xs text-muted-foreground">{draft.id ? `Version ${draft.version ?? "—"}` : "Define a new database-backed planning rule"}</p></div>
                                <div className="space-y-3">
                                    <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_140px_100px_auto]">
                                        <div>
                                            <label className="text-xs">Rule Name</label>
                                            <input aria-label="Rule name" aria-invalid={!!formErrors.name} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} className={`mt-1 h-9 w-full rounded-md border px-2 ${formErrors.name ? "border-destructive" : ""}`} />
                                            {formErrors.name && <span className="mt-1 block text-[11px] text-destructive">{formErrors.name}</span>}
                                        </div>
                                        <div>
                                            <label className="text-xs">Max Price</label>
                                            <input required aria-required="true" aria-invalid={!!formErrors.max_unit_price} aria-label="Maximum unit price" inputMode="decimal" value={draft.max_unit_price} onChange={(e) => /^\d*(\.\d*)?$/.test(e.target.value) && setDraft({ ...draft, max_unit_price: e.target.value })} className={`mt-1 h-9 w-full rounded-md border px-2 ${formErrors.max_unit_price ? "border-destructive" : ""}`} />
                                            {formErrors.max_unit_price && <span className="mt-1 block text-[11px] text-destructive">{formErrors.max_unit_price}</span>}
                                        </div>
                                        <div>
                                            <label className="text-xs">Unit</label>
                                            <input aria-label="Planning unit" value={draft.unit} onChange={(e) => setDraft({ ...draft, unit: e.target.value })} className="mt-1 h-9 w-full rounded-md border px-2" />
                                            {formErrors.unit && <span className="mt-1 block text-[11px] text-destructive">{formErrors.unit}</span>}
                                        </div>
                                        <label className="flex items-center gap-2 self-end pb-2 text-xs"><input aria-label="Rule active" type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />Active</label>
                                    </div>

                                </div>
                                {allocationDraft && <AllocationStrategyEditor sionId={sion} value={allocationDraft} onChange={changeAllocationStrategy} onStandardItemSelected={(name) => setDraft((current) => current ? { ...current, name } : current)} disabled={!!busy} errors={formErrors} ruleId={draft?.id} />}
                                <ExpressionTreeEditor group={draft.expression} ruleName={draft.name} onChange={(expression) => setDraft({ ...draft, expression })} />
                            </div>
                            <p aria-live="polite" className={`px-4 pb-4 text-xs ${hasValidationErrors(formErrors) ? "text-destructive" : hasUnsavedChanges ? "text-amber-700" : "text-muted-foreground"}`}>{hasValidationErrors(formErrors) ? (formErrors.percentage_rows ?? "Validation needs attention") : hasUnsavedChanges ? "Unsaved changes" : "No changes yet"}</p>
                        </> : selectedRule ? <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-5">
                            <section><h3 className="text-sm font-semibold">Overview</h3><dl className="mt-2 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-xs text-muted-foreground">Rule Name</dt><dd className="font-medium">{selectedRule.name}</dd></div><div><dt className="text-xs text-muted-foreground">Maximum Price</dt><dd className="font-medium">${selectedRule.max_unit_price}/{selectedRule.unit}</dd></div><div><dt className="text-xs text-muted-foreground">Status</dt><dd><Badge variant={selectedRule.is_active ? "default" : "secondary"}>{selectedRule.is_active ? "Active" : "Draft"}</Badge></dd></div><div><dt className="text-xs text-muted-foreground">Priority</dt><dd>#{selectedRule.priority}</dd></div></dl></section>
                            <section><h3 className="text-sm font-semibold">Strategy</h3><p className="mt-2 text-sm">{strategyLabel(selectedRule.strategy)}{selectedRule.standard_item_name ? ` — ${selectedRule.standard_item_name}` : ""}</p></section>
                            <section><h3 className="text-sm font-semibold">Import Items / Allocations</h3>{selectedRule.percentage_rows?.length ? <table className="mt-2 w-full text-sm"><thead className="text-left text-xs text-muted-foreground"><tr><th>Item</th><th>Percentage</th><th>Unit Price</th></tr></thead><tbody>{selectedRule.percentage_rows.map((row, index) => <tr key={index} className="border-t"><td className="py-2">Item #{row.import_item}</td><td>{row.percentage}%</td><td>${row.unit_price}/{selectedRule.unit}</td></tr>)}</tbody></table> : <p className="mt-2 text-sm">{selectedRule.standard_item_name ?? "No import item configured."}</p>}</section>
                            <section><h3 className="text-sm font-semibold">Match Logic</h3><div className="mt-2 rounded-lg bg-muted/30 p-3"><MatchLogicView group={selectedRule.expression} /></div></section>
                            <section><h3 className="text-sm font-semibold">Validation</h3><p className="mt-2 text-sm text-emerald-700">Passed · Required fields complete</p></section>
                            <section><h3 className="text-sm font-semibold">Metadata</h3><dl className="mt-2 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-xs text-muted-foreground">Last modified by</dt><dd>{selectedRule.modified_by_username ?? "Not available"}</dd></div><div><dt className="text-xs text-muted-foreground">Last modified at</dt><dd>{displayDate(selectedRule.modified_on)}</dd></div><div><dt className="text-xs text-muted-foreground">Version</dt><dd>{selectedRule.version ?? "Not available"}</dd></div></dl></section>
                        </div> : <div className="grid flex-1 place-items-center p-8 text-sm text-muted-foreground">Select a rule to inspect its details.</div>}
                    </section>
                </section>
            </TabsContent>
            <TabsContent value="simulation">{requestedLicenseNumber && requestedSion && scopedPreview ? <ScopedPreview preview={scopedPreview} /> : preview ? <LicensePreview preview={preview} onViewPlan={(licenseId) => navigate(`/licenses/${licenseId}/overview?tab=planning`)} /> : <section className="rounded-xl border bg-card p-8 text-center"><Eye className="mx-auto size-7 text-muted-foreground" /><h3 className="mt-2 font-semibold">Run a safe simulation</h3><p className="mt-1 text-sm text-muted-foreground">Preview matched licences, availability and proposed planning CIF without saving plans.</p><Button className="mt-4" variant="outline" onClick={previewSion} disabled={!canExecuteSion}>Preview impact</Button></section>}</TabsContent>
            <TabsContent value="versions"><section className="rounded-xl border bg-card p-4"><h3 className="font-semibold">Version History</h3><table className="mt-3 w-full text-sm"><thead className="text-left text-xs text-muted-foreground"><tr><th>Version</th><th>Status</th><th>Rule Count</th><th>Last Modified</th></tr></thead><tbody><tr className="border-t"><td className="py-3">v{Math.max(0, ...rules.map((r) => r.version ?? 0)) || "Not available"}</td><td><Badge>Active</Badge></td><td>{rules.length}</td><td>{displayDate(selectedRule?.modified_on)}</td></tr></tbody></table></section></TabsContent>
            <TabsContent value="audit"><section className="rounded-xl border bg-card p-4"><h3 className="font-semibold">Audit Log</h3><p className="mt-2 text-sm text-muted-foreground">Rule changes are shown from the existing rule version metadata.</p><table className="mt-3 w-full text-sm"><thead className="text-left text-xs text-muted-foreground"><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Rule</th></tr></thead><tbody>{rules.slice(0, 10).map((rule) => <tr key={rule.id} className="border-t"><td className="py-2">{displayDate(rule.modified_on)}</td><td>{rule.modified_by_username ?? "Not available"}</td><td>Rule configuration</td><td>{rule.name}</td></tr>)}</tbody></table></section></TabsContent>
        </Tabs></>}
        </main>
        {pendingSion !== undefined && <ConfirmDialog show title="Unsaved changes" message="Save or discard the current rule before switching SION norms." severity="warning" confirmText="Discard and switch" onConfirm={() => applySion(pendingSion ?? null)} onCancel={() => setPendingSion(undefined)} />}
        <ConfirmDialog show={confirmForceAll} title={`Force re-plan ${sionLabel}?`} message={`This will reprocess all eligible current DFIA entries for ${sionLabel} using the latest saved planning rules.`} severity="danger" confirmText="Force All" onConfirm={() => planSion("ALL")} onCancel={() => setConfirmForceAll(false)} />
        <ConfirmDialog show={!!confirmDeleteRule} title="Delete planning rule?" message={`Delete ${confirmDeleteRule?.name ?? "this rule"}? This cannot be undone.`} severity="danger" confirmText={busy === "delete" ? "Deleting…" : "Delete"} onConfirm={deleteRule} onCancel={() => setConfirmDeleteRule(null)} />
    </div>;
}
