import type { RuleCondition } from "@/services/api/planningRuleApi";

const FIELD_LABELS: Record<string, string> = {
    HSN: "HSN",
    HSN_DIGITS: "HSN Digits",
    PRODUCT_DESCRIPTION: "Product Description",
    ITEM_KEY: "Item Key",
};

const OPERATOR_LABELS: Record<string, string> = {
    CONTAINS: "contains",
    NOT_CONTAINS: "does not contain",
    EQUALS: "equals",
    STARTS_WITH: "starts with",
    NOT_STARTS_WITH: "does not start with",
    WORD_CONTAINS: "contains word",
};

export const conditionOperator = (condition: RuleCondition): string =>
    String(condition.comparator ?? condition.operator ?? "").toUpperCase();

export function getConditionDisplay(condition: RuleCondition) {
    const field = String(condition.field ?? "").toUpperCase();
    const operator = conditionOperator(condition);
    return {
        fieldLabel: FIELD_LABELS[field] ?? `Unknown field: ${field || "(missing)"}`,
        operatorLabel: OPERATOR_LABELS[operator] ?? `Unknown operator: ${operator || "(missing)"}`,
        value: String(condition.value ?? ""),
    };
}

export function withConditionOperator(condition: RuleCondition, operator: string): RuleCondition {
    return condition.comparator !== undefined
        ? { ...condition, comparator: operator }
        : { ...condition, operator };
}

export const MATCH_FIELDS = Object.entries(FIELD_LABELS);
export const MATCH_OPERATORS = Object.entries(OPERATOR_LABELS);
