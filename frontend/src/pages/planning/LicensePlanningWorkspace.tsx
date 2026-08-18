import { Fragment, useEffect, useState, type ComponentProps } from "react";
import { ArrowDown, ArrowLeft, ArrowUp, ChevronDown, ChevronRight, Eye, Loader2, MoreHorizontal, Pencil, Plus, Search, TestTube2, Zap } from "lucide-react";
import Select from "react-select";
import { toast } from "sonner";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import api from "@/api/axios";
import { Button as UiButton } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { createSionPlanningRule, fetchSionPlanningRules, planSavedSionRules, previewSavedSionRules, reorderSionPlanningRules, testSionPlanningRule, updateSionPlanningRule, type RuleAllocationStrategy, type SionPlanningMode, type SionPlanningPreview, type SionPlanningPreviewLicense, type SionPlanningRule } from "@/services/api/planningRuleApi";
import { SplitAllocationPreview } from "./SplitAllocationPreview";
import { AllocationStrategyEditor } from "./AllocationStrategyEditor";
import { validatePlanningRule, hasValidationErrors, type RuleFormErrors } from "./ruleFormValidation";
import { ExpressionTreeEditor, emptyRuleCondition } from "./ExpressionTreeEditor";

// This workspace contains actions, never form submissions. Keeping the native
// type explicit prevents a future surrounding form from turning any editor
// action into a submit/navigation (and therefore a scroll-to-top).
const Button = (props: ComponentProps<typeof UiButton>) => <UiButton type="button" {...props} />;

export function planningPath(licenseId?: string | number | null, origin?: string): string { const p = new URLSearchParams(); if (licenseId) p.set("license_id", String(licenseId)); if (origin) p.set("origin", origin); return `/planning${p.size ? `?${p}` : ""}`; }
const emptyRule = (sion: number): SionPlanningRule => ({ sion, name: "", expression: { operator: "AND", conditions: [emptyRuleCondition()] }, max_unit_price: "", unit: "KG", priority: 0, is_active: true });

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

