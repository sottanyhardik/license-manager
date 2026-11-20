/**
 * Pure, norm-agnostic derivations for the /planning SION workspace.
 *
 * Every value is read from the norm's actual configuration (DB rules + the
 * read-only `norm-configuration` payload). Nothing here names a norm or a
 * product; E126's PKO / Olive Oil split appears only because its registry and
 * entitlement profile declare it.
 */
import { formatDateTime } from "@/utils/dateFormatter";
import type {
    EntitlementGroupConfig, PlanningActionConfig, RegistryRule, RuleCondition, RuleGroup,
    SionNormConfiguration, SionNormSummary, SionPlanningRule,
} from "@/api/planningRuleApi";
import { hasValidationErrors, validatePlanningRule } from "../ruleFormValidation";

// ── Exact decimal arithmetic (no floats for configured percentages) ─────────
const SCALE = 1_000_000n;
const DECIMAL = /^-?\d+(?:\.\d+)?$/;

/** "0.5" → 500000n (6 dp). Returns null for anything that is not a plain decimal. */
export function toMicros(value: unknown): bigint | null {
    const text = String(value ?? "").trim();
    if (!DECIMAL.test(text)) return null;
    const negative = text.startsWith("-");
    const [whole, fraction = ""] = text.replace("-", "").split(".");
    if (fraction.length > 6) return null;
    const micros = BigInt(whole) * SCALE + BigInt(fraction.padEnd(6, "0"));
    return negative ? -micros : micros;
}

function formatMicros(micros: bigint, maxDp = 4): string {
    const negative = micros < 0n;
    const abs = negative ? -micros : micros;
    const whole = abs / SCALE;
    const fraction = (abs % SCALE).toString().padStart(6, "0").slice(0, maxDp).replace(/0+$/, "");
    return `${negative ? "-" : ""}${whole}${fraction ? `.${fraction}` : ""}`;
}

/** Ratio ("0.5") → percentage label ("50%"). */
export function ratioToPercent(ratio: unknown): string {
    const micros = toMicros(ratio);
    return micros == null ? String(ratio ?? "—") : `${formatMicros(micros * 100n)}%`;
}

/** Percentage ("50.00") → label ("50%"). */
export function percentLabel(percent: unknown): string {
    const micros = toMicros(percent);
    return micros == null ? String(percent ?? "—") : `${formatMicros(micros)}%`;
}

export function displayDate(value?: string | null): string {
    if (!value) return "Not available";
    return formatDateTime(value) || "Not available";
}

// ── Expression helpers ──────────────────────────────────────────────────────
type Node = RuleGroup | RuleCondition;
const isGroup = (node: Node): node is RuleGroup => Array.isArray((node as RuleGroup).conditions);

export function flattenConditions(node: Node | null | undefined): RuleCondition[] {
    if (!node) return [];
    return isGroup(node) ? node.conditions.flatMap((child) => flattenConditions(child)) : [node];
}

const isHsnField = (c: RuleCondition) => ["HSN", "HSN_DIGITS"].includes(String(c.field).toUpperCase());
const op = (c: RuleCondition) => String(c.comparator ?? c.operator ?? "").toUpperCase();

export function conditionSummary(node: Node | null | undefined) {
    const leaves = flattenConditions(node);
    const fmt = (c: RuleCondition) => `${op(c).replace(/_/g, " ").toLowerCase()} "${c.value}"`;
    return {
        hsn: leaves.filter(isHsnField).map(fmt),
        description: leaves.filter((c) => !isHsnField(c)).map(fmt),
        total: leaves.length,
    };
}

