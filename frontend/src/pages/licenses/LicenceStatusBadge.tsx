import { Ban, CircleCheck, CircleX, Circle, Clock, PauseCircle, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const GOOD = "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-200";
const BAD = "border-red-300 bg-red-50 text-red-800 dark:border-red-700 dark:bg-red-950/50 dark:text-red-200";
const WARN = "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-200";
const INFO = "border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-700 dark:bg-sky-950/50 dark:text-sky-200";
const NEUTRAL = "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200";

/**
 * Icon and colour per status code the database can produce. A code not listed here
 * still shows, with the server's label, in the neutral style, so a new status needs no change here.
 */
const STYLES: Record<string, { icon: LucideIcon; className: string }> = {
  ACTIVE: { icon: CircleCheck, className: GOOD },
  EXPIRED: { icon: CircleX, className: BAD },
  CANCELLED: { icon: Ban, className: BAD },
  SUSPENDED: { icon: PauseCircle, className: WARN },
  PENDING: { icon: Clock, className: INFO },
  INACTIVE: { icon: Circle, className: NEUTRAL },
};

const FALLBACK = { icon: Circle, className: NEUTRAL };

/** Text label from the server. Without one, the code is shown in words. */
function labelFor(code: string, label: string | null | undefined): string {
  if (label) return label;
  if (!code) return "Unknown";
  return code
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

interface LicenceStatusBadgeProps {
  code: string;
  label: string | null | undefined;
}

/** The licence's stored status: text and an icon, never colour alone. */
export default function LicenceStatusBadge({ code, label }: LicenceStatusBadgeProps) {
  const style = STYLES[code] ?? FALLBACK;
  const Icon = style.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium",
        style.className,
      )}
    >
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      {labelFor(code, label)}
    </span>
  );
}
