import { ArrowDownToLine, Copy, Download, FileText, Pencil, Trash2, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { OUTLINE_TOKENS } from "@/lib/display";
import type { AllotmentCardAction } from "../types";

const ICONS: Record<string, LucideIcon> = {
    pencil: Pencil,
    copy: Copy,
    "box-arrow-in-down": ArrowDownToLine,
    "file-pdf": FileText,
    download: Download,
    trash: Trash2,
};

/** Labelled buttons for existing card actions (same handlers + gating as the card header). */
export function ActionButtons({ actions }: { actions: AllotmentCardAction[] }) {
    return (
        <div className="flex flex-wrap gap-2">
            {actions.map((a) => {
                const Icon = ICONS[a.icon];
                return (
                    <Button
                        key={a.title}
                        type="button"
                        size="sm"
                        variant={a.tone === "danger" ? "destructive" : "outline"}
                        className={a.tone === "danger" ? undefined : OUTLINE_TOKENS}
                        onClick={() => { void a.onClick(); }}
                    >
                        {Icon && <Icon aria-hidden="true" />}
                        {a.title}
                    </Button>
                );
            })}
        </div>
    );
}
