import { useState, type KeyboardEvent } from "react";
import { Check, Loader2, Pencil, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import AsyncSelectField from "@/components/AsyncSelectField";

interface InlineNormEditorProps {
    isEditing: boolean;
    selectedId: number | null;
    onSelectedIdChange: (id: number | null) => void;
    onEditStart: () => void;
    onSave: () => void;
    onCancel: () => void;
    saving: boolean;
    /** Gates the whole affordance — `hasRole("LICENSE_MANAGER")` AND the
     * license actually has an export row to attach a norm to. */
    canEdit: boolean;
}

/**
 * Inline edit control for the license's SION Norm
 * (`export_license[0].norm_class`). Reuses the SAME searchable async combobox
 * (`AsyncSelectField`, `/masters/sion-classes/`) already used for the "Norm
 * Class" field on the export item row in the Masters License edit form
 * (`NestedFieldArray.tsx`) — same look, same search-as-you-type behavior,
 * same component — rather than a separate shadcn `Select` populated from a
 * hand-fetched list.
 *
 * `?is_active=true` restricts the SEARCH RESULTS to active norms only. A
 * license already pointing at an inactive norm still shows/keeps it
 * correctly: `AsyncSelectField` resolves the currently-selected value via a
 * direct `/masters/sion-classes/{id}/` detail lookup (see its
 * `fetchOptionById`), which bypasses the `is_active` query filter entirely —
 * so an existing inactive selection displays and round-trips fine, it's only
 * excluded from *new* search results.
 */
export default function InlineNormEditor({
    isEditing,
    selectedId,
    onSelectedIdChange,
    onEditStart,
    onSave,
    onCancel,
    saving,
    canEdit,
}: InlineNormEditorProps) {
    // Tracks the combobox's own open/closed state so a single Enter keypress
    // that merely picks a highlighted option (closing the menu) isn't also
    // read as "submit the whole edit" — a second, later Enter (menu already
    // closed) is what actually saves. Mirrors the two-step interaction the
    // Purchase Status / previous shadcn-Select version already used.
    const [menuOpen, setMenuOpen] = useState(false);

    if (!canEdit) return null;

    if (!isEditing) {
        return (
            <Button variant="outline" size="sm" onClick={onEditStart} aria-label="Edit SION norm">
                <Pencil className="size-3.5" aria-hidden="true" />
                Edit
            </Button>
        );
    }

    const handleWrapperKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
        if (saving) return;
        if (e.key === "Escape") {
            e.preventDefault();
            onCancel();
        } else if (e.key === "Enter" && !menuOpen) {
            e.preventDefault();
            if (selectedId != null) onSave();
        }
    };

    return (
        <div className="flex items-center gap-2" onKeyDown={handleWrapperKeyDown}>
            <AsyncSelectField
                endpoint="/masters/sion-classes/?is_active=true"
                labelField="label"
                valueField="id"
                value={selectedId}
                onChange={(val: unknown) => onSelectedIdChange(typeof val === "number" ? val : null)}
                isClearable={false}
                isDisabled={saving}
                placeholder="Search SION norm…"
                className="w-64 react-select-sm"
                ariaLabel="SION norm class"
                onMenuOpen={() => setMenuOpen(true)}
                onMenuClose={() => setMenuOpen(false)}
            />
            <Button
                size="icon"
                className="size-8"
                onClick={onSave}
                disabled={saving || selectedId == null}
                aria-label="Save SION norm"
            >
                {saving ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Check className="size-4" aria-hidden="true" />}
            </Button>
            <Button
                variant="ghost"
                size="icon"
                className="size-8"
                onClick={onCancel}
                disabled={saving}
                aria-label="Cancel editing SION norm"
            >
                <X className="size-4" aria-hidden="true" />
            </Button>
        </div>
    );
}