// ── Split configuration ─────────────────────────────────────────────────────
export interface SplitTarget {
    key: string;
    /** Display label of the target (output mapping / entitlement label / item). */
    label: string;
    share: string;
    products: string[];
    entitlement?: string;
    valuation?: string;
    rate?: string;
}
export interface SplitView {
    id: string;
    source: "registry" | "database" | "profile";
    /** percent = shares must total 100%; unit_value = price-band buckets. */
    kind: "percent" | "unit_value";
    sourceLabel: string;
    sourceRuleKey?: string | null;
    sourceRuleName?: string;
    basis?: string;
    group?: string;
    targets: SplitTarget[];
    totalShare: string;
    totalValid: boolean;
    restrictions: string[];
    quantityRule?: string;
}

const str = (value: unknown) => (value == null ? "" : String(value));

function registrySplits(config: SionNormConfiguration): SplitView[] {
    const registry = config.registry;
    if (!registry) return [];
    const groups = config.entitlement_profile?.groups ?? [];
    const entitlements = config.entitlement_profile?.entitlements ?? [];
    return registry.actions.filter((a) => a.action_type === "SPLIT").map((action) => {
        const cfg = action.config as { source_output?: string; basis?: string; targets?: Record<string, string> };
        const sourceRule: RegistryRule | undefined = registry.rules.find((r) => r.output_key === cfg.source_output);
        const group: EntitlementGroupConfig | undefined = groups.find((g) => g.split_action === action.stable_key);
        const targets = Object.entries(cfg.targets ?? {}).map(([key, ratio]) => {
            const ent = entitlements.find((e) => e.split_target === key);
            const mapping = registry.mappings.find((m) => m.source_key === key);
            return {
                key,
                label: ent?.label ?? mapping?.output_name ?? key,
                share: ratioToPercent(ratio),
                entitlement: ent?.item,
                valuation: ent?.valuation,
                rate: mapping?.rate,
                products: group?.products.filter((p) => p.entitlement === ent?.item).map((p) => p.name) ?? [],
            };
        });
        const sum = Object.values(cfg.targets ?? {}).reduce<bigint | null>((acc, v) => {
            const m = toMicros(v);
            return acc == null || m == null ? null : acc + m;
        }, 0n);
        const rebalances = registry.actions.filter((a) => a.action_type === "REBALANCE"
            && (a.config as { eligible_source?: string }).eligible_source === cfg.source_output);
        const rounding = registry.actions.find((a) => a.action_type === "ROUND");
        return {
            id: action.stable_key,
            source: "registry" as const,
            kind: "percent" as const,
            sourceLabel: action.stable_key,
            sourceRuleKey: sourceRule?.stable_key ?? group?.source_rule ?? null,
            sourceRuleName: sourceRule?.name,
            basis: cfg.basis,
            group: group?.label,
            targets,
            totalShare: sum == null ? "—" : ratioToPercent(formatMicros(sum, 6)),
            totalValid: sum === SCALE,
            restrictions: rebalances.map((r) => describeAction(r)),
            quantityRule: rounding ? describeAction(rounding) : undefined,
        };
    });
}

function databaseSplits(rules: SionPlanningRule[]): SplitView[] {
    return rules.filter((r) => r.is_active && r.strategy === "SPLIT_BY_PERCENT" && r.percentage_rows?.length).map((rule) => {
        const rows = rule.percentage_rows ?? [];
        const sum = rows.reduce<bigint | null>((acc, row) => {
            const m = toMicros(row.percentage);
            return acc == null || m == null ? null : acc + m;
        }, 0n);
        return {
            id: `rule-${rule.id}`,
            source: "database" as const,
            kind: "percent" as const,
            sourceLabel: rule.stable_key || `Rule #${rule.priority}`,
            sourceRuleKey: rule.stable_key,
            sourceRuleName: rule.name,
            basis: "Percentage rows",
            targets: rows.map((row, index) => ({
                key: `${row.import_item}-${index}`,
                label: `Item #${row.import_item}`,
                share: percentLabel(row.percentage),
                rate: row.unit_price,
                products: [],
            })),
            totalShare: sum == null ? "—" : percentLabel(formatMicros(sum, 6)),
            totalValid: sum === 100n * SCALE,
            restrictions: rows.filter((row) => row.max_quantity).map((row) => `Item #${row.import_item} capped at ${row.max_quantity} ${rule.unit}`),
        };
    });
}

