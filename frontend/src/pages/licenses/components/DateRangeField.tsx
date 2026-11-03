import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface DateRange {
  from: string;
  to: string;
}

interface DateRangeFieldProps {
  /** Noun used in accessible names, e.g. "Licence date". */
  label: string;
  from: string;
  to: string;
  /** Error from the URL state (e.g. a stored range that is out of order). */
  error?: string | null;
  /** Called only with a valid range (from <= to, or one/both empty). */
  onCommit: (range: DateRange) => void;
}

/**
 * Two native date inputs. A change commits immediately when the range is
 * valid; an out-of-order range shows an inline error and is not committed.
 */
export function DateRangeField({ label, from, to, error, onCommit }: DateRangeFieldProps) {
  const [draft, setDraft] = useState<DateRange>({ from, to });
  const [synced, setSynced] = useState<DateRange>({ from, to });
  if (synced.from !== from || synced.to !== to) {
    setSynced({ from, to });
    setDraft({ from, to });
  }

  const localError = draft.from !== "" && draft.to !== "" && draft.from > draft.to ? "From must be on or before To." : null;
  const message = localError ?? error ?? null;
  const errorId = `${label.replace(/\s+/g, "-").toLowerCase()}-error`;

  const update = (next: DateRange) => {
    setDraft(next);
    if (next.from !== "" && next.to !== "" && next.from > next.to) return;
    if (next.from === from && next.to === to) return;
    onCommit(next);
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-[1fr_1fr_auto] items-center gap-2">
        <Input
          type="date"
          aria-label={`${label} from`}
          value={draft.from}
          max={draft.to || undefined}
          aria-invalid={message ? true : undefined}
          aria-describedby={message ? errorId : undefined}
          onChange={(event) => update({ from: event.target.value, to: draft.to })}
        />
        <Input
          type="date"
          aria-label={`${label} to`}
          value={draft.to}
          min={draft.from || undefined}
          aria-invalid={message ? true : undefined}
          aria-describedby={message ? errorId : undefined}
          onChange={(event) => update({ from: draft.from, to: event.target.value })}
        />
        <Button
          type="button"
          variant="ghost"
          aria-label={`Clear ${label}`}
          disabled={draft.from === "" && draft.to === ""}
          onClick={() => update({ from: "", to: "" })}
          className="px-2"
        >
          Clear
        </Button>
      </div>
      {message && (
        <p id={errorId} aria-live="polite" className="text-xs font-medium text-destructive">
          {message}
        </p>
      )}
    </div>
  );
}
