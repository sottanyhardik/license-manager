import { displayValue } from "@/lib/display";

export interface FieldSpec {
    key: string;
    label: string;
}

type Props = { record: Record<string, unknown>; fields: FieldSpec[] };

/** Label/value grid for backend fields, rendered as received (no client-side computation). */
export function FieldGrid({ record, fields }: Props) {
    return (
        <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
            {fields.map((f) => (
                <div key={f.key} className="min-w-0">
                    <dt className="mb-0.5 text-[0.66rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground">{f.label}</dt>
                    <dd className="break-words text-sm font-medium text-foreground">{displayValue(record[f.key])}</dd>
                </div>
            ))}
        </dl>
    );
}
