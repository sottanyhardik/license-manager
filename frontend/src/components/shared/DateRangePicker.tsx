import { useId } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface DateRange { from?: string; to?: string }
export interface DatePreset { id: string; label: string; range: () => DateRange }

export interface DateRangePickerProps {
    label: string;
    value: DateRange;
    onChange: (v: DateRange) => void;
    presets?: DatePreset[];
    min?: string;
    max?: string;
    className?: string;
}

const normalise = (r: DateRange): DateRange => {
    const out: DateRange = {};
    if (r.from) out.from = r.from;
    if (r.to) out.to = r.to;
    return out;
};

/** From/to ISO (YYYY-MM-DD) dates using native inputs. Emits nothing when from > to. */
export function DateRangePicker({ label, value, onChange, presets, min, max, className }: DateRangePickerProps) {
    const errId = useId();
    const invalid = !!value.from && !!value.to && value.from > value.to;
    const update = (patch: DateRange) => {
        const next = normalise({ ...value, ...patch });
        if (next.from && next.to && next.from > next.to) return; // blocked; caller keeps previous value
        onChange(next);
    };
    return (
        <fieldset className={cn("min-w-0", className)}>
            <legend className="mb-1 text-xs font-medium text-muted-foreground">{label}</legend>
            <div className="flex flex-wrap items-center gap-2">
                <Input type="date" aria-label={`${label} from`} min={min} max={max} value={value.from ?? ""}
                    aria-invalid={invalid || undefined} aria-describedby={invalid ? errId : undefined}
                    onChange={(e) => update({ from: e.target.value || undefined })} className="w-auto" />
                <span aria-hidden="true" className="text-muted-foreground">–</span>
                <Input type="date" aria-label={`${label} to`} min={min} max={max} value={value.to ?? ""}
                    aria-invalid={invalid || undefined}
                    onChange={(e) => update({ to: e.target.value || undefined })} className="w-auto" />
            </div>
            {presets && presets.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                    {presets.map((p) => {
                        const r = normalise(p.range());
                        const pressed = (r.from ?? "") === (value.from ?? "") && (r.to ?? "") === (value.to ?? "");
                        return (
                            <button key={p.id} type="button" aria-pressed={pressed} onClick={() => onChange(r)}
                                className={cn("rounded-md border px-2 py-0.5 text-xs cursor-pointer focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
                                    pressed ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
                                {p.label}
                            </button>
                        );
                    })}
                </div>
            )}
            {invalid && <p id={errId} role="alert" className="mt-1 text-xs text-destructive">From date must not be after to date.</p>}
        </fieldset>
    );
}
