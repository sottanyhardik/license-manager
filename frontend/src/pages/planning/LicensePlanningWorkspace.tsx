import { Fragment, useCallback, useContext, useEffect, useMemo, useRef, useState, type ComponentProps, type ReactNode } from "react";
import { ArrowDown, ArrowLeft, ArrowUp, ChevronDown, ChevronRight, Eye, MoreHorizontal, Pencil, Plus, Search, Zap, CheckCircle2, ClipboardList, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { AuthContext } from "@/context/AuthContext";
import { ROLES } from "@/routes/authorizationRoles";
import ActiveFilters, { type ActiveFilterItem } from "@/components/ActiveFilters";
import { Button as UiButton } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { WorkspaceToolbar, WorkspaceTitle } from "@/components/workspace/WorkspaceToolbar";
import { DetailTabs, type DetailTab } from "@/components/workspace/DetailTabs";
import { ActionMenu, EmptyState, InlineError, LoadingState } from "@/components/shared";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { createSionPlanningRule, deleteSionPlanningRule, fetchSionPlanningRules, planSavedSionRules, previewSavedSionRules, reorderSionPlanningRules, testSionPlanningRule, updateSionPlanningRule, previewScopedSionPlan, fetchSionNormSummaries, fetchSionNormConfiguration, type SionNormSummary, type SionNormConfiguration, type RuleAllocationStrategy, type SionPlanningMode, type SionPlanningPreview, type SionPlanningPreviewLicense, type SionPlanningRule, type ScopedPlanPreview } from "@/api/planningRuleApi";
import { SplitAllocationPreview } from "./SplitAllocationPreview";
import { EntitlementPlanningReport } from "./EntitlementPlanningReport";
import { AllocationStrategyEditor } from "./AllocationStrategyEditor";
import { validatePlanningRule, hasValidationErrors, type RuleFormErrors } from "./ruleFormValidation";
import { ExpressionTreeEditor } from "./ExpressionTreeEditor";
import { emptyRuleCondition } from "./expressionTreeUtils";
import { displayDate, normalizeTab, TAB_LABELS, validateNormConfiguration, visibleNormTabs, type NormTabId } from "./workspace/normConfig";
import { OverviewTab, ProductMappingTab, RegistryRulesPanel, SplitConfigurationTab, ValidationTab, VersionHistoryTab } from "./workspace/NormTabs";
import { SionNormRow } from "./workspace/SionNormRow";

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
            <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[720px] text-xs"><thead><tr className="border-b border-border/70 text-left"><th className="p-2">License</th><th>SION</th><th>Matched Items</th><th>Rules</th><th>Existing Plan</th><th>Proposed Plan</th><th>Change</th><th>Shortage</th><th>Status</th><th>Actions</th></tr></thead><tbody>{licenses.map((license) => {
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
        <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[720px] text-xs"><thead><tr className="border-b border-border/70 text-left"><th className="p-2">Input</th><th>Priority</th><th>Target</th><th>Actual Qty/CIF</th><th>Excess Qty/CIF</th><th>New Qty/CIF</th><th>Final Qty/CIF</th><th>Closing CIF</th><th>Status</th></tr></thead><tbody>{preview.lines.map((line, i) => <tr key={`${line.licence_item}-${line.SION_input}-${i}`} className="border-b"><td className="p-2">{line.SION_input}</td><td>{line.priority}.{line.priority_sequence}</td><td>{line.percentage_target_quantity}</td><td>{line.actual_debited_quantity} / {line.actual_debited_cif}</td><td>{line.excess_debited_quantity} / {line.excess_debited_cif}</td><td>{line.new_planned_quantity} / {line.new_planned_cif}</td><td>{line.final_accounted_quantity} / {line.final_accounted_cif}</td><td>{line.closing_balance_cif}</td><td>{line.priority_status}</td></tr>)}</tbody></table></div>
        <p className="mt-2 text-sm">New planned CIF: {preview.grand_totals.new_planned_cif} · Remaining CIF: {preview.grand_totals.remaining_cif} · Reconciliation difference: {preview.grand_totals.reconciliation_difference}</p>
    </section>;
}

