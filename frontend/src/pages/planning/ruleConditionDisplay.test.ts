import { describe, expect, it } from "vitest";
import { getConditionDisplay } from "./ruleConditionDisplay";

describe("canonical planning condition labels", () => {
    it.each([
        ["HSN", "CONTAINS", "1803", "HSN contains 1803"],
        ["HSN", "NOT_CONTAINS", "0404", "HSN does not contain 0404"],
        ["PRODUCT_DESCRIPTION", "CONTAINS", "1803", "Product Description contains 1803"],
        ["PRODUCT_DESCRIPTION", "NOT_CONTAINS", "0404", "Product Description does not contain 0404"],
    ])("renders %s %s without changing its meaning", (field, operator, value, expected) => {
        const display = getConditionDisplay({ field, operator, value });
        expect(`${display.fieldLabel} ${display.operatorLabel} ${display.value}`).toBe(expected);
    });

    it("does not turn unknown enums into valid business labels", () => {
        const display = getConditionDisplay({ field: "MYSTERY", operator: "ALIEN", value: "x" });
        expect(display.fieldLabel).toBe("Unknown field: MYSTERY");
        expect(display.operatorLabel).toBe("Unknown operator: ALIEN");
    });
});
