/** Filter condition tree shared by the description table and its tests — the Licence Planning rule-builder shape
 *  (`{operator: "AND" | "OR", conditions: [condition | group]}`). Evaluation happens on the server only. */

export type FilterField = "description" | "hsn" | "sion";
export type FilterOp = "contains" | "not_contains" | "starts_with" | "not_starts_with" | "ends_with" | "not_ends_with" | "equals" | "not_equals" | "empty" | "not_empty";
/** ``id``: client-only stable React key (stripped before the tree is applied / sent). */
export type Condition = { id?: string; field: FilterField; op: FilterOp; value: string };
export type FilterGroup = { id?: string; operator: "AND" | "OR"; conditions: (Condition | FilterGroup)[] };
export type Filters = FilterGroup;

export const MAX_DEPTH = 12; // same limit as the Licence Planning rule engine
export const EMPTY_FILTERS: Filters = { operator: "AND", conditions: [] };
export const FIELD_LABEL: Record<FilterField, string> = { description: "Original Product Description", hsn: "HSN Code", sion: "SION" };
export const OP_LABEL: Record<FilterOp, string> = {
    contains: "Contains", not_contains: "Does Not Contain", starts_with: "Starts With", not_starts_with: "Does Not Start With",
    ends_with: "Ends With", not_ends_with: "Does Not End With", equals: "Equals", not_equals: "Does Not Equal", empty: "Is Empty", not_empty: "Is Not Empty",
};
export const NO_VALUE: FilterOp[] = ["empty", "not_empty"];
let seq = 0;
export const nodeId = () => `f${Date.now().toString(36)}${(seq++).toString(36)}`;
export const blank = (): Condition => ({ id: nodeId(), field: "description", op: "contains", value: "" });
export const blankGroup = (): FilterGroup => ({ id: nodeId(), operator: "AND", conditions: [blank()] });
/** The tree with a stable client id on every node (for the editor's React keys). */
export const withIds = (g: FilterGroup): FilterGroup => ({
    id: g.id ?? nodeId(), operator: g.operator, conditions: g.conditions.map((c) => (isGroup(c) ? withIds(c) : { ...c, id: c.id ?? nodeId() })),
});
/** The tree without client ids — what is applied, compared and sent. */
export const stripIds = (g: FilterGroup): FilterGroup => ({
    operator: g.operator, conditions: g.conditions.map((c) => (isGroup(c) ? stripIds(c) : { field: c.field, op: c.op, value: c.value.trim() })),
});
export const isGroup = (n: Condition | FilterGroup): n is FilterGroup => "conditions" in n;

export const countConditions = (g: FilterGroup): number => g.conditions.reduce((n, c) => n + (isGroup(c) ? countConditions(c) : 1), 0);
export const validFilters = (g: FilterGroup): boolean => g.conditions.every((c) => (isGroup(c) ? validFilters(c) : NO_VALUE.includes(c.op) || !!c.value.trim()));
export const sameFilters = (a: Filters, b: Filters) => JSON.stringify(stripIds(a)) === JSON.stringify(stripIds(b));

export function describeFilters(g: FilterGroup, labels: Partial<Record<FilterField, string>> = FIELD_LABEL): string {
    const node = (n: Condition | FilterGroup): string => isGroup(n)
        ? `(${n.conditions.map(node).join(n.operator === "AND" ? " AND " : " OR ")})`
        : `${labels[n.field] ?? FIELD_LABEL[n.field]} ${OP_LABEL[n.op].toLowerCase()}${NO_VALUE.includes(n.op) ? "" : ` “${n.value}”`}`;
    return g.conditions.length ? node(g) : "";
}
