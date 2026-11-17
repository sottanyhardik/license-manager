import { AlertTriangle } from "lucide-react";

type Props = {
    index: number;
    override: boolean;
    reason: string;
    warnings?: string[];
    onOverrideChange: (checked: boolean) => void;
    onReasonChange: (text: string) => void;
};

/**
 * T1: explicit manual-amount toggle (+ required reason) for one trade line, and
 * T4: non-blocking CIF INR warnings returned by the server for that line.
 */
export default function TradeLineAmountOverride({ index, override, reason, warnings, onOverrideChange, onReasonChange }: Props) {
    const checkboxId = `amount-override-${index}`;
    const reasonId = `amount-override-reason-${index}`;
    return (
        <div className="mt-1 space-y-1 text-left">
            <label htmlFor={checkboxId} className="flex items-center gap-1 text-[11px] text-muted-foreground">
                <input
                    id={checkboxId}
                    type="checkbox"
                    checked={override}
                    onChange={(e) => onOverrideChange(e.target.checked)}
                />
                Manual amount
            </label>
            {override && (
                <input
                    id={reasonId}
                    type="text"
                    required
                    maxLength={255}
                    aria-label={`Reason for manual amount, line ${index + 1}`}
                    aria-required="true"
                    aria-invalid={!reason.trim()}
                    className="flex h-7 w-full rounded-md border border-input bg-card px-2 py-1 text-xs outline-none focus-visible:border-ring"
                    value={reason}
                    onChange={(e) => onReasonChange(e.target.value)}
                    placeholder="Reason (required)"
                />
            )}
            {warnings && warnings.length > 0 && (
                <ul className="space-y-0.5" aria-label={`Warnings, line ${index + 1}`}>
                    {warnings.map((w, i) => (
                        // AA-safe warning text token (--tb-warning-text), not the fill colour.
                        <li key={`${i}-${w}`} className="flex items-start gap-1 text-[11px] text-[color:var(--tb-warning-text)]">
                            <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
                            <span>{w}</span>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
