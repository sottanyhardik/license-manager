import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { normaliseDecimal } from "../licenseListFilters";

export const NUMBER_COMMIT_DELAY_MS = 500;

export interface NumberRange {
  min: string;
  max: string;
}

interface NumberRangeFieldProps {
  /** Noun used in accessible names, e.g. "Balance CIF". */
  label: string;
  min: string;
  max: string;
  /** Error from the URL state. */
  error?: string | null;
  /** Called with a valid, changed range 500 ms after the last edit. */
  onCommit: (range: NumberRange) => void;
}

const FORMAT_MESSAGE = "Enter an amount with at most 2 decimal places.";
const ORDER_MESSAGE = "Minimum must be less than or equal to maximum.";

/**
 * Min and max amounts (2 dp). Invalid or out-of-order values show an inline
 * error and are never committed. Valid edits commit after a 500 ms pause.
 */
export function NumberRangeField({ label, min, max, error, onCommit }: NumberRangeFieldProps) {
  const [draft, setDraft] = useState<NumberRange>({ min, max });
  const [synced, setSynced] = useState<NumberRange>({ min, max });
  if (synced.min !== min || synced.max !== max) {
    setSynced({ min, max });
    setDraft({ min, max });
  }

  const onCommitRef = useRef(onCommit);
  useEffect(() => {
    onCommitRef.current = onCommit;
  });

  const minValue = draft.min.trim() === "" ? "" : normaliseDecimal(draft.min);
  const maxValue = draft.max.trim() === "" ? "" : normaliseDecimal(draft.max);
  const formatError = minValue === null || maxValue === null ? FORMAT_MESSAGE : null;
  const orderError =
    formatError === null && minValue !== "" && maxValue !== "" && Number(minValue) > Number(maxValue) ? ORDER_MESSAGE : null;
  const message = formatError ?? orderError ?? error ?? null;
  const valid = formatError === null && orderError === null;
  const errorId = `${label.replace(/\s+/g, "-").toLowerCase()}-error`;

  useEffect(() => {
    if (!valid) return;
    const nextMin = minValue ?? "";
    const nextMax = maxValue ?? "";
    if (nextMin === min && nextMax === max) return;
    const timer = setTimeout(() => onCommitRef.current({ min: nextMin, max: nextMax }), NUMBER_COMMIT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [valid, minValue, maxValue, min, max]);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-2 gap-2">
        <Input
          type="text"
          inputMode="decimal"
          aria-label={`${label} minimum (₹)`}
          placeholder="Min ₹"
          value={draft.min}
          aria-invalid={message ? true : undefined}
          aria-describedby={message ? errorId : undefined}
          onChange={(event) => setDraft({ min: event.target.value, max: draft.max })}
        />
        <Input
          type="text"
          inputMode="decimal"
          aria-label={`${label} maximum (₹)`}
          placeholder="Max ₹"
          value={draft.max}
          aria-invalid={message ? true : undefined}
          aria-describedby={message ? errorId : undefined}
          onChange={(event) => setDraft({ min: draft.min, max: event.target.value })}
        />
      </div>
      {message && (
        <p id={errorId} aria-live="polite" className="text-xs font-medium text-destructive">
          {message}
        </p>
      )}
    </div>
  );
}
