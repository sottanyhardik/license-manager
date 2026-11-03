import { useRef, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentedFilterProps<T extends string> {
  /** Accessible name of the radio group (also the visible label). */
  label: string;
  value: T;
  options: readonly SegmentedOption<T>[];
  onChange: (value: T) => void;
  /** Id of help text that describes the group. */
  describedBy?: string;
}

/**
 * Single-choice control built from radio buttons. Roving tabindex with
 * Left/Right arrow keys, as in a native radio group.
 */
export function SegmentedFilter<T extends string>({
  label,
  value,
  options,
  onChange,
  describedBy,
}: SegmentedFilterProps<T>) {
  const groupRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const step = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (index + step + options.length) % options.length;
    onChange(options[nextIndex].value);
    groupRef.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[nextIndex]?.focus();
  };

  return (
    <div
      ref={groupRef}
      role="radiogroup"
      aria-label={label}
      aria-describedby={describedBy}
      className="flex w-full overflow-hidden rounded-lg border border-input bg-card shadow-sm"
      style={{ height: "var(--tb-control-height-compact)" }}
    >
      {options.map((option, index) => {
        const checked = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => handleKeyDown(event, index)}
            className={cn(
              "inline-flex h-full min-w-0 flex-1 cursor-pointer items-center justify-center whitespace-nowrap px-2 text-sm font-medium outline-none transition-colors",
              "focus-visible:relative focus-visible:z-10 focus-visible:ring-[3px] focus-visible:ring-ring/40",
              index > 0 && "border-l border-input",
              checked ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-muted",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