export default function LicensePlanningWorkspace() {
    const [params, setParams] = useSearchParams(); const navigate = useNavigate(); const location = useLocation();
    const origin = params.get("origin") || "/licenses";
    const [sions, setSions] = useState<any[]>([]); const [sion, setSion] = useState<number | null>(null); const [rules, setRules] = useState<SionPlanningRule[]>([]); const [draft, setDraft] = useState<SionPlanningRule | null>(null); const [selectedRuleId, setSelectedRuleId] = useState<number | null>(null); const [activeTab, setActiveTab] = useState("rules"); const [ruleSearch, setRuleSearch] = useState(""); const [pendingSion, setPendingSion] = useState<number | null | undefined>(undefined); const [confirmForceAll, setConfirmForceAll] = useState(false); const [busy, setBusy] = useState<"save" | "test" | "preview" | "plan-new" | "plan-all" | "deactivate" | "reorder" | null>(null); const [preview, setPreview] = useState<SionPlanningPreview | null>(null); const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
    const [allocationDraft, setAllocationDraft] = useState<RuleAllocationStrategy | null>(null);
    const [savedAllocation, setSavedAllocation] = useState<RuleAllocationStrategy | null>(null);
    const [formErrors, setFormErrors] = useState<RuleFormErrors>({});
    const preserveScroll = () => {
        const host = document.getElementById("main-content");
        if (!host) return () => undefined;
        const top = host.scrollTop;
        return () => requestAnimationFrame(() => requestAnimationFrame(() => {
            host.scrollTop = top;
        }));
    };
    useEffect(() => { setLoading(true); api.get("masters/sion-classes/", { params: { is_active: true, page_size: 500, ordering: "norm_class" } }).then(({ data }) => { const rows = data?.results ?? data ?? []; setSions(rows); const requested = params.get("sion"); if (requested) { const match = rows.find((row: any) => String(row.id) === requested || String(row.norm_class).toUpperCase() === requested.toUpperCase()); if (match) setSion(match.id); } }).catch(() => setError("Unable to load SION norms.")).finally(() => setLoading(false)); }, []);
    useEffect(() => { if (!sion) { setRules([]); setDraft(null); setSelectedRuleId(null); setPreview(null); return; } setLoading(true); setError(""); setDraft(null); setPreview(null); fetchSionPlanningRules(sion).then((rows) => { const ordered = [...rows].sort((a, b) => a.priority - b.priority); setRules(ordered); setSelectedRuleId(ordered[0]?.id ?? null); }).catch(() => setError("Unable to load planning rules.")).finally(() => setLoading(false)); }, [sion]);
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
    const save = async () => { if (!draft) return null; const { priority: _databasePriority, output_item: _obsoleteOutputItem, ...payload } = draft; const saved = ruleHasUnsavedChanges ? (draft.id ? await updateSionPlanningRule(draft.id, payload) : await createSionPlanningRule(payload as SionPlanningRule)) : draft; const fresh = [...await fetchSionPlanningRules(saved.sion)].sort((a, b) => a.priority - b.priority); setRules(fresh); const persisted = fresh.find((rule) => rule.id === saved.id) ?? saved; setDraft(persisted); setSelectedRuleId(persisted.id ?? null); toast.success("Rule saved"); return saved; };
    const testRule = async () => { if (busy || !draft?.id || hasUnsavedChanges) return; const restore = preserveScroll(); setBusy("test"); setError(""); try { setPreview(await testSionPlanningRule(draft.id)); setActiveTab("preview"); toast.success("Rule test completed"); } catch { toast.error("Rule test failed"); } finally { setBusy(null); restore(); } };
    const planSion = async (mode: SionPlanningMode) => { if (busy || !sion || !canExecuteSion) return; const restore = preserveScroll(); setConfirmForceAll(false); setBusy(mode === "ALL" ? "plan-all" : "plan-new"); setError(""); try { await planSavedSionRules(sion, mode); setPreview(await previewSavedSionRules(sion, mode)); setActiveTab("preview"); toast.success(mode === "ALL" ? `${sionLabel} full eligible universe reprocessed` : `${sionLabel} new eligible data planned`); setRules(await fetchSionPlanningRules(sion)); } catch { toast.error("Planning failed"); } finally { setBusy(null); restore(); } };
    const selectedSion = sions.find((row) => row.id === sion); const sionLabel = selectedSion?.norm_class ?? "SION";
    const selectSion = (next: number | null) => { if (hasUnsavedChanges) { setPendingSion(next); return; } applySion(next); };
    const applySion = (next: number | null) => { setSion(next); setPendingSion(undefined); const nextParams = new URLSearchParams(params); if (next) { const row = sions.find((item) => item.id === next); nextParams.set("sion", row?.norm_class ?? String(next)); } else nextParams.delete("sion"); setParams(nextParams, { replace: true }); };
    const previewSion = async () => { if (!sion || busy || !canExecuteSion) return; const restore = preserveScroll(); setBusy("preview"); setError(""); try { setPreview(await previewSavedSionRules(sion, "NEW")); setActiveTab("preview"); toast.success(`${sionLabel} preview updated`); } catch { toast.error("Plan preview failed"); } finally { setBusy(null); restore(); } };
    const reorder = async (index: number, offset: number) => { if (!sion || busy) return; const next = [...rules]; const target = index + offset; if (target < 0 || target >= next.length) return; const restore = preserveScroll(); [next[index], next[target]] = [next[target], next[index]]; setBusy("reorder"); setError(""); try { const fresh = await reorderSionPlanningRules(sion, next.map((rule) => rule.id!)); setRules([...fresh].sort((a, b) => a.priority - b.priority)); toast.success("Priority updated"); } catch { toast.error("Unable to reorder rules"); } finally { setBusy(null); restore(); } };
    const selectedRule = rules.find((rule) => rule.id === selectedRuleId) ?? null;
    const filteredRules = rules.filter((rule) => rule.name.toLowerCase().includes(ruleSearch.trim().toLowerCase()));
    const beginEdit = (rule: SionPlanningRule) => { setSelectedRuleId(rule.id ?? null); setDraft(rule); };
    const runSelectedTest = async () => { if (!selectedRule?.id || busy) return; setBusy("test"); try { setPreview(await testSionPlanningRule(selectedRule.id)); setActiveTab("preview"); toast.success("Rule test completed"); } catch { toast.error("Rule test failed"); } finally { setBusy(null); } };
    return <div className="space-y-3">
        <div className="sticky top-0 z-30 -mx-2 border-b bg-background/95 px-2 py-2 backdrop-blur">
            <div className="flex flex-wrap items-center gap-3">
                <Button variant="ghost" size="sm" onClick={() => navigate(origin, { state: { fromPlanning: location.pathname + location.search } })}><ArrowLeft className="size-4" />Back</Button>
                <div className="mr-auto"><h1 className="text-lg font-semibold">SION Planning</h1><p className="text-xs text-muted-foreground">{sion ? `${sionLabel} · ${rules.length} rules · ${activeSavedRules.length} active · Database rules` : "Select a norm to begin"}</p></div>
                <label className="w-48 text-xs font-medium">SION Norm<Select aria-label="SION Norm" options={sions.map((row) => ({ value: row.id, label: row.norm_class }))} value={sions.filter((row) => row.id === sion).map((row) => ({ value: row.id, label: row.norm_class }))[0] ?? null} onChange={(option) => selectSion(option?.value ?? null)} className="mt-1 font-normal" /></label>
                <Button variant="outline" onClick={previewSion} disabled={!!busy || !canExecuteSion}>{busy === "preview" ? <Loader2 className="size-4 animate-spin" /> : <Eye className="size-4" />}Preview</Button>
                <Button onClick={() => planSion("NEW")} disabled={!!busy || !canExecuteSion}>{busy === "plan-new" ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" />}New Only</Button>
                <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" aria-label="More planning actions"><MoreHorizontal className="size-4" />More</Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem className="text-destructive" disabled={!!busy || !canExecuteSion} onSelect={() => setConfirmForceAll(true)}>Force All</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
            </div>
        </div>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        {loading && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Loading…</p>}
        {!sion ? <div className="rounded-lg border border-dashed p-12 text-center text-sm text-muted-foreground">Select a SION norm to load its saved planning rules.</div> :
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-3">
            <TabsList><TabsTrigger value="rules">Rules ({rules.length})</TabsTrigger><TabsTrigger value="preview">Plan Preview {preview?.licenses?.length ? `(${preview.licenses.length})` : ""}</TabsTrigger></TabsList>
            <TabsContent value="rules">
                <section aria-label="Rule workspace" className="grid min-h-[620px] overflow-hidden rounded-lg border bg-card lg:grid-cols-[minmax(320px,38%)_minmax(0,62%)]">
                    <div className="border-b lg:border-b-0 lg:border-r">
                        <div className="flex items-center gap-2 border-b p-3"><div className="relative flex-1"><Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" /><input aria-label="Search rules" value={ruleSearch} onChange={(event) => setRuleSearch(event.target.value)} placeholder="Search rules…" className="h-9 w-full rounded-md border bg-background pl-8 pr-2 text-sm" /></div><Button size="sm" onClick={() => { setDraft(emptyRule(sion)); setSelectedRuleId(null); }}><Plus className="size-4" />Add Rule</Button></div>
                        <div className="max-h-[560px] overflow-auto"><table className="w-full text-sm"><thead className="sticky top-0 bg-muted/80 text-left text-xs text-muted-foreground"><tr><th className="w-12 px-3 py-2">#</th><th className="px-2 py-2">Rule</th><th className="px-2 py-2">Max</th><th className="w-12 py-2"></th></tr></thead><tbody>{filteredRules.map((rule) => {
                            const index = rules.findIndex((item) => item.id === rule.id); const selected = selectedRuleId === rule.id;
                            return <tr key={rule.id} className={`border-t ${selected ? "bg-primary/5" : "hover:bg-muted/30"}`}><td className="px-3 py-2 font-semibold">{rule.priority}</td><td className="p-0"><button type="button" aria-current={selected ? "true" : undefined} className="w-full px-2 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring" onClick={() => { if (!hasUnsavedChanges) { setSelectedRuleId(rule.id ?? null); setDraft(null); } }}><span className="block truncate font-medium">{rule.name}</span><span className="flex items-center gap-2 text-[11px] text-muted-foreground">{rule.strategy === "SPLIT_BY_UNIT_VALUE" && <Badge variant="outline" className="h-4 px-1 text-[9px]">Split</Badge>}{rule.strategy === "SPLIT_BY_PERCENT" && <Badge variant="outline" className="h-4 px-1 text-[9px]">%</Badge>}<Badge variant={rule.is_active ? "default" : "secondary"} className="h-4 px-1 text-[9px]">{rule.is_active ? "Active" : "Inactive"}</Badge>v{rule.version ?? "—"} · {rule.unit}</span></button></td><td className="px-2 tabular-nums">{rule.max_unit_price}</td><td><DropdownMenu><DropdownMenuTrigger asChild><Button size="icon" variant="ghost" aria-label={`Actions for ${rule.name}`}><MoreHorizontal className="size-4" /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onSelect={() => { setSelectedRuleId(rule.id ?? null); setDraft(null); }}>View</DropdownMenuItem><DropdownMenuItem onSelect={() => beginEdit(rule)}>Edit</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem disabled={index === 0 || !!busy} onSelect={() => reorder(index, -1)}><ArrowUp />Move Up</DropdownMenuItem><DropdownMenuItem disabled={index === rules.length - 1 || !!busy} onSelect={() => reorder(index, 1)}><ArrowDown />Move Down</DropdownMenuItem></DropdownMenuContent></DropdownMenu></td></tr>;
                        })}</tbody></table>{!filteredRules.length && <p className="p-8 text-center text-sm text-muted-foreground">No rules match this search.</p>}</div>
                    </div>
                    <section aria-label={draft ? "Rule editor" : "Rule detail"} className="flex min-h-0 flex-col">
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
                            <div aria-label="Rule edit actions" className="sticky bottom-0 flex min-h-14 items-center gap-2 border-t bg-card/95 px-4 py-2 backdrop-blur">
                                <span className={`mr-auto text-xs font-medium ${hasValidationErrors(formErrors) ? "text-destructive" : hasUnsavedChanges ? "text-warning" : "text-success"}`}>
                                    {hasValidationErrors(formErrors) ? "❌ Errors present" : hasUnsavedChanges ? "● Unsaved changes" : "✓ Saved"}
                                </span>
                                <Button variant="outline" onClick={() => setDraft(null)}>Discard</Button>
                                {draft.id && <Button variant="outline" onClick={testRule} disabled={!!busy || hasUnsavedChanges}>{busy === "test" ? <Loader2 className="size-4 animate-spin" /> : <TestTube2 className="size-4" />}Test Rule</Button>}
                                <Button onClick={async () => { if (busy) return; const restore = preserveScroll(); setBusy("save"); try { await save(); } catch { toast.error("Unable to save rule"); } finally { setBusy(null); restore(); } }} disabled={!!busy || hasValidationErrors(formErrors) || !hasUnsavedChanges}>
                                    {busy === "save" && <Loader2 className="size-4 animate-spin" />}Save
                                </Button>
                            </div>
                        </> : selectedRule ? <div className="space-y-5 p-5">
                            <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Rule #{selectedRule.priority}</p><h2 className="text-lg font-semibold">{selectedRule.name}</h2><p className="mt-1 text-xs text-muted-foreground">Version {selectedRule.version ?? "—"} · Updated {selectedRule.modified_on ? new Date(selectedRule.modified_on).toLocaleString() : "—"}</p></div><Badge variant={selectedRule.is_active ? "default" : "secondary"}>{selectedRule.is_active ? "Active" : "Inactive"}</Badge></div>
                            <dl className="grid grid-cols-2 gap-3 rounded-md bg-muted/30 p-3 text-sm">
                                <div><dt className="text-xs text-muted-foreground">Strategy</dt><dd className="font-medium">{selectedRule.strategy ?? "Legacy"}</dd></div>
                                <div><dt className="text-xs text-muted-foreground">Priority</dt><dd className="font-medium">#{selectedRule.priority}</dd></div>
                                {selectedRule.strategy === "STANDARD" && selectedRule.standard_item_name && <div><dt className="text-xs text-muted-foreground">Import Item</dt><dd className="font-medium">{selectedRule.standard_item_name}</dd></div>}
                                <div><dt className="text-xs text-muted-foreground">Max Price</dt><dd className="font-medium">{selectedRule.max_unit_price} / {selectedRule.unit}</dd></div>
                            </dl>
                            <AllocationStrategySummary rule={selectedRule} />
                            <div className="flex justify-end gap-2 border-t pt-3"><Button variant="outline" onClick={runSelectedTest} disabled={!!busy}><TestTube2 className="size-4" />Test Rule</Button><Button onClick={() => beginEdit(selectedRule)}><Pencil className="size-4" />Edit</Button></div>
                        </div> : <div className="grid flex-1 place-items-center p-8 text-sm text-muted-foreground">Select a rule to inspect its details.</div>}
                    </section>
                </section>
            </TabsContent>
            <TabsContent value="preview">{preview ? <LicensePreview preview={preview} onViewPlan={(licenseId) => navigate(`/licenses/${licenseId}/overview?tab=planning`)} /> : <div className="rounded-lg border border-dashed p-12 text-center text-sm text-muted-foreground">Run Preview to inspect matched licenses and proposed plan changes.</div>}</TabsContent>
        </Tabs>}
        {pendingSion !== undefined && <ConfirmDialog show title="Unsaved changes" message="Save or discard the current rule before switching SION norms." severity="warning" confirmText="Discard and switch" onConfirm={() => applySion(pendingSion ?? null)} onCancel={() => setPendingSion(undefined)} />}
        <ConfirmDialog show={confirmForceAll} title={`Force re-plan ${sionLabel}?`} message={`This will reprocess all eligible current DFIA entries for ${sionLabel} using the latest saved planning rules.`} severity="danger" confirmText="Force All" onConfirm={() => planSion("ALL")} onCancel={() => setConfirmForceAll(false)} />
    </div>;
}
