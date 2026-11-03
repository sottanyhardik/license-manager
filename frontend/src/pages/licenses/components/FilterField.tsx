import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface FilterFieldProps {
  label: string;
  /** Inline validation message; announced politely. */
  error?: string | null;
  /** Explanatory text shown under the label (e.g. the ₹200 rule). */
  help?: string;
  /** Span two grid columns when the viewport allows (sm and up). */
  wide?: boolean;
  id?: string;
  children: ReactNode;
}

/** Label, control and messages for one filter. Keeps every filter cell aligned. */
export function FilterField({ label, error, help, wide = false, id, children }: FilterFieldProps) {
  const errorId = id ? `${id}-error` : undefined;
  const helpId = id ? `${id}-help` : undefined;
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", wide && "sm:col-span-2")}>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
      {help && (
        <p id={helpId} className="text-xs text-muted-foreground">
          {help}
        </p>
      )}
      {error && (
        <p id={errorId} aria-live="polite" className="text-xs font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
