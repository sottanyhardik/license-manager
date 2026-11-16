import { useState } from "react";
import { Loader2, Plus, X } from "lucide-react";

import AsyncSelectField from "@/components/AsyncSelectField";
import ConditionBadge from "@/components/ConditionBadge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { LICENSE_MARKING_OPTIONS, useLicenceModalEdits } from "./useLicenceModalParity";

export type ItemTag = { id: number; name: string };

interface ItemTagsEditorProps {
    licenseId: string | number;
    itemId: number;
    tags: ItemTag[];
    /** `get_norm_class` from `licenses/:id/`; filters the search like the modal. */
    normClass?: string | null;
}

/** Port of the modal's add/remove item-tag chips (`PATCH license-items/:id/ { items }`). Writer-only. */
export function ItemTagsEditor({ licenseId, itemId, tags, normClass }: ItemTagsEditorProps) {
    const { saveItemTags } = useLicenceModalEdits(licenseId);
    const [adding, setAdding] = useState(false);
    const [saving, setSaving] = useState(false);
    const endpoint = `masters/item-names/${normClass ? `?norm_class=${encodeURIComponent(normClass)}` : ""}`;

    const save = async (ids: number[]) => {
        setSaving(true);
        await saveItemTags(itemId, ids);
        setSaving(false);
    };
    const handleRemove = (tagId: number) => void save(tags.filter((t) => t.id !== tagId).map((t) => t.id));
    const handleAdd = (value: unknown) => {
        setAdding(false);
        if (typeof value !== "number" || tags.some((t) => t.id === value)) return;
        void save([...tags.map((t) => t.id), value]);
    };

    return (
        <div className="mt-1 flex flex-wrap items-center gap-1" aria-label="Item tags">
            {tags.map((tag) => (
                <span key={tag.id} className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-[11px]">
                    {tag.name}
                    <button
                        type="button"
                        onClick={() => handleRemove(tag.id)}
                        disabled={saving}
                        aria-label={`Remove ${tag.name}`}
                        className="rounded text-muted-foreground hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                    >
                        <X className="size-3" aria-hidden="true" />
                    </button>
                </span>
            ))}
            {adding ? (
                <div className="min-w-[220px]" onKeyDown={(e) => { if (e.key === "Escape") setAdding(false); }}>
                    <AsyncSelectField
                        endpoint={endpoint}
                        value={null}
                        onChange={handleAdd}
                        placeholder="Add item…"
                        className="react-select-sm"
                        ariaLabel="Add item tag"
                        isClearable={false}
                    />
                </div>
            ) : (
                <Button variant="outline" size="sm" className="h-6 px-1.5 text-[11px]" onClick={() => setAdding(true)} disabled={saving}>
                    <Plus className="size-3" aria-hidden="true" /> Add
                </Button>
            )}
            {saving && <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-label="Saving item tags" />}
        </div>
    );
}

const NONE = "__none__";

interface MarkingProps {
    licenseId: string | number;
    itemId: number;
    value: string | null | undefined;
    canEdit: boolean;
    label: string;
}

/** Port of the modal's License Marking select (`PATCH license-items/:id/ { condition_type }`). */
export function LicenceMarkingControl({ licenseId, itemId, value, canEdit, label }: MarkingProps) {
    const { saveItemMarking } = useLicenceModalEdits(licenseId);
    const [saving, setSaving] = useState(false);
    const current = value || "";

    if (!canEdit) return value ? <ConditionBadge type={value} size="xs" /> : <span className="text-muted-foreground">—</span>;

    const handleChange = async (next: string) => {
        const conditionType = next === NONE ? "" : next;
        if (conditionType === current) return;
        setSaving(true);
        await saveItemMarking(itemId, conditionType);
        setSaving(false);
    };

    return (
        <Select value={current || NONE} onValueChange={(v) => void handleChange(v)} disabled={saving}>
            <SelectTrigger size="sm" className="h-8 w-[110px] text-xs" aria-label={label}>
                <SelectValue />
            </SelectTrigger>
            <SelectContent>
                {LICENSE_MARKING_OPTIONS.map((o) => (
                    <SelectItem key={o.label} value={o.value || NONE}>{o.label}</SelectItem>
                ))}
            </SelectContent>
        </Select>
    );
}