type Bucket = { code?: string; min_price?: string; max_price?: string; reference_price?: string };

/** Price-band buckets ascending, contiguous and non-overlapping (exact decimals). */
function bucketsContiguous(buckets: Bucket[]): boolean {
    const bands = buckets.map((b) => [toMicros(b.min_price), toMicros(b.max_price)] as const);
    if (bands.some(([lo, hi]) => lo == null || hi == null || lo > hi)) return false;
    return bands.every(([lo], i) => i === 0 || lo === bands[i - 1][1]);
}

function bucketView(id: string, source: SplitView["source"], label: string, name: string | undefined, basis: string | undefined, buckets: Bucket[], restrictions: string[]): SplitView {
    const valid = buckets.length > 0 && bucketsContiguous(buckets);
    return {
        id, source, kind: "unit_value", sourceLabel: label, sourceRuleKey: source === "database" ? label : null, sourceRuleName: name, basis,
        targets: buckets.map((b, i) => ({ key: b.code || `band-${i + 1}`, label: b.code || `Band ${i + 1}`, share: `$${b.min_price ?? "?"} – $${b.max_price ?? "?"}`, rate: b.reference_price, products: [] })),
        totalShare: valid ? `${buckets.length} contiguous band${buckets.length === 1 ? "" : "s"}` : "Bands overlap or have gaps",
        totalValid: valid, restrictions,
    };
}

function databaseUnitValueSplits(rules: SionPlanningRule[]): SplitView[] {
    return rules.filter((r) => r.is_active && r.strategy === "SPLIT_BY_UNIT_VALUE" && r.unit_value_rows?.length).map((rule) => bucketView(
        `rule-uv-${rule.id}`, "database", rule.stable_key || `Rule #${rule.priority}`, rule.name, "Unit value rows",
        (rule.unit_value_rows ?? []).map((row) => ({ code: `Item #${row.import_item}`, min_price: row.min_unit_price, max_price: row.max_unit_price, reference_price: row.preferred_unit_price })),
        [],
    ));
}

function profileSplits(config: SionNormConfiguration): SplitView[] {
    const profile = config.profiles.find((p) => p.is_active);
    if (!profile) return [];
    return profile.actions.filter((a) => a.is_active !== false && a.action_type === "SPLIT").map((action) => {
        const cfg = action.config as { basis?: string; category?: string; buckets?: Bucket[]; targets?: Record<string, string> };
        const { basis, category, buckets, targets, ...rest } = cfg;
        const restrictions = Object.entries(rest).map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? JSON.stringify(v) : str(v)}`);
        if (buckets?.length) return bucketView(action.stable_key, "profile", action.stable_key, category, basis, buckets, restrictions);
        const sum = Object.values(targets ?? {}).reduce<bigint | null>((acc, v) => { const m = toMicros(v); return acc == null || m == null ? null : acc + m; }, 0n);
        return {
            id: action.stable_key, source: "profile" as const, kind: "percent" as const, sourceLabel: action.stable_key, sourceRuleName: category, basis,
            targets: Object.entries(targets ?? {}).map(([key, ratio]) => ({ key, label: key, share: ratioToPercent(ratio), products: [] })),
            totalShare: sum == null ? "—" : ratioToPercent(formatMicros(sum, 6)), totalValid: sum === SCALE, restrictions,
        };
    });
}

export function deriveSplits(rules: SionPlanningRule[], config: SionNormConfiguration | null): SplitView[] {
    return [...databaseSplits(rules), ...databaseUnitValueSplits(rules), ...(config ? [...profileSplits(config), ...registrySplits(config)] : [])];
}

export function describeAction(action: PlanningActionConfig): string {
    const cfg = action.config ?? {};
    const parts = Object.entries(cfg).map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? JSON.stringify(v) : str(v)}`);
    return `${action.action_type}${parts.length ? ` — ${parts.join(" · ")}` : ""}`;
}

