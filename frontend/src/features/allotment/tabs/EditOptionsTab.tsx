import { ActionButtons } from "./ActionButtons";
import type { AllotmentCardAction } from "../types";

/** Edit Options: exactly the card's existing actions, with the same role gating. */
export function EditOptionsTab({ actions }: { actions: AllotmentCardAction[] }) {
    return (
        <div className="space-y-2">
            <ActionButtons actions={actions} />
            {!actions.some((a) => a.title === "Edit") && (
                <p className="text-xs text-muted-foreground">Editing requires allotment write access.</p>
            )}
        </div>
    );
}
