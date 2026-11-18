/**
 * Presentational tab bodies for one expanded SION norm. Pure: every value comes
 * from props (DB rules + the read-only norm-configuration payload).
 */
import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, Pencil, XCircle } from "lucide-react";

import type { SionNormConfiguration, SionNormSummary, SionPlanningRule } from "@/api/planningRuleApi";
import { Button } from "@/components/ui/button";
import { EmptyState, StatusBadge } from "@/components/shared";
import { cn } from "@/lib/utils";
import {
    conditionSummary, deriveMappingRows, deriveSplits, displayDate,
    type ConfigIssue, type NormTabId,
} from "./normConfig";

const TABLE = "w-full min-w-[640px] text-sm";
const TH = "px-3 py-2 text-left text-xs font-medium text-muted-foreground";
const TD = "px-3 py-2 align-top";

function Panel({ title, description, actions, children, className }: { title: string; description?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
    return (
        <section aria-label={title} className={cn("min-w-0 rounded-lg border border-border/70 bg-card", className)}>
            <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-3 py-2">
                <div className="min-w-0">
                    <h3 className="text-sm font-semibold">{title}</h3>
                    {description && <p className="text-xs text-muted-foreground">{description}</p>}
                </div>
                {actions}
            </header>
            <div className="min-w-0 overflow-x-auto">{children}</div>
        </section>
    );
}

function Stat({ label, value, onClick }: { label: string; value: ReactNode; onClick?: () => void }) {
    const body = <><dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</dt><dd className="mt-0.5 text-base font-semibold tabular-nums">{value}</dd></>;
    return onClick
        ? <button type="button" onClick={onClick} className="rounded-md border border-border/70 bg-muted/30 px-3 py-2 text-left transition-colors hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"><dl>{body}</dl></button>
        : <dl className="rounded-md border border-border/70 bg-muted/30 px-3 py-2">{body}</dl>;
}

const Keys = ({ value }: { value?: string | null }) => value ? <code className="rounded bg-muted px-1 py-px font-mono text-[11px]">{value}</code> : <span className="text-muted-foreground">—</span>;

// ── Overview ────────────────────────────────────────────────────────────────
export function OverviewTab({ summary, rules, config, issues, onOpenTab }: {
    summary?: SionNormSummary; rules: SionPlanningRule[]; config: SionNormConfiguration | null; issues: ConfigIssue[]; onOpenTab: (tab: NormTabId) => void;
}) {
    const active = rules.filter((r) => r.is_active);
    const profile = config?.profiles.find((p) => p.is_active);
    const actionCount = profile?.actions.filter((a) => a.is_active !== false).length ?? config?.registry?.actions.length ?? 0;
    const groups = config?.entitlement_profile?.groups ?? [];
    const outputs = new Set([...active.map((r) => r.standard_item_name).filter(Boolean), ...(config?.registry?.mappings.map((m) => m.output_name) ?? [])]);
    const errors = issues.filter((i) => i.severity === "error").length;
    const warnings = issues.filter((i) => i.severity === "warning").length;
    const version = Math.max(0, ...rules.map((r) => r.version ?? 0), profile?.version ?? 0);
    const lastUpdated = [...rules.map((r) => r.modified_on), summary?.last_updated, profile?.modified_on].filter(Boolean).sort().pop();
    const sources = [active.length ? "Database rules" : null, profile ? `DB profile ${profile.stable_key} v${profile.version}` : null, config?.registry ? "Code registry" : null, config?.entitlement_profile ? "Entitlement profile" : null].filter(Boolean);
    return (
        <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
                <Stat label="Active Rules" value={active.length || (config?.registry?.rules.length ? `${config.registry.rules.length} (registry)` : 0)} onClick={() => onOpenTab("rules")} />
                <Stat label="Actions" value={actionCount} />
                <Stat label="Product Groups" value={groups.length || outputs.size} onClick={groups.length ? () => onOpenTab("mapping") : undefined} />
                <Stat label="Validation" value={errors ? `${errors} error${errors === 1 ? "" : "s"}` : warnings ? `${warnings} warning${warnings === 1 ? "" : "s"}` : "Passed"} onClick={() => onOpenTab("validation")} />
                <Stat label="Version" value={version || "Not available"} />
                <Stat label="Last Updated" value={<span className="text-sm">{displayDate(lastUpdated)}</span>} />
            </div>
            <Panel title="Configuration summary" description={sources.length ? `Sources: ${sources.join(" · ")}` : "No planning configuration recorded for this norm."}>
                <dl className="grid gap-x-6 gap-y-2 p-3 text-sm sm:grid-cols-2">
                    <div><dt className="text-xs text-muted-foreground">Norm</dt><dd className="font-mono font-semibold">{config?.sion.norm_class ?? summary?.norm_class}</dd></div>
                    <div><dt className="text-xs text-muted-foreground">Status</dt><dd><StatusBadge tone={(config?.sion.is_active ?? summary?.is_active) ? "success" : "neutral"} label={(config?.sion.is_active ?? summary?.is_active) ? "Active" : "Inactive"} /></dd></div>
                    <div className="sm:col-span-2"><dt className="text-xs text-muted-foreground">Description</dt><dd>{config?.sion.description ?? summary?.description ?? "—"}</dd></div>
                    {groups.length > 0 && <div className="sm:col-span-2"><dt className="text-xs text-muted-foreground">Product groups</dt><dd className="mt-1 flex flex-wrap gap-1.5">{groups.map((g) => <span key={g.key} className="rounded-sm border border-border px-1.5 py-px text-xs">{g.label}{g.entitlement_items.length > 1 ? ` · ${g.entitlement_items.length} entitlements` : ""}</span>)}</dd></div>}
                    {outputs.size > 0 && <div className="sm:col-span-2"><dt className="text-xs text-muted-foreground">Outputs</dt><dd className="mt-1 flex flex-wrap gap-1.5">{[...outputs].map((o) => <span key={String(o)} className="rounded-sm bg-muted px-1.5 py-px text-xs">{o}</span>)}</dd></div>}
                </dl>
            </Panel>
        </div>
    );
}

// ── Rules (code registry, read-only) ────────────────────────────────────────
export function RegistryRulesPanel({ config }: { config: SionNormConfiguration | null }) {
    const rules = config?.registry?.rules ?? [];
    if (!rules.length) return null;
    return (
        <Panel title="Code registry rules" description="Declared in the generic planner registry (read-only here; database rules take precedence once saved).">
            <table className={TABLE}>
                <thead className="bg-muted/50"><tr><th className={TH}>Priority</th><th className={TH}>Stable key</th><th className={TH}>Rule</th><th className={TH}>Conditions</th><th className={TH}>Output</th><th className={TH}>Max price</th></tr></thead>
                <tbody>{rules.map((rule) => {
                    const c = conditionSummary(rule.expression);
                    return <tr key={rule.stable_key} className="border-t border-border/60"><td className={cn(TD, "font-semibold")}>{rule.priority}</td><td className={TD}><Keys value={rule.stable_key} /></td><td className={cn(TD, "font-medium")}>{rule.name}</td><td className={cn(TD, "text-xs text-muted-foreground")}>{c.total} condition{c.total === 1 ? "" : "s"}</td><td className={TD}><Keys value={rule.output_key} /></td><td className={cn(TD, "tabular-nums")}>${rule.max_unit_price}/{rule.unit}</td></tr>;
                })}</tbody>
            </table>
        </Panel>
    );
}

// ── Split configuration ─────────────────────────────────────────────────────
export function SplitConfigurationTab({ rules, config }: { rules: SionPlanningRule[]; config: SionNormConfiguration | null }) {
    const splits = deriveSplits(rules, config);
    if (!splits.length) return <EmptyState title="No split rules" description="This norm has no split-based rule configured." />;
    return (
        <div className="space-y-3">
            {splits.map((split) => (
                <Panel
                    key={split.id}
                    title={split.group ? `${split.group} split` : split.sourceRuleName ?? split.sourceLabel}
                    description={<>Source: <Keys value={split.sourceLabel} /> · {{ registry: "code registry", database: split.kind === "percent" ? "database percentage rows" : "database unit-value rows", profile: "database planning profile" }[split.source]}</>}
                    actions={<StatusBadge tone={split.totalValid ? "success" : "danger"} label={split.kind === "percent" ? `Total ${split.totalShare}` : split.totalShare} />}
                >
                    <dl className="grid gap-x-6 gap-y-2 border-b border-border/60 p-3 text-sm sm:grid-cols-3">
                        <div><dt className="text-xs text-muted-foreground">Source product group</dt><dd className="font-medium">{split.sourceRuleName ?? "—"} {split.sourceRuleKey && <Keys value={split.sourceRuleKey} />}</dd></div>
                        <div><dt className="text-xs text-muted-foreground">Quantity basis</dt><dd><Keys value={split.basis} /></dd></div>
                        <div><dt className="text-xs text-muted-foreground">{split.kind === "percent" ? "Entitlement groups" : "Price bands"}</dt><dd>{split.targets.length}</dd></div>
                    </dl>
                    <table className={TABLE} aria-label="Split entitlements">
                        <thead className="bg-muted/50"><tr><th className={TH}>Entitlement</th><th className={TH}>Target key</th><th className={cn(TH, "text-right")}>{split.kind === "percent" ? "Split" : "Price band"}</th><th className={TH}>Products mapped</th><th className={TH}>Valuation</th><th className={cn(TH, "text-right")}>{split.kind === "percent" ? "Rate" : "Reference price"}</th></tr></thead>
                        <tbody>{split.targets.map((t) => (
                            <tr key={t.key} className="border-t border-border/60">
                                <td className={cn(TD, "font-medium")}>{t.label}{t.entitlement && t.entitlement !== t.label && <span className="block text-xs text-muted-foreground">{t.entitlement}</span>}</td>
                                <td className={TD}><Keys value={t.key} /></td>
                                <td className={cn(TD, "text-right font-semibold tabular-nums")}>{t.share}</td>
                                <td className={TD}>{t.products.length ? <ul className="space-y-0.5">{t.products.map((p) => <li key={p}>{p} → {t.label}</li>)}</ul> : <span className="text-muted-foreground">—</span>}</td>
                                <td className={TD}>{t.valuation ?? "—"}</td>
                                <td className={cn(TD, "text-right tabular-nums")}>{t.rate ? `$${t.rate}` : "—"}</td>
                            </tr>
                        ))}</tbody>
                    </table>
                    {(split.restrictions.length > 0 || split.quantityRule) && (
                        <div className="space-y-1 border-t border-border/60 p-3 text-xs">
                            {split.restrictions.map((r) => <p key={r}><span className="font-medium">{split.source === "registry" ? "Rebalance:" : "Configured:"}</span> <span className="font-mono text-muted-foreground">{r}</span></p>)}
                            {split.quantityRule && <p><span className="font-medium">Quantity allocation:</span> <span className="font-mono text-muted-foreground">{split.quantityRule}</span></p>}
                        </div>
                    )}
                </Panel>
            ))}
        </div>
    );
}

// ── Product mapping ─────────────────────────────────────────────────────────
export function ProductMappingTab({ rules, config, canWrite, onEditRule }: { rules: SionPlanningRule[]; config: SionNormConfiguration | null; canWrite: boolean; onEditRule: (ruleId: number) => void }) {
    const rows = deriveMappingRows(rules, config);
    const groups = (config?.entitlement_profile?.groups ?? []).filter((g) => g.products.length);
    const outputs = config?.profiles.find((p) => p.is_active)?.output_mappings.filter((m) => m.is_active) ?? [];
    return (
        <div className="space-y-3">
            {groups.map((group) => (
                <Panel key={group.key} title={`${group.label} — product → entitlement`} description={<>Matched on BOE product / allotment item names · source <Keys value={config?.entitlement_profile?.source} /></>}>
                    <table className={TABLE} aria-label={`${group.label} product mapping`}>
                        <thead className="bg-muted/50"><tr><th className={TH}>Product</th><th className={TH}>Entitlement</th><th className={TH}>Matching aliases</th></tr></thead>
                        <tbody>{group.products.map((p) => {
                            const label = config?.entitlement_profile?.entitlements.find((e) => e.item === p.entitlement)?.label;
                            return <tr key={p.name} className="border-t border-border/60"><td className={cn(TD, "font-medium")}>{p.name}</td><td className={TD}>{p.entitlement}{label && label !== p.entitlement && <span className="block text-xs text-muted-foreground">{label}</span>}</td><td className={TD}><span className="flex flex-wrap gap-1">{p.aliases.map((a) => <Keys key={a} value={a} />)}</span></td></tr>;
                        })}</tbody>
                    </table>
                </Panel>
            ))}
            <Panel title="Rule matching conditions" description="HS code and product-description conditions with the assigned output item.">
                {rows.length ? (
                    <table className={TABLE}>
                        <thead className="bg-muted/50"><tr><th className={TH}>Priority</th><th className={TH}>Rule</th><th className={TH}>HS code</th><th className={TH}>Product description</th><th className={TH}>Assignment</th><th className={TH}>Max price</th>{canWrite && <th className={TH}><span className="sr-only">Actions</span></th>}</tr></thead>
                        <tbody>{rows.map((row) => (
                            <tr key={row.id} className="border-t border-border/60">
                                <td className={cn(TD, "font-semibold")}>{row.priority}</td>
                                <td className={TD}><span className="font-medium">{row.ruleName}</span><span className="block"><Keys value={row.ruleKey} /> {row.source === "registry" && <span className="text-[11px] text-muted-foreground">registry</span>}</span></td>
                                <td className={cn(TD, "text-xs")}>{row.hsn.length ? row.hsn.join(" · ") : "—"}</td>
                                <td className={cn(TD, "text-xs")}>{row.description.length ? row.description.join(" · ") : "—"}</td>
                                <td className={TD}>{row.assignment}</td>
                                <td className={cn(TD, "tabular-nums")}>${row.maxPrice}/{row.unit}</td>
                                {canWrite && <td className={TD}>{row.ruleId != null && <Button type="button" size="sm" variant="ghost" aria-label={`Edit mapping rule ${row.ruleName}`} onClick={() => onEditRule(row.ruleId!)}><Pencil className="size-3.5" />Edit</Button>}</td>}
                            </tr>
                        ))}</tbody>
                    </table>
                ) : <p className="p-4 text-sm text-muted-foreground">No rules configured.</p>}
            </Panel>
            {outputs.length > 0 && (
                <Panel title="Profile output mappings" description="Active database profile outputs.">
                    <table className={TABLE}><thead className="bg-muted/50"><tr><th className={TH}>Stable key</th><th className={TH}>Source rule</th><th className={TH}>Output item</th><th className={TH}>Rate</th></tr></thead>
                        <tbody>{outputs.map((m) => <tr key={m.stable_key} className="border-t border-border/60"><td className={TD}><Keys value={m.stable_key} /></td><td className={TD}>{m.source_rule_name ?? "—"}</td><td className={TD}>{m.output_item ?? "—"}</td><td className={cn(TD, "tabular-nums")}>{m.rate ? `$${m.rate}/${m.unit}` : "—"}</td></tr>)}</tbody>
                    </table>
                </Panel>
            )}
        </div>
    );
}

// ── Validation ──────────────────────────────────────────────────────────────
const SEVERITY = {
    error: { icon: XCircle, tone: "danger", label: "Error" },
    warning: { icon: AlertTriangle, tone: "warning", label: "Warning" },
    info: { icon: Info, tone: "info", label: "Info" },
} as const;

export function ValidationTab({ issues, selectedRuleName, onRunTest, canRunTest, busy }: { issues: ConfigIssue[]; selectedRuleName?: string; onRunTest: () => void; canRunTest: boolean; busy: boolean }) {
    const errors = issues.filter((i) => i.severity === "error").length;
    return (
        <div className="space-y-3">
            <Panel
                title="Configuration validation"
                description="Checks rule completeness, split percentages, duplicate conditions/priorities and product mappings."
                actions={<div className="flex items-center gap-2"><StatusBadge tone={errors ? "danger" : "success"} label={errors ? `${errors} error${errors === 1 ? "" : "s"}` : "No errors"} />
                    <Button type="button" size="sm" variant="outline" disabled={!canRunTest || busy} onClick={onRunTest} title={selectedRuleName ? `Test ${selectedRuleName} against licences` : "Select a saved rule in the Rules tab"}><CheckCircle2 className="size-4" />Test selected rule</Button></div>}
            >
                {issues.length ? (
                    <ul className="divide-y divide-border/60" aria-label="Validation results">
                        {issues.map((issue, index) => {
                            const s = SEVERITY[issue.severity];
                            return <li key={`${issue.code}-${index}`} className="flex items-start gap-2 px-3 py-2 text-sm"><s.icon className={cn("mt-0.5 size-4 shrink-0", issue.severity === "error" ? "text-destructive" : issue.severity === "warning" ? "text-amber-600" : "text-muted-foreground")} aria-hidden="true" /><div className="min-w-0"><p><span className="sr-only">{s.label}: </span>{issue.subject && <span className="font-medium">{issue.subject} — </span>}{issue.message}</p><p className="font-mono text-[11px] text-muted-foreground">{issue.code}</p></div></li>;
                        })}
                    </ul>
                ) : <p className="flex items-center gap-2 p-3 text-sm text-success"><CheckCircle2 className="size-4" aria-hidden="true" />All configuration checks passed.</p>}
            </Panel>
            <p className="px-1 text-xs text-muted-foreground">Validation history is not recorded; results are computed from the current configuration. Backend validation still applies on every save.</p>
        </div>
    );
}

// ── Version history ─────────────────────────────────────────────────────────
const EVENT_LABELS: Record<string, string> = { RULE_CREATED: "Rule created", RULE_UPDATED: "Rule updated", RULE_ACTIVATED: "Rule activated", RULE_DEACTIVATED: "Rule deactivated" };

export function VersionHistoryTab({ config }: { config: SionNormConfiguration | null }) {
    if (!config) return null;
    const { rule_versions: versions, profiles, audit } = config;
    return (
        <div className="space-y-3">
            {versions.length > 0 && (
                <Panel title="Rule versions" description="Every saved version; edits append a new version and retire the previous one.">
                    <table className={TABLE}><thead className="bg-muted/50"><tr><th className={TH}>Stable key</th><th className={TH}>Rule</th><th className={TH}>Version</th><th className={TH}>Status</th><th className={TH}>Modified</th><th className={TH}>By</th></tr></thead>
                        <tbody>{versions.map((v) => <tr key={v.id} className="border-t border-border/60"><td className={TD}><Keys value={v.stable_key} /></td><td className={cn(TD, "font-medium")}>{v.name}</td><td className={cn(TD, "tabular-nums")}>v{v.version}</td><td className={TD}><StatusBadge tone={v.is_active ? "success" : "neutral"} label={v.is_active ? "Current" : "Superseded"} /></td><td className={cn(TD, "whitespace-nowrap")}>{displayDate(v.modified_on)}</td><td className={TD}>{v.modified_by_username ?? "—"}</td></tr>)}</tbody>
                    </table>
                </Panel>
            )}
            {profiles.length > 0 && (
                <Panel title="Planning profile versions">
                    <table className={TABLE}><thead className="bg-muted/50"><tr><th className={TH}>Profile</th><th className={TH}>Version</th><th className={TH}>Status</th><th className={TH}>Actions</th><th className={TH}>Modified</th></tr></thead>
                        <tbody>{profiles.map((p) => <tr key={p.id} className="border-t border-border/60"><td className={TD}><Keys value={p.stable_key} /></td><td className={TD}>v{p.version}</td><td className={TD}><StatusBadge tone={p.is_active ? "success" : "neutral"} label={p.is_active ? "Active" : "Inactive"} /></td><td className={cn(TD, "text-xs")}>{p.actions.filter((a) => a.is_active !== false).map((a) => a.action_type).join(" → ") || "—"}</td><td className={TD}>{displayDate(p.modified_on)}</td></tr>)}</tbody>
                    </table>
                </Panel>
            )}
            <Panel title="Audit log" description="SION planning audit events recorded on rule changes.">
                {audit.length ? (
                    <table className={TABLE}><thead className="bg-muted/50"><tr><th className={TH}>Timestamp</th><th className={TH}>User</th><th className={TH}>Event</th><th className={TH}>Rule</th></tr></thead>
                        <tbody>{audit.map((a) => <tr key={a.id} className="border-t border-border/60"><td className={cn(TD, "whitespace-nowrap")}>{displayDate(a.timestamp)}</td><td className={TD}>{a.username ?? "—"}</td><td className={TD}>{EVENT_LABELS[a.event] ?? a.event}</td><td className={TD}>{a.rule_id ? `#${a.rule_id}${a.rule_version ? ` v${a.rule_version}` : ""}` : "—"}</td></tr>)}</tbody>
                    </table>
                ) : <p className="p-3 text-sm text-muted-foreground">No audit events recorded for this norm.</p>}
            </Panel>
        </div>
    );
}