// ── Product mapping ─────────────────────────────────────────────────────────
export interface MappingRow {
    id: string;
    source: "database" | "registry";
    ruleId?: number;
    ruleKey?: string | null;
    ruleName: string;
    priority: number;
    hsn: string[];
    description: string[];
    assignment: string;
    maxPrice: string;
    unit: string;
}

export function deriveMappingRows(rules: SionPlanningRule[], config: SionNormConfiguration | null): MappingRow[] {
    const db = rules.filter((r) => r.is_active).map((rule) => {
        const c = conditionSummary(rule.expression);
        return {
            id: `db-${rule.id}`, source: "database" as const, ruleId: rule.id, ruleKey: rule.stable_key, ruleName: rule.name,
            priority: rule.priority, hsn: c.hsn, description: c.description,
            assignment: rule.standard_item_name ?? (rule.percentage_rows?.length ? `${rule.percentage_rows.length} split rows` : rule.execution_output ?? "—"),
            maxPrice: rule.max_unit_price, unit: rule.unit,
        };
    });
    const dbKeys = new Set(rules.map((r) => r.stable_key).filter(Boolean));
    const registry = (config?.registry?.rules ?? []).filter((r) => !dbKeys.has(r.stable_key)).map((rule) => {
        const c = conditionSummary(rule.expression);
        const mapping = config?.registry?.mappings.find((m) => m.source_key === rule.output_key);
        const split = config?.registry?.actions.find((a) => a.action_type === "SPLIT" && (a.config as { source_output?: string }).source_output === rule.output_key);
        return {
            id: `reg-${rule.stable_key}`, source: "registry" as const, ruleKey: rule.stable_key, ruleName: rule.name,
            priority: rule.priority, hsn: c.hsn, description: c.description,
            assignment: mapping?.output_name ?? (split ? `Split (${split.stable_key})` : rule.output_key),
            maxPrice: rule.max_unit_price, unit: rule.unit,
        };
    });
    return [...db, ...registry].sort((a, b) => a.priority - b.priority);
}

// ── Validation ──────────────────────────────────────────────────────────────
export type IssueSeverity = "error" | "warning" | "info";
export interface ConfigIssue { severity: IssueSeverity; code: string; message: string; subject?: string }

