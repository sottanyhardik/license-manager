import { describe, expect, it } from "vitest";
import { validatePlanningRule } from "./ruleFormValidation";

const rule = {
    id: 3, sion: 1, name: "003 MILK PRODUCTS", expression: { operator: "AND" as const, conditions: [] },
    max_unit_price: "6.50", unit: "KG", priority: 1, is_active: true,
};

describe("unit-value rule validation", () => {
    it("accepts zero preferred prices and reverse-entered touching ranges", () => {
        const errors = validatePlanningRule(rule, {
            strategy: "SPLIT_BY_UNIT_VALUE",
            unit_value_rows: [
                { import_item: 269, min_unit_price: "1.5", max_unit_price: "6.50", preferred_unit_price: "0" },
                { import_item: 141, min_unit_price: "0", max_unit_price: "1.50", preferred_unit_price: "0" },
            ],
        });

        expect(errors).toEqual({});
    });

    it("shows an actionable overlap error without floating-point comparisons", () => {
        const errors = validatePlanningRule(rule, {
            strategy: "SPLIT_BY_UNIT_VALUE",
            unit_value_rows: [
                { import_item: 269, min_unit_price: "1.49", max_unit_price: "6.50", preferred_unit_price: "0" },
                { import_item: 141, min_unit_price: "0", max_unit_price: "1.50", preferred_unit_price: "0" },
            ],
        });

        expect(errors.unit_value_rows).toBe("Price ranges overlap");
    });
});

describe("split-by-percent rule validation", () => {
    it("rejects rows that total 100% only before 2-decimal rounding", () => {
        const errors = validatePlanningRule(rule, {
            strategy: "SPLIT_BY_PERCENT",
            percentage_rows: [
                { import_item: 1, percentage: "33.333", unit_price: "1" },
                { import_item: 2, percentage: "33.333", unit_price: "1" },
                { import_item: 3, percentage: "33.334", unit_price: "1" },
            ],
        });

        expect(errors.percentage_rows).toBe("Percentages must total 100%");
    });

    it("accepts rows that total exactly 100% at 2 decimals", () => {
        const errors = validatePlanningRule(rule, {
            strategy: "SPLIT_BY_PERCENT",
            percentage_rows: [
                { import_item: 1, percentage: "33.33", unit_price: "1" },
                { import_item: 2, percentage: "33.33", unit_price: "1" },
                { import_item: 3, percentage: "33.34", unit_price: "1" },
            ],
        });

        expect(errors.percentage_rows).toBeUndefined();
    });
});