function strategyLabel(strategy?: RuleAllocationStrategy["strategy"]) {
    return ({ STANDARD: "Single Item", SPLIT_BY_PERCENT: "Split by %", SPLIT_BY_UNIT_VALUE: "Split by Unit Value" } as Record<string, string>)[strategy ?? "STANDARD"];
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
    const { hasRole, isSuperAdmin } = useContext(AuthContext);
    // UI hint only; LicensePermission on the API stays authoritative for every write.
    const canWrite = isSuperAdmin() || hasRole(ROLES.LICENSE_MANAGER);
    const origin = params.get("origin") || "/licenses";
    const [norms, setNorms] = useState<SionNormSummary[]>([]); const [normsError, setNormsError] = useState(""); const [normsLoading, setNormsLoading] = useState(true);
    const [sion, setSion] = useState<number | null>(null); const [rules, setRules] = useState<SionPlanningRule[]>([]); const [draft, setDraft] = useState<SionPlanningRule | null>(null); const [selectedRuleId, setSelectedRuleId] = useState<number | null>(Number(params.get("rule")) || null); const [activeTab, setActiveTab] = useState<NormTabId>(normalizeTab(params.get("view") || params.get("tab"))); const [ruleSearch, setRuleSearch] = useState(""); const [normSearch, setNormSearch] = useState(params.get("q") ?? ""); const [normStatusFilter, setNormStatusFilter] = useState(params.get("status") ?? "all"); const [configFilter, setConfigFilter] = useState(params.get("config") ?? "all"); const [strategyFilter, setStrategyFilter] = useState("all"); const [statusFilter, setStatusFilter] = useState("all"); const [pendingSion, setPendingSion] = useState<number | null | undefined>(undefined); const [confirmForceAll, setConfirmForceAll] = useState(false); const [confirmDeleteRule, setConfirmDeleteRule] = useState<SionPlanningRule | null>(null); const [busy, setBusy] = useState<"save" | "test" | "preview" | "plan-new" | "plan-all" | "deactivate" | "reorder" | "delete" | null>(null); const [preview, setPreview] = useState<SionPlanningPreview | null>(null); const [error, setError] = useState(""); const [loading, setLoading] = useState(false); const [draggedRuleId, setDraggedRuleId] = useState<number | null>(null);
    const [config, setConfig] = useState<SionNormConfiguration | null>(null);
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
    const loadNorms = useCallback(() => { setNormsLoading(true); setNormsError(""); return fetchSionNormSummaries().then(setNorms).catch(() => setNormsError("Unable to load SION norms.")).finally(() => setNormsLoading(false)); }, []);
    const loadConfig = useCallback((id: number) => fetchSionNormConfiguration(id).then(setConfig).catch(() => setConfig(null)), []);
    // Fetch the norm list once; the request has no dependency on the URL.
    useEffect(() => { void loadNorms(); }, [loadNorms]);
    useEffect(() => { if (!requestedLicenseNumber || !requestedSion) return; setLoading(true); previewScopedSionPlan(requestedLicenseNumber, requestedSion).then(setScopedPreview).catch((e) => setError(e?.response?.data?.error || "Unable to preview the exact licence/SION selection.")).finally(() => setLoading(false)); }, [requestedLicenseNumber, requestedSion]);
    useEffect(() => { if (!sion) { setRules([]); setDraft(null); setSelectedRuleId(null); setPreview(null); setConfig(null); return; } setLoading(true); setError(""); setDraft(null); setPreview(null); setConfig(null); void loadConfig(sion); fetchSionPlanningRules(sion).then((rows) => { const ordered = [...rows].sort((a, b) => a.priority - b.priority); setRules(ordered); setSelectedRuleId((current) => ordered.some((rule) => rule.id === current) ? current : ordered[0]?.id ?? null); }).catch(() => setError("Unable to load planning rules.")).finally(() => setLoading(false)); }, [sion, loadConfig]);
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

    // The URL (?sion=) is the source of truth for the expanded norm, so refresh
    // and browser back/forward reopen / close the same row.
    useEffect(() => {
        if (normsLoading) return;
        const match = requestedSion ? norms.find((row) => String(row.id) === requestedSion || row.norm_class.toUpperCase() === requestedSion.toUpperCase()) : undefined;
        const target = match?.id ?? null;
        if (target === sion) return;
        if (hasUnsavedChanges) setPendingSion(target); else setSion(target);
        // eslint-disable-next-line react-hooks/exhaustive-deps -- react to URL/list changes only, never to local edits
    }, [norms, normsLoading, requestedSion]);

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
    const refreshAfterWrite = (id: number) => { void loadNorms(); void loadConfig(id); };
    const save = async () => {
        if (!draft || !allocationDraft || !hasUnsavedChanges) return null;
        setBusy("save");
        setError("");
        const { priority: _databasePriority, output_item: _obsoleteOutputItem, stable_key: _readOnlyStableKey, ...ruleFields } = draft;
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
            refreshAfterWrite(saved.sion);
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
    const planSion = async (mode: SionPlanningMode, expiryScope?: "EXPIRED" | "EXPIRING_SOON") => { if (busy || !sion || !canExecuteSion) return; const restore = preserveScroll(); setConfirmForceAll(false); setBusy(mode === "ALL" ? "plan-all" : "plan-new"); setError(""); try { const result = expiryScope ? await planSavedSionRules(sion, mode, undefined, expiryScope) : await planSavedSionRules(sion, mode); setPreview(await previewSavedSionRules(sion, mode)); setWorkbenchTab("simulation"); toast.success(expiryScope ? `${result.replan_request_ids?.length ?? 0} ${expiryScope === "EXPIRED" ? "expired" : "expiring-soon"} licences queued for ${sionLabel}` : mode === "ALL" ? `${sionLabel} full eligible universe reprocessed` : `${sionLabel} new eligible data planned`); setRules(await fetchSionPlanningRules(sion)); } catch { toast.error("Planning failed"); } finally { setBusy(null); restore(); } };
    const selectedSion = norms.find((row) => row.id === sion); const sionLabel = selectedSion?.norm_class ?? "SION";
    const setUrl = (mutate: (next: URLSearchParams) => void, mode: "push" | "replace" = "replace") => { const next = new URLSearchParams(params); mutate(next); if (next.toString() !== params.toString()) setParams(next, { replace: mode === "replace" }); };
    const selectSion = (next: number | null) => { if (hasUnsavedChanges) { setPendingSion(next); return; } applySion(next); };
    // Expand / collapse pushes a history entry (back/forward walks open/closed norms, like the Licence register).
    const applySion = (next: number | null) => { setSion(next); setPendingSion(undefined); setUrl((p) => { if (next) { const row = norms.find((item) => item.id === next); p.set("sion", row?.norm_class ?? String(next)); } else p.delete("sion"); p.delete("rule"); }, "push"); };
    const cancelPendingSion = () => { setPendingSion(undefined); setUrl((p) => { if (sion) p.set("sion", selectedSion?.norm_class ?? String(sion)); else p.delete("sion"); }); };
    const toggleNorm = (id: number) => selectSion(sion === id ? null : id);
    const previewSion = async () => { if (!sion || busy || !canExecuteSion) return; const restore = preserveScroll(); setBusy("preview"); setError(""); try { setPreview(await previewSavedSionRules(sion, "NEW")); setWorkbenchTab("simulation"); toast.success(`${sionLabel} preview updated`); } catch { toast.error("Plan preview failed"); } finally { setBusy(null); restore(); } };
    const reorder = async (index: number, offset: number) => { if (!sion || busy || !canWrite) return; const next = [...rules]; const target = index + offset; if (target < 0 || target >= next.length) return; const restore = preserveScroll(); [next[index], next[target]] = [next[target], next[index]]; setBusy("reorder"); setError(""); try { const fresh = await reorderSionPlanningRules(sion, next.map((rule) => rule.id!)); setRules([...fresh].sort((a, b) => a.priority - b.priority)); toast.success("Priority updated"); } catch { toast.error("Unable to reorder rules"); } finally { setBusy(null); restore(); } };
    const reorderByDrag = useCallback(async (sourceId: number, targetId: number) => { if (!sion || busy || !canWrite || sourceId === targetId) return; const next = [...rules]; const source = next.findIndex((rule) => rule.id === sourceId); const target = next.findIndex((rule) => rule.id === targetId); if (source < 0 || target < 0) return; const [moved] = next.splice(source, 1); next.splice(target, 0, moved); setBusy("reorder"); setError(""); try { const fresh = await reorderSionPlanningRules(sion, next.map((rule) => rule.id!)); setRules([...fresh].sort((a, b) => a.priority - b.priority)); toast.success("Priority updated"); } catch { toast.error("Unable to reorder rules"); } finally { setDraggedRuleId(null); setBusy(null); } }, [sion, busy, rules, canWrite]);
    const selectedRule = rules.find((rule) => rule.id === selectedRuleId) ?? null;
    const filteredRules = rules.filter((rule) =>
        rule.name.toLowerCase().includes(ruleSearch.trim().toLowerCase())
        && (strategyFilter === "all" || rule.strategy === strategyFilter)
        && (statusFilter === "all" || (statusFilter === "active" ? rule.is_active : !rule.is_active)),
    );
    const filteredNorms = useMemo(() => {
        const q = normSearch.trim().toLowerCase();
        return norms.filter((row) =>
            (!q || row.norm_class.toLowerCase().includes(q) || String(row.description ?? "").toLowerCase().includes(q))
            && (normStatusFilter === "all" || (normStatusFilter === "active" ? row.is_active : !row.is_active))
            && (configFilter === "all"
                || (configFilter === "rules" && (row.active_rule_count > 0 || row.registry_rule_count > 0))
                || (configFilter === "split" && (row.split_rule_count > 0 || row.registry_split_count > 0))
                || (configFilter === "unconfigured" && !row.active_rule_count && !row.registry_rule_count)),
        );
    }, [norms, normSearch, normStatusFilter, configFilter]);
    const issues = useMemo(() => validateNormConfiguration(rules, config), [rules, config]);
    const hasSimulation = !!preview || !!(requestedLicenseNumber && requestedSion);
    const tabIds = visibleNormTabs({ rules, config, summary: selectedSion, hasSimulation });
    const setWorkbenchTab = (tab: NormTabId) => { setActiveTab(tab); setUrl((p) => { p.set("view", tab); p.delete("tab"); }); };
    const updateNormFilter = (key: "q" | "status" | "config", value: string, setter: (v: string) => void) => { setter(value); setUrl((p) => { if (!value || value === "all") p.delete(key); else p.set(key, value); }); };
    const selectRule = (id: number | null) => { setSelectedRuleId(id); setUrl((p) => { if (id) p.set("rule", String(id)); else p.delete("rule"); }); };
    const beginEdit = (rule: SionPlanningRule) => { if (!canWrite) return; selectRule(rule.id ?? null); setDraft(rule); };
    const startNewRule = () => { if (!sion || !canWrite) return; const next = { ...emptyRule(sion), priority: Math.max(0, ...rules.map((rule) => rule.priority)) + 1 }; setWorkbenchTab("rules"); setDraft(next); selectRule(null); requestAnimationFrame(() => document.querySelector<HTMLInputElement>("[aria-label='Rule name']")?.focus()); };
    const runSelectedTest = async () => { if (!selectedRule?.id || busy) return; setBusy("test"); try { setPreview(await testSionPlanningRule(selectedRule.id)); setWorkbenchTab("simulation"); toast.success("Rule test completed"); } catch { toast.error("Rule test failed"); } finally { setBusy(null); } };
    const retireRule = async () => { const rule = confirmDeleteRule; if (!rule?.id || busy) return; setBusy("delete"); try { await deleteSionPlanningRule(rule.id); setRules((rows) => rows.filter((row) => row.id !== rule.id)); setDraft(null); selectRule(null); refreshAfterWrite(rule.sion); toast.success("Rule deleted"); } catch { toast.error("Unable to delete rule"); } finally { setBusy(null); setConfirmDeleteRule(null); } };
    useEffect(() => {
        const rows = Array.from(document.querySelectorAll<HTMLTableRowElement>("[aria-label='Rule workspace'] tbody tr"));
        const cleanups = rows.flatMap((row, index) => {
            const rule = filteredRules[index];
            if (!rule?.id || !canWrite) return [];
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
    }, [filteredRules, busy, draggedRuleId, reorderByDrag, canWrite]);

    const selectedRuleErrors = selectedRule ? validatePlanningRule(selectedRule, { strategy: selectedRule.strategy, import_item: selectedRule.import_item, unit_value_rows: selectedRule.unit_value_rows, percentage_rows: selectedRule.percentage_rows }) : {};
    const rulesTab = <div className="space-y-3">
        <section aria-label="Rule workspace" className="grid min-h-[210px] overflow-hidden rounded-lg border border-border/70 bg-card lg:h-[min(640px,calc(100dvh-16rem))] lg:grid-cols-[minmax(320px,38%)_minmax(0,62%)]">
            <div className="flex min-h-0 flex-col border-b lg:border-b-0 lg:border-r">
                <div className="flex items-center gap-2 border-b px-3 py-2">
                    <div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" /><input aria-label="Search rules" value={ruleSearch} onChange={(event) => setRuleSearch(event.target.value)} placeholder="Search rules…" className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" /></div>
                    <span className="shrink-0 text-xs text-muted-foreground">{filteredRules.length} of {rules.length} rules</span>
                </div>
                <LicensePlanningWorkspaceActiveFiltersDisplay
                    ruleSearch={ruleSearch}
                    strategyFilter={strategyFilter}
                    statusFilter={statusFilter}
                    onRemoveFilter={(key) => {
                        if (key === 'ruleSearch') setRuleSearch("");
                        if (key === 'strategyFilter') setStrategyFilter("all");
                        if (key === 'statusFilter') setStatusFilter("all");
                    }}
                    onClearAll={() => {
                        setRuleSearch("");
                        setStrategyFilter("all");
                        setStatusFilter("all");
                    }}
                />
                <div className="min-h-0 flex-1 overflow-auto"><table className="min-w-[640px] w-full text-sm"><thead className="sticky top-0 bg-muted/80 text-left text-xs text-muted-foreground"><tr><th className="w-12 px-3 py-2">Priority</th><th className="px-2 py-2">Rule Name / Match Logic</th><th className="px-2 py-2">Strategy</th><th className="px-2 py-2">Max Price</th><th className="px-2 py-2">Status</th><th className="w-12 py-2"></th></tr></thead><tbody>{filteredRules.map((rule) => {
                    const index = rules.findIndex((item) => item.id === rule.id); const selected = selectedRuleId === rule.id;
                    const counts = matchLogicCounts(rule.expression); const allocationCount = rule.percentage_rows?.length ?? rule.unit_value_rows?.length ?? 0;
                    return <tr key={rule.id} className={`border-t ${selected ? "bg-primary/5" : "hover:bg-muted/30"}`}><td className="px-3 py-2 font-semibold">{rule.priority}</td><td className="p-0"><button type="button" aria-current={selected ? "true" : undefined} aria-label={`Select rule ${rule.name}`} className="w-full px-2 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring" onClick={() => { if (!hasUnsavedChanges) { selectRule(rule.id ?? null); setDraft(null); } }}><span className="line-clamp-2 block font-medium">{rule.name}</span>{rule.stable_key && <span className="mt-0.5 block font-mono text-[10px] text-muted-foreground">{rule.stable_key}</span>}<span className="mt-1 block text-[11px] text-muted-foreground">{strategyLabel(rule.strategy)} · {rule.is_active ? "Active" : "Draft"} · ${rule.max_unit_price}/{rule.unit}</span><span className="mt-1 block text-[11px] text-muted-foreground">{allocationCount ? `${allocationCount} allocation${allocationCount === 1 ? "" : "s"} · ` : ""}{counts.groups ? `${counts.groups} group${counts.groups === 1 ? "" : "s"} · ` : ""}{counts.conditions} match condition{counts.conditions === 1 ? "" : "s"}</span></button></td><td className="px-2 text-xs">{strategyLabel(rule.strategy)}<br /><span className="text-muted-foreground">v{rule.version ?? "Not available"}</span></td><td className="px-2 tabular-nums">${rule.max_unit_price}<br /><span className="text-xs text-muted-foreground">{rule.unit}</span></td><td className="px-2"><Badge variant={rule.is_active ? "default" : "secondary"}>{rule.is_active ? "Active" : "Draft"}</Badge></td><td><DropdownMenu><DropdownMenuTrigger asChild><Button size="icon" variant="ghost" aria-label={`Actions for ${rule.name}`}><MoreHorizontal className="size-4" /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onSelect={() => { selectRule(rule.id ?? null); setDraft(null); }}>View</DropdownMenuItem>{canWrite && <><DropdownMenuItem onSelect={() => beginEdit(rule)}>Edit</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem disabled={index === 0 || !!busy} onSelect={() => reorder(index, -1)}><ArrowUp />Move Up</DropdownMenuItem><DropdownMenuItem disabled={index === rules.length - 1 || !!busy} onSelect={() => reorder(index, 1)}><ArrowDown />Move Down</DropdownMenuItem></>}</DropdownMenuContent></DropdownMenu></td></tr>;
                })}</tbody></table>{!filteredRules.length && <p className="p-8 text-center text-sm text-muted-foreground">No rules match this search.</p>}</div>
            </div>
            <section aria-label={draft ? "Rule editor" : "Rule detail"} className="flex min-h-0 flex-col">
                {(draft || selectedRule) && <header className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b bg-card/95 px-4 py-3 backdrop-blur"><div className="mr-auto min-w-0"><p className="truncate font-semibold">Priority {draft?.priority ?? selectedRule?.priority} · {draft?.name ?? selectedRule?.name}</p><p className="text-xs text-muted-foreground">Version {draft?.version ?? selectedRule?.version ?? "Not available"} · {(draft?.is_active ?? selectedRule?.is_active) ? "Active" : "Draft"} · {hasValidationErrors(draft ? formErrors : selectedRuleErrors) ? "Validation needs attention" : "Validation passed"}</p></div>{canWrite && <div role="group" aria-label="Rule detail mode" className="inline-flex rounded-md border p-0.5"><Button aria-pressed={!draft} size="sm" variant={!draft ? "default" : "ghost"} onClick={() => draft && setDraft(null)}>View</Button><Button aria-pressed={!!draft} size="sm" variant={draft ? "default" : "ghost"} onClick={() => !draft && selectedRule && beginEdit(selectedRule)}>Edit</Button></div>}{draft ? <><Button variant="outline" size="sm" onClick={() => setDraft(null)}>Cancel</Button><Button size="sm" disabled={!hasUnsavedChanges || !!busy || hasValidationErrors(formErrors)} onClick={() => void save()}>{busy === "save" ? "Saving…" : "Save Changes"}</Button></> : canWrite ? <><Button size="sm" onClick={() => selectedRule && beginEdit(selectedRule)}><Pencil className="size-4" />Edit Rule</Button><Button variant="destructive" size="sm" disabled={!!busy} onClick={() => selectedRule && setConfirmDeleteRule(selectedRule)}><Trash2 className="size-4" />Delete</Button></> : null}</header>}
                {draft ? <>
                    <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
                        <div><h2 className="font-semibold">{draft.id ? `Edit Rule #${draft.priority}` : `New ${sionLabel} Rule`}</h2><p className="text-xs text-muted-foreground">{draft.id ? `Version ${draft.version ?? "—"}` : "Define a new database-backed planning rule"}</p></div>
                        <div className="space-y-3">
                            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_140px_100px_120px_auto]">
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
                                <div>
                                    <label className="text-xs">CIF Restriction</label>
                                    <select
                                        aria-label="CIF restriction percentage"
                                        value={draft.cif_restriction_percentage ?? ""}
                                        onChange={(e) => setDraft({ ...draft, cif_restriction_percentage: e.target.value ? Number(e.target.value) : null })}
                                        className="mt-1 h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
                                    >
                                        <option value="">No restriction</option>
                                        <option value="2">2%</option>
                                        <option value="3">3%</option>
                                        <option value="5">5%</option>
                                        <option value="10">10%</option>
                                    </select>
                                    <p className="mt-1 text-[10px] text-muted-foreground">Skip planning if debited + allotted CIF exceeds this % of item total CIF</p>
                                </div>
                                <label className="flex items-center gap-2 self-end pb-2 text-xs"><input aria-label="Rule active" type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />Active</label>
                            </div>

                        </div>
                        {allocationDraft && <AllocationStrategyEditor sionId={sion} value={allocationDraft} onChange={changeAllocationStrategy} onStandardItemSelected={(name) => setDraft((current) => current ? { ...current, name } : current)} disabled={!!busy} errors={formErrors} ruleId={draft?.id} />}
                        <ExpressionTreeEditor group={draft.expression} ruleName={draft.name} onChange={(expression) => setDraft({ ...draft, expression })} />
                    </div>
                    <p aria-live="polite" className={`px-4 pb-4 text-xs ${hasValidationErrors(formErrors) ? "text-destructive" : hasUnsavedChanges ? "text-amber-700" : "text-muted-foreground"}`}>{hasValidationErrors(formErrors) ? (formErrors.percentage_rows ?? "Validation needs attention") : hasUnsavedChanges ? "Unsaved changes" : "No changes yet"}</p>
                </> : selectedRule ? <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-5">
                    <section><h3 className="text-sm font-semibold">Overview</h3><dl className="mt-2 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-xs text-muted-foreground">Rule Name</dt><dd className="font-medium">{selectedRule.name}</dd></div><div><dt className="text-xs text-muted-foreground">Maximum Price</dt><dd className="font-medium">${selectedRule.max_unit_price}/{selectedRule.unit}</dd></div><div><dt className="text-xs text-muted-foreground">Status</dt><dd><Badge variant={selectedRule.is_active ? "default" : "secondary"}>{selectedRule.is_active ? "Active" : "Draft"}</Badge></dd></div><div><dt className="text-xs text-muted-foreground">Priority</dt><dd>#{selectedRule.priority}</dd></div><div className="col-span-2"><dt className="text-xs text-muted-foreground">Stable identifier</dt><dd className="font-mono text-xs">{selectedRule.stable_key ?? "Not assigned"}</dd></div></dl></section>
                    <section><h3 className="text-sm font-semibold">Strategy</h3><p className="mt-2 text-sm">{strategyLabel(selectedRule.strategy)}{selectedRule.standard_item_name ? ` — ${selectedRule.standard_item_name}` : ""}</p></section>
                    <section><h3 className="text-sm font-semibold">Import Items / Allocations</h3>{selectedRule.percentage_rows?.length ? <table className="mt-2 w-full text-sm"><thead className="text-left text-xs text-muted-foreground"><tr><th>Item</th><th>Percentage</th><th>Unit Price</th></tr></thead><tbody>{selectedRule.percentage_rows.map((row, index) => <tr key={index} className="border-t"><td className="py-2">Item #{row.import_item}</td><td>{row.percentage}%</td><td>${row.unit_price}/{selectedRule.unit}</td></tr>)}</tbody></table> : <p className="mt-2 text-sm">{selectedRule.standard_item_name ?? "No import item configured."}</p>}</section>
                    <section><h3 className="text-sm font-semibold">Match Logic</h3><div className="mt-2 rounded-lg bg-muted/30 p-3"><MatchLogicView group={selectedRule.expression} /></div></section>
                    <section><h3 className="text-sm font-semibold">Validation</h3>{hasValidationErrors(selectedRuleErrors) ? <p className="mt-2 text-sm text-destructive">Needs attention · {Object.values(selectedRuleErrors).filter((v) => typeof v === "string").join(" ")}</p> : <p className="mt-2 text-sm text-emerald-700">Passed · Required fields complete</p>}</section>
                    <section><h3 className="text-sm font-semibold">Metadata</h3><dl className="mt-2 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-xs text-muted-foreground">Last modified by</dt><dd>{selectedRule.modified_by_username ?? "Not available"}</dd></div><div><dt className="text-xs text-muted-foreground">Last modified at</dt><dd>{displayDate(selectedRule.modified_on)}</dd></div><div><dt className="text-xs text-muted-foreground">Version</dt><dd>{selectedRule.version ?? "Not available"}</dd></div></dl></section>
                </div> : <div className="grid flex-1 place-items-center p-8 text-sm text-muted-foreground">{rules.length ? "Select a rule to inspect its details." : canWrite ? "No database rules yet. Use New Rule to add one." : "No database rules configured."}</div>}
            </section>
        </section>
        <RegistryRulesPanel config={config} />
    </div>;

    const simulationTab = <div className="space-y-4">{requestedLicenseNumber && requestedSion && <EntitlementPlanningReport licenseNumber={requestedLicenseNumber} sion={requestedSion} />}{requestedLicenseNumber && requestedSion && scopedPreview ? <ScopedPreview preview={scopedPreview} /> : preview ? <LicensePreview preview={preview} onViewPlan={(licenseId) => navigate(`/licenses/${licenseId}/overview?tab=planning`)} /> : <section className="rounded-lg border border-border/70 bg-card p-8 text-center"><Eye className="mx-auto size-7 text-muted-foreground" /><h3 className="mt-2 font-semibold">Run a safe simulation</h3><p className="mt-1 text-sm text-muted-foreground">Preview matched licences, availability and proposed planning CIF without saving plans.</p><Button className="mt-4" variant="outline" onClick={previewSion} disabled={!canExecuteSion}>Preview impact</Button></section>}</div>;

    const renderTab: Record<NormTabId, () => ReactNode> = {
        overview: () => <OverviewTab summary={selectedSion} rules={rules} config={config} issues={issues} onOpenTab={setWorkbenchTab} />,
        rules: () => rulesTab,
        split: () => <SplitConfigurationTab rules={rules} config={config} />,
        mapping: () => <ProductMappingTab rules={rules} config={config} canWrite={canWrite} onEditRule={(id) => { const rule = rules.find((r) => r.id === id); if (rule) { setWorkbenchTab("rules"); beginEdit(rule); } }} />,
        validation: () => <ValidationTab issues={issues} selectedRuleName={selectedRule?.name} onRunTest={() => void runSelectedTest()} canRunTest={!!selectedRule?.id && !hasUnsavedChanges} busy={!!busy} />,
        history: () => <VersionHistoryTab config={config} />,
        simulation: () => simulationTab,
    };
    const errorCount = issues.filter((i) => i.severity === "error").length;
    const tabs: DetailTab[] = tabIds.map((id) => ({ id, label: id === "rules" ? `Rules (${rules.length})` : id === "validation" && errorCount ? `Validation (${errorCount})` : TAB_LABELS[id], render: renderTab[id] }));
    const lastUpdated = [...rules.map((r) => r.modified_on), selectedSion?.last_updated].filter(Boolean).sort().pop();
    const version = Math.max(0, ...rules.map((r) => r.version ?? 0)) || selectedSion?.profile_version;

    return <div className="planning-workbench min-w-0 space-y-3" aria-label="SION Planning Workbench">
        <div className="sticky top-0 z-30">
            <WorkspaceToolbar
                className="rounded-lg border border-border/70 bg-card/95 shadow-sm backdrop-blur"
                start={<WorkspaceTitle title="Planning" breadcrumbs={[{ label: "Home", to: "/" }]} count={normsLoading ? undefined : filteredNorms.length} countNoun="SION norm" />}
                search={<div className="relative"><Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden="true" /><input aria-label="Search SION norms" value={normSearch} onChange={(event) => updateNormFilter("q", event.target.value, setNormSearch)} placeholder="Search norms…" className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-sm" /></div>}
                filters={<>
                    <label className="space-y-1 text-xs font-medium">Norm status<select aria-label="Filter norm status" value={normStatusFilter} onChange={(e) => updateNormFilter("status", e.target.value, setNormStatusFilter)} className="mt-1 h-8 w-full rounded-md border border-input bg-background px-2 text-xs font-normal"><option value="all">All norms</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
                    <label className="space-y-1 text-xs font-medium">Configuration<select aria-label="Filter configuration" value={configFilter} onChange={(e) => updateNormFilter("config", e.target.value, setConfigFilter)} className="mt-1 h-8 w-full rounded-md border border-input bg-background px-2 text-xs font-normal"><option value="all">Any configuration</option><option value="rules">Has rules</option><option value="split">Has split rules</option><option value="unconfigured">No rules</option></select></label>
                    <label className="space-y-1 text-xs font-medium">Rule strategy<select aria-label="Filter strategy" value={strategyFilter} onChange={(e) => setStrategyFilter(e.target.value)} className="mt-1 h-8 w-full rounded-md border border-input bg-background px-2 text-xs font-normal"><option value="all">All strategies</option><option value="STANDARD">Single Item</option><option value="SPLIT_BY_PERCENT">Split by %</option><option value="SPLIT_BY_UNIT_VALUE">Unit Value</option></select></label>
                    <label className="space-y-1 text-xs font-medium">Rule status<select aria-label="Filter status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="mt-1 h-8 w-full rounded-md border border-input bg-background px-2 text-xs font-normal"><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
                </>}
                activeFilterCount={[normStatusFilter, configFilter, strategyFilter, statusFilter].filter((v) => v !== "all").length}
                filterActions={<Button variant="ghost" size="sm" onClick={() => { setStrategyFilter("all"); setStatusFilter("all"); setNormStatusFilter("all"); setConfigFilter("all"); setUrl((p) => { p.delete("status"); p.delete("config"); }); }}>Reset</Button>}
                actions={<>
                    {canWrite && <Button size="sm" onClick={startNewRule} disabled={!sion} title={sion ? `New ${sionLabel} rule` : "Expand a SION norm first"}><Plus className="size-4" />New Rule</Button>}
                    <Button size="sm" variant="outline" onClick={previewSion} disabled={!!busy || !canExecuteSion}><Eye className="size-4" />Preview Impact</Button>
                    <Button size="sm" variant="outline" onClick={runSelectedTest} disabled={!selectedRule?.id || !!busy || hasUnsavedChanges}><CheckCircle2 className="size-4" />Validate</Button>
                    <ActionMenu trigger="button" label="More planning actions" items={[
                        ...(canWrite ? [
                            { id: "plan-expired", label: "Plan all expired licences", icon: Zap, disabled: !!busy || !canExecuteSion, onSelect: () => void planSion("ALL", "EXPIRED") },
                            { id: "plan-expiring", label: "Plan licences expiring soon", icon: Zap, disabled: !!busy || !canExecuteSion, onSelect: () => void planSion("ALL", "EXPIRING_SOON") },
                            { id: "replan-all", label: "Re-plan all eligible licences", icon: Zap, disabled: !!busy || !canExecuteSion, onSelect: () => setConfirmForceAll(true) },
                        ] : []),
                        { id: "back", label: "Back", icon: ArrowLeft, onSelect: () => navigate(origin, { state: { fromPlanning: location.pathname + location.search } }) },
                    ]} />
                </>}
            />
        </div>
        {normsError && <InlineError error={new Error(normsError)} title="Planning workspace error" onRetry={() => void loadNorms()} />}
        {normsLoading ? <NormSkeleton /> : !filteredNorms.length ? <EmptyState size="page" icon={ClipboardList} title="No SION norms found" description={norms.length ? "Try adjusting your search or filters." : "No active or configured SION norms."} /> : (
            <ul className="flex min-w-0 flex-col gap-1.5" aria-label="SION norms">
                {filteredNorms.map((norm) => {
                    const expanded = sion === norm.id;
                    return <li key={norm.id} className="min-w-0">
                        <SionNormRow
                            norm={norm}
                            expanded={expanded}
                            onToggle={toggleNorm}
                            detailBar={expanded ? <>
                                <dl className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-5 gap-y-1 text-sm">
                                    <div className="flex items-baseline gap-1.5"><dt className="text-xs text-muted-foreground">Version</dt><dd className="font-medium tabular-nums">{version || "Not available"}</dd></div>
                                    <div className="flex items-baseline gap-1.5"><dt className="text-xs text-muted-foreground">Last updated</dt><dd className="font-medium">{displayDate(lastUpdated)}</dd></div>
                                    {hasUnsavedChanges && <div className="text-xs font-medium text-amber-700">Unsaved rule changes</div>}
                                </dl>
                                <Button size="sm" variant="ghost" onClick={() => selectSion(null)} aria-label={`Close ${norm.norm_class} workspace`}><X className="size-4" />Close</Button>
                            </> : undefined}
                        >
                            {expanded && <>
                                {error && <InlineError error={new Error(error)} title="Planning workspace error" onRetry={() => { setSion(null); requestAnimationFrame(() => setSion(norm.id)); }} />}
                                {loading && !rules.length ? <LoadingState variant="spinner" label="Loading planning workbench…" /> : (
                                    <DetailTabs
                                        recordKey={`sion:${norm.id}`}
                                        tabs={tabs}
                                        value={activeTab}
                                        onValueChange={(id) => setWorkbenchTab(id as NormTabId)}
                                        className="min-w-0 [&_[role=tablist]]:flex-nowrap [&_[role=tablist]]:overflow-x-auto [&_[role=tab]]:shrink-0"
                                        ariaLabel={`SION norm ${norm.norm_class} sections`}
                                    />
                                )}
                            </>}
                        </SionNormRow>
                    </li>;
                })}
            </ul>
        )}
        {pendingSion !== undefined && <ConfirmDialog show title="Unsaved changes" message="Save or discard the current rule before switching SION norms." severity="warning" confirmText="Discard and switch" onConfirm={() => { setDraft(null); applySion(pendingSion ?? null); }} onCancel={cancelPendingSion} />}
        <ConfirmDialog show={confirmForceAll} title={`Force re-plan ${sionLabel}?`} message={`This will reprocess all eligible current DFIA entries for ${sionLabel} using the latest saved planning rules.`} severity="danger" confirmText="Force All" onConfirm={() => planSion("ALL")} onCancel={() => setConfirmForceAll(false)} />
        <ConfirmDialog show={!!confirmDeleteRule} title="Delete planning rule?" message={`Delete ${confirmDeleteRule?.name ?? "this rule"}? This cannot be undone.`} severity="danger" confirmText={busy === "delete" ? "Deleting…" : "Delete"} onConfirm={retireRule} onCancel={() => setConfirmDeleteRule(null)} />
    </div>;
}

function NormSkeleton() {
    return (
        <div role="status" aria-label="Loading SION norms" className="space-y-1.5">
            {[60, 80, 70, 90, 65].map((w, i) => (
                <div key={i} className="flex items-center gap-4 rounded-lg border border-border bg-card px-4 py-3">
                    <Skeleton className="h-4 w-12" />
                    <Skeleton className="h-3" style={{ width: `${w * 2}px` }} />
                    <Skeleton className="h-3 w-20" />
                    <Skeleton className="ml-auto h-5 w-16 rounded-full" />
                </div>
            ))}
        </div>
    );
}

/**
 * LicensePlanningWorkspaceActiveFiltersDisplay — shows all active filters with individual remove buttons
 */
function LicensePlanningWorkspaceActiveFiltersDisplay({
    ruleSearch,
    strategyFilter,
    statusFilter,
    onRemoveFilter,
    onClearAll,
}: {
    ruleSearch: string;
    strategyFilter: string;
    statusFilter: string;
    onRemoveFilter: (key: string) => void;
    onClearAll: () => void;
}) {
    const activeFilters: ActiveFilterItem[] = useMemo(() => {
        const items: ActiveFilterItem[] = [];

        // Rule Search
        if (ruleSearch.trim()) {
            items.push({
                key: 'ruleSearch',
                label: 'Rule Search',
                value: `"${ruleSearch}"`,
            });
        }

        // Strategy Filter
        if (strategyFilter !== "all") {
            const strategyLabels: Record<string, string> = {
                "STANDARD": "Single Item",
                "SPLIT_BY_PERCENT": "Split by %",
                "SPLIT_BY_UNIT_VALUE": "Unit Value",
            };
            items.push({
                key: 'strategyFilter',
                label: 'Strategy',
                value: strategyLabels[strategyFilter] || strategyFilter,
            });
        }

        // Status Filter
        if (statusFilter !== "all") {
            const statusLabels: Record<string, string> = {
                "active": "Active",
                "inactive": "Inactive",
            };
            items.push({
                key: 'statusFilter',
                label: 'Status',
                value: statusLabels[statusFilter] || statusFilter,
            });
        }

        return items;
    }, [ruleSearch, strategyFilter, statusFilter]);

    if (activeFilters.length === 0) {
        return null;
    }

    return (
        <div className="border-b">
            <div className="px-3 py-2">
                <ActiveFilters
                    filters={activeFilters}
                    onRemove={onRemoveFilter}
                    onClearAll={onClearAll}
                    showCount={true}
                    compact={true}
                />
            </div>
        </div>
    );
}
