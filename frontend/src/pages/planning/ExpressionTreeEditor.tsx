import { useState } from "react";
import { ChevronDown, ChevronRight, MoreHorizontal, Plus, Trash2, X } from "lucide-react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/button";
import type { RuleCondition, RuleGroup } from "@/services/api/planningRuleApi";
import { conditionOperator, defaultOperatorForPlanningField, operatorsForPlanningField, PLANNING_MATCH_FIELDS, withConditionOperator } from "./ruleConditionDisplay";
import { emptyRuleCondition } from "./expressionTreeUtils";

const isGroup = (node: RuleCondition | RuleGroup): node is RuleGroup => "conditions" in node;

const descendantCount = (group: RuleGroup): number => group.conditions.reduce(
    (total, node) => total + (isGroup(node) ? descendantCount(node) : 1),
    0,
);

type ExpressionTreeEditorProps = {
    group: RuleGroup;
    onChange: (group: RuleGroup) => void;
    ruleName?: string;
};

type GroupNodeProps = ExpressionTreeEditorProps & {
    depth: number;
    onRemove?: () => void;
};

function GroupNode({ group, onChange, ruleName, depth, onRemove }: GroupNodeProps) {
    const isRoot = depth === 0;
    const [expanded, setExpanded] = useState(true);
    const [confirmation, setConfirmation] = useState<"all" | "group" | null>(null);
    const itemCount = descendantCount(group);

    const replace = (index: number, node: RuleCondition | RuleGroup) => onChange({
        ...group,
        conditions: group.conditions.map((current, currentIndex) => currentIndex === index ? node : current),
    });
    const removeAt = (index: number) => onChange({
        ...group,
        conditions: group.conditions.filter((_, currentIndex) => currentIndex !== index),
    });

    return <div
        className={isRoot ? "space-y-2" : "border-l border-border pl-3"}
        data-expression-group={isRoot ? "root" : "nested"}
    >
        <div className="flex min-h-9 items-center gap-2 rounded-md bg-muted/45 px-2 py-1">
            {!isRoot && <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7 shrink-0"
                aria-label={`${expanded ? "Collapse" : "Expand"} ${group.operator === "AND" ? "ALL" : "ANY"} group`}
                aria-expanded={expanded}
                onClick={() => setExpanded((current) => !current)}
            >{expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}</Button>}
            <select
                aria-label={isRoot ? "Rule logic" : "Nested group logic"}
                value={group.operator}
                onChange={(event) => onChange({ ...group, operator: event.target.value as RuleGroup["operator"] })}
                className="h-8 rounded-md border bg-background px-2 text-xs font-semibold"
            >
                <option value="AND">ALL (AND)</option>
                <option value="OR">ANY (OR)</option>
            </select>
            <span className="text-xs text-muted-foreground">
                {itemCount} {itemCount === 1 ? "condition" : "conditions"}
            </span>
            <div className="ml-auto flex items-center gap-1">
                <Button type="button" size="sm" variant="ghost" className="h-8" onClick={() => onChange({ ...group, conditions: [...group.conditions, emptyRuleCondition()] })}>
                    <Plus className="size-3.5" />Condition
                </Button>
                <Button type="button" size="sm" variant="ghost" className="h-8" onClick={() => onChange({ ...group, conditions: [...group.conditions, { operator: "AND", conditions: [emptyRuleCondition()] }] })}>
                    <Plus className="size-3.5" />Group
                </Button>
                {isRoot ? group.conditions.length > 0 && <details className="relative"><summary className="flex size-8 cursor-pointer list-none items-center justify-center rounded-md hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label="More match rule actions"><MoreHorizontal className="size-4" /></summary><div className="absolute right-0 z-20 mt-1 w-56 rounded-md border bg-popover p-1 shadow-md"><button type="button" aria-label="Remove All Match Rules" className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-destructive hover:bg-accent" onClick={() => setConfirmation("all")}><Trash2 className="size-4" />Clear All Match Conditions</button></div></details> : <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="size-8 text-muted-foreground hover:text-destructive"
                    aria-label="Remove Group"
                    onClick={() => group.conditions.length ? setConfirmation("group") : onRemove?.()}
                ><Trash2 className="size-4" /></Button>}
            </div>
        </div>

        {(isRoot || expanded) && <div className="space-y-2">
            {group.conditions.map((node, index) => isGroup(node)
                ? <GroupNode
                    key={index}
                    group={node}
                    depth={depth + 1}
                    ruleName={ruleName}
                    onChange={(next) => replace(index, next)}
                    onRemove={() => removeAt(index)}
                />
                : <div key={index} className="grid min-h-10 items-center gap-2 border-l border-border pl-3 sm:grid-cols-[minmax(130px,0.8fr)_minmax(150px,0.9fr)_minmax(180px,1.5fr)_32px]">
                    <select aria-label={`Condition ${index + 1} field`} value={node.field} onChange={(event) => { const field = event.target.value; replace(index, withConditionOperator({ ...node, field }, defaultOperatorForPlanningField(field))); }} className="h-9 rounded-md border bg-background px-2 text-sm">
                        {PLANNING_MATCH_FIELDS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                    <select aria-label={`Condition ${index + 1} comparator`} value={conditionOperator(node)} onChange={(event) => replace(index, withConditionOperator(node, event.target.value))} className="h-9 rounded-md border bg-background px-2 text-sm">
                        {operatorsForPlanningField(node.field).map(([value, label]) => <option key={value} value={value}>{label.charAt(0).toUpperCase() + label.slice(1)}</option>)}
                    </select>
                    <input aria-label={`Condition ${index + 1} value`} value={node.value} onChange={(event) => replace(index, { ...node, value: event.target.value })} className="h-9 min-w-0 rounded-md border bg-background px-2 text-sm" />
                    <Button type="button" size="icon" variant="ghost" className="size-8 text-muted-foreground hover:text-destructive" aria-label={`Remove condition ${index + 1}`} onClick={() => removeAt(index)}>
                        <X className="size-4" />
                    </Button>
                </div>)}
            {!group.conditions.length && <div className="rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
                No match conditions defined. This rule currently matches no items.
            </div>}
        </div>}

        <ConfirmDialog show={confirmation === "all"} title="Remove all match rules?" message={`This will remove every condition and nested AND/OR group from "${ruleName || "this rule"}". The planning rule itself, price, unit and priority will remain. Save to persist the change.`} severity="danger" confirmText="Remove All" onConfirm={() => { onChange({ operator: "AND", conditions: [] }); setConfirmation(null); }} onCancel={() => setConfirmation(null)} />
        <ConfirmDialog show={confirmation === "group"} title="Remove populated group?" message="This removes the group and every condition or nested group inside it." severity="danger" confirmText="Remove Group" onConfirm={() => { onRemove?.(); setConfirmation(null); }} onCancel={() => setConfirmation(null)} />
    </div>;
}

export function ExpressionTreeEditor(props: ExpressionTreeEditorProps) {
    return <section aria-label="Match rules" className="space-y-2">
        <h3 className="text-sm font-semibold">Match logic</h3>
        <GroupNode {...props} depth={0} />
    </section>;
}
