import { useState } from "react";
import { Circle, CircleArrowDown, CircleCheck, CircleQuestionMark, OctagonX, Ruler, TriangleAlert, type LucideIcon } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { describeFlag, statusDisplay, type StatusIconName, type StatusTone } from "./labels";

const ICONS: Record<StatusIconName, LucideIcon> = {
  check: CircleCheck,
  warning: TriangleAlert,
  down: CircleArrowDown,
  help: CircleQuestionMark,
  stop: OctagonX,
  ruler: Ruler,
  neutral: Circle,
};

const TONE_CLASSES: Record<StatusTone, string> = {
  good: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-200",
  warn: "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-200",
  bad: "border-red-300 bg-red-50 text-red-800 dark:border-red-700 dark:bg-red-950/50 dark:text-red-200",
  info: "border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-700 dark:bg-sky-950/50 dark:text-sky-200",
  neutral: "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200",
};

/** Status shown as text plus an icon, never colour alone. */
export function StatusPill({ status }: { status: string | null | undefined }) {
  const display = statusDisplay(status);
  const Icon = ICONS[display.icon];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium",
        TONE_CLASSES[display.tone],
      )}
    >
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      {display.label}
    </span>
  );
}

interface StatusReasonsButtonProps {
  status: string;
  flags: string[];
  /** Name of the licence or item the status belongs to, used in the accessible name and dialog. */
  subject: string;
}

/** The status pill as a button that explains its flags in a dialog. */
export function StatusReasonsButton({ status, flags, subject }: StatusReasonsButtonProps) {
  const [open, setOpen] = useState(false);
  const display = statusDisplay(status);

  return (
    <>
      <button
        type="button"
        aria-haspopup="dialog"
        aria-label={`${display.label}: show reasons for ${subject}`}
        onClick={() => setOpen(true)}
        className="rounded-full outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 cursor-pointer"
      >
        <StatusPill status={status} />
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Status reasons</DialogTitle>
            <DialogDescription>
              {subject}: {display.label}
            </DialogDescription>
          </DialogHeader>
          {flags.length === 0 ? (
            <p className="text-sm text-muted-foreground">No review flags are recorded for this status.</p>
          ) : (
            <ul className="space-y-3 text-sm">
              {flags.map((code) => {
                const flag = describeFlag(code);
                return (
                  <li key={code} className="rounded-md border bg-muted/30 p-3">
                    <p>{flag.text}</p>
                    {flag.known ? <p className="mt-1 font-mono text-xs text-muted-foreground">{flag.code}</p> : null}
                  </li>
                );
              })}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
