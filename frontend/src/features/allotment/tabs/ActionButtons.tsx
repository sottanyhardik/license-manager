import { Button } from "@/components/ui/button";
import { OUTLINE_TOKENS } from "@/lib/display";
import type { AllotmentCardAction } from "../types";
import { ALLOTMENT_ACTION_ICONS } from "../allotmentCardActions";

const ICONS = ALLOTMENT_ACTION_ICONS;

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
