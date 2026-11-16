import { FileText, Layers, Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";

import { OUTLINE_TOKENS } from "@/lib/display";

type Props = {
    canWrite: boolean;
    onEdit: () => void;
    onTransferLetter: () => void;
    onMerge: () => void;
};

/** Existing card actions only, same handlers and gating (Edit is BOE_MANAGER only). */
export function EditOptionsTab({ canWrite, onEdit, onTransferLetter, onMerge }: Props) {
    return (
        <div className="flex flex-wrap gap-2">
            {canWrite && (
                <Button type="button" size="sm" variant="outline" className={OUTLINE_TOKENS} onClick={onEdit}>
                    <Pencil aria-hidden="true" />
                    Edit BOE
                </Button>
            )}
            <Button type="button" size="sm" variant="outline" className={OUTLINE_TOKENS} onClick={onTransferLetter}>
                <FileText aria-hidden="true" />
                Generate Transfer Letter
            </Button>
            <Button type="button" size="sm" variant="outline" className={OUTLINE_TOKENS} onClick={onMerge}>
                <Layers aria-hidden="true" />
                Merge with duplicate BOE
            </Button>
        </div>
    );
}
