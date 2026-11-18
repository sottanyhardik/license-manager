import { describe, expect, it } from "vitest";
import type { SionNormConfiguration, SionPlanningRule } from "@/api/planningRuleApi";
import { deriveSplits, normalizeTab, ratioToPercent, toMicros, validateNormConfiguration, visibleNormTabs } from "./normConfig";

const config = (targets: Record<string, string>, productEntitlement = "OLIVE OIL"): SionNormConfiguration => ({
    sion: { id: 1, norm_class: "X1", is_active: true }, rule_versions: [], profiles: [], audit: [],
    registry: {
        source: "r",
        rules: [{ stable_key: "X1:RULE:1", name: "Split src", priority: 1, expression: { field: "HSN", comparator: "STARTS_WITH", value: "15" }, max_unit_price: "5", unit: "KG", output_key: "SRC" }],
        actions: [{ stable_key: "X1:ACTION:SPLIT", priority: 1, action_type: "SPLIT", config: { source_output: "SRC", basis: "RECORD_AVAILABLE_QUANTITY", targets } }],
        mappings: [],
    },
    entitlement_profile: {
        source: "p",
        groups: [{ key: "G", label: "Group", entitlement_items: ["PKO ITEM", "OLIVE OIL"], source_rule: "X1:RULE:1", split_action: "X1:ACTION:SPLIT", products: [{ name: "Sunflower", entitlement: productEntitlement, aliases: ["SUNFLOWER"] }] }],
        entitlements: [{ item: "PKO ITEM", label: "PKO", split_target: "A" }, { item: "OLIVE OIL", label: "Olive", split_target: "B" }],
    },
});

const rule = (over: Partial<SionPlanningRule>): SionPlanningRule => ({ id: 1, sion: 1, name: "R", expression: { operator: "AND", conditions: [{ field: "HSN", comparator: "STARTS_WITH", value: "17" }] }, max_unit_price: "2", unit: "KG", priority: 1, is_active: true, strategy: "STANDARD", import_item: 9, ...over });

describe("normConfig", () => {
    it("parses decimals exactly and formats ratios as percentages", () => {
        expect(toMicros("0.5")).toBe(500000n);
        expect(toMicros("abc")).toBeNull();
        expect(ratioToPercent("0.5")).toBe("50%");
        expect(ratioToPercent("0.333333")).toBe("33.3333%");
    });

    it("derives a registry split with products mapped to their entitlement", () => {
        const [split] = deriveSplits([], config({ A: "0.5", B: "0.5" }));
        expect(split.totalValid).toBe(true);
        expect(split.sourceRuleName).toBe("Split src");
        expect(split.targets.map((t) => [t.label, t.share, t.products])).toEqual([["PKO", "50%", []], ["Olive", "50%", ["Sunflower"]]]);
    });

    it("flags invalid split totals and unknown product entitlements", () => {
        const codes = validateNormConfiguration([], config({ A: "0.6", B: "0.5" }, "MISSING")).map((i) => i.code);
        expect(codes).toContain("SPLIT_TOTAL");
        expect(codes).toContain("MAPPING_UNKNOWN_ENTITLEMENT");
        expect(codes).toContain("REGISTRY_ONLY");
    });

    it("flags duplicate conditions and priorities among active rules", () => {
        const issues = validateNormConfiguration([rule({ id: 1, name: "A" }), rule({ id: 2, name: "B" })], null);
        expect(issues.map((i) => i.code)).toEqual(expect.arrayContaining(["DUPLICATE_CONDITIONS", "DUPLICATE_PRIORITY"]));
    });

    it("validates percentage-row splits against 100%", () => {
        const split = rule({ strategy: "SPLIT_BY_PERCENT", percentage_rows: [{ import_item: 1, percentage: "40.00", unit_price: "1" }, { import_item: 2, percentage: "60.00", unit_price: "2" }] });
        expect(deriveSplits([split], null)[0].totalValid).toBe(true);
    });

    it("reads unit-value bucket splits from the active DB profile", () => {
        const cfg = { ...config({ A: "0.5", B: "0.5" }), registry: null, entitlement_profile: null, profiles: [{ id: 1, stable_key: "P", strategy_type: "ACTION_PIPELINE", version: 1, is_active: true, modified_on: null, output_mappings: [], actions: [{ stable_key: "P:SPLIT", priority: 1, action_type: "SPLIT", is_active: true, config: { basis: "BALANCE_CIF_PER_QUANTITY", category: "MILK", buckets: [{ code: "SWP", min_price: "0.00", max_price: "1.50", reference_price: "1.50" }, { code: "DWP", min_price: "1.50", max_price: "6.50", reference_price: "6.50" }] } }] }] };
        const [split] = deriveSplits([], cfg);
        expect(split).toMatchObject({ kind: "unit_value", totalValid: true, sourceRuleName: "MILK" });
        expect(split.targets.map((t) => t.share)).toEqual(["$0.00 – $1.50", "$1.50 – $6.50"]);
        cfg.profiles[0].actions[0].config.buckets = [{ code: "A", min_price: "0", max_price: "2", reference_price: "1" }, { code: "B", min_price: "1.5", max_price: "3", reference_price: "2" }];
        expect(validateNormConfiguration([], cfg).map((i) => i.code)).toContain("SPLIT_BANDS");
    });

    it("shows only tabs with meaningful content", () => {
        expect(visibleNormTabs({ rules: [], config: null, hasSimulation: false })).toEqual(["overview", "rules", "validation"]);
        expect(visibleNormTabs({ rules: [], config: config({ A: "0.5", B: "0.5" }), hasSimulation: true })).toEqual(["overview", "rules", "split", "mapping", "validation", "simulation"]);
        expect(normalizeTab("audit")).toBe("history");
        expect(normalizeTab("nonsense")).toBe("overview");
    });
});