export function validateNormConfiguration(rules: SionPlanningRule[], config: SionNormConfiguration | null): ConfigIssue[] {
    const issues: ConfigIssue[] = [];
    const active = rules.filter((r) => r.id != null && r.is_active);

    for (const rule of active) {
        const errors = validatePlanningRule(rule, { strategy: rule.strategy, import_item: rule.import_item, unit_value_rows: rule.unit_value_rows, percentage_rows: rule.percentage_rows });
        if (hasValidationErrors(errors)) {
            const messages = Object.values(errors).filter((v): v is string => typeof v === "string");
            issues.push({ severity: "error", code: "RULE_INVALID", subject: rule.name, message: messages.join(" ") || "Rule configuration is incomplete." });
        }
        if (!flattenConditions(rule.expression).length) issues.push({ severity: "error", code: "NO_CONDITIONS", subject: rule.name, message: "Rule has no match conditions." });
    }

    const byExpression = new Map<string, string[]>();
    for (const rule of active) {
        const key = JSON.stringify(rule.expression);
        byExpression.set(key, [...(byExpression.get(key) ?? []), rule.name]);
    }
    for (const names of byExpression.values()) {
        if (names.length > 1) issues.push({ severity: "warning", code: "DUPLICATE_CONDITIONS", subject: names.join(", "), message: "Rules share identical match conditions; only the first by priority can match." });
    }
    const priorities = new Map<number, number>();
    active.forEach((r) => priorities.set(r.priority, (priorities.get(r.priority) ?? 0) + 1));
    for (const [priority, count] of priorities) {
        if (count > 1) issues.push({ severity: "error", code: "DUPLICATE_PRIORITY", subject: `Priority ${priority}`, message: `${count} active rules share priority ${priority}.` });
    }

    for (const split of deriveSplits(rules, config)) {
        if (!split.totalValid) issues.push(split.kind === "percent"
            ? { severity: "error", code: "SPLIT_TOTAL", subject: split.sourceLabel, message: `Split shares total ${split.totalShare}; expected 100%.` }
            : { severity: "error", code: "SPLIT_BANDS", subject: split.sourceLabel, message: "Unit-value price bands overlap or leave gaps." });
        if (split.source === "registry" && !split.sourceRuleName) issues.push({ severity: "error", code: "SPLIT_SOURCE_MISSING", subject: split.sourceLabel, message: "No registry rule produces the split's source output." });
    }

    for (const group of config?.entitlement_profile?.groups ?? []) {
        for (const product of group.products) {
            if (!group.entitlement_items.includes(product.entitlement)) {
                issues.push({ severity: "error", code: "MAPPING_UNKNOWN_ENTITLEMENT", subject: `${group.label}: ${product.name}`, message: `Mapped to ${product.entitlement}, which is not an entitlement of this group.` });
            }
        }
        const aliasOwners = new Map<string, Set<string>>();
        group.products.forEach((p) => p.aliases.forEach((a) => aliasOwners.set(a.toUpperCase(), new Set([...(aliasOwners.get(a.toUpperCase()) ?? []), p.entitlement]))));
        for (const [alias, owners] of aliasOwners) {
            if (owners.size > 1) issues.push({ severity: "warning", code: "MAPPING_AMBIGUOUS_ALIAS", subject: `${group.label}: ${alias}`, message: "Alias maps to more than one entitlement; such debits are reported as ambiguous." });
        }
        if (group.split_action && !config?.registry?.actions.some((a) => a.stable_key === group.split_action)) {
            issues.push({ severity: "error", code: "MAPPING_SPLIT_MISSING", subject: group.label, message: `Split action ${group.split_action} is not declared in the registry.` });
        }
    }

    if (!active.length) {
        issues.push(config?.registry
            ? { severity: "info", code: "REGISTRY_ONLY", message: "No active database rules; the code registry configuration is shown read-only. Preview Impact and planning need saved database rules." }
            : { severity: "warning", code: "NO_RULES", message: "No active planning rules are configured for this norm." });
    }
    return issues;
}

// ── Tabs (configuration-driven) ─────────────────────────────────────────────
export type NormTabId = "overview" | "rules" | "split" | "mapping" | "validation" | "history" | "simulation";

export function visibleNormTabs(args: {
    rules: SionPlanningRule[]; config: SionNormConfiguration | null; summary?: SionNormSummary; hasSimulation: boolean;
}): NormTabId[] {
    const { rules, config, summary, hasSimulation } = args;
    const tabs: NormTabId[] = ["overview", "rules"];
    const hasSplit = deriveSplits(rules, config).length > 0 || !!summary?.split_rule_count || !!summary?.registry_split_count || !!summary?.profile_split_count;
    if (hasSplit) tabs.push("split");
    if (rules.length || config?.registry?.rules.length || config?.entitlement_profile) tabs.push("mapping");
    tabs.push("validation");
    if (config && (config.rule_versions.length || config.profiles.length || config.audit.length)) tabs.push("history");
    if (hasSimulation) tabs.push("simulation");
    return tabs;
}

/** Legacy `?view=` values keep working. */
export function normalizeTab(value: string | null | undefined): NormTabId {
    const v = String(value ?? "").toLowerCase();
    if (v === "versions" || v === "audit") return "history";
    return (["overview", "rules", "split", "mapping", "validation", "history", "simulation"] as const).find((t) => t === v) ?? "overview";
}

export const TAB_LABELS: Record<NormTabId, string> = {
    overview: "Overview", rules: "Rules", split: "Split Configuration", mapping: "Product Mapping",
    validation: "Validation", history: "Version History", simulation: "Simulation",
};
