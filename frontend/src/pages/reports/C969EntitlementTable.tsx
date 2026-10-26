import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { TOTAL_SUMMARY_TITLE } from "./itemPivotReportUtils";

// Flat C969 entitlement table: one row per product category, eight standard columns.
// Columns and values come from the backend (`c969_entitlement`); the layout is the flat
// row-per-item layout used across the report, not a grouped product matrix.

type EntitlementColumn = { key: string; label: string };
export type EntitlementRow = {
    category: string;
    hsn_code: string;
    description: string;
    total_qty: string;
    allotted_qty: string;
    allotted_cif: string;
    debited_qty: string;
    debited_cif: string;
    balance_qty: string;
    line_count: number;
    license_count: number;
    source_descriptions: string[];
};
export type UnrecognisedItem = {
    import_item_id: number;
    serial_number: number;
    licence_number: string;
    description: string;
    quantity: string;
    unit: string;
    current_classifiers: string[];
};
export type C969Entitlement = {
    columns: EntitlementColumn[];
    rows: EntitlementRow[];
    unrecognised_items?: UnrecognisedItem[];
};

const NUMERIC_DIGITS: Record<string, number> = {
    total_qty: 3,
    allotted_qty: 3,
    allotted_cif: 2,
    debited_qty: 3,
    debited_cif: 2,
    balance_qty: 3,
};

// Same display rule as the rest of the report: blank shows as a dash, negatives never show.
function formatValue(value: unknown, digits: number) {
    if (value == null || value === "") return "—";
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return Math.max(n, 0).toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function UnrecognisedTable({ items }: { items: UnrecognisedItem[] }) {
    return (
        <Card className="mb-4 rounded-md shadow-none">
            <CardHeader className="border-b bg-amber-50 py-3">
                <h2 className="text-base font-semibold">Unclassified C969 Lines — to classify</h2>
                <p className="text-xs text-muted-foreground">
                    {items.length === 0
                        ? "No unclassified lines. Every C969 line is named."
                        : `${items.length} line${items.length === 1 ? "" : "s"} name no product yet. Give each a classifier.`}
                </p>
            </CardHeader>
            {items.length > 0 && (
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-xs">
                            <thead className="bg-muted">
                                <tr>
                                    {["IMPORT ITEM ID", "SERIAL NO", "LICENCE", "ORIGINAL DESCRIPTION", "QUANTITY", "UNIT", "CURRENT CLASSIFIER", "SUGGESTED CLASSIFIER"].map((label) => (
                                        <th key={label} className="whitespace-nowrap border p-2 text-left font-semibold">{label}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {items.map((item) => (
                                    <tr key={item.import_item_id} className="hover:bg-muted/30">
                                        <td className="border p-2 tabular-nums">{item.import_item_id}</td>
                                        <td className="border p-2 tabular-nums">{item.serial_number}</td>
                                        <td className="border p-2">{item.licence_number}</td>
                                        <td className="border p-2">{item.description || "—"}</td>
                                        <td className="whitespace-nowrap border p-2 text-right tabular-nums">{formatValue(item.quantity, 3)}</td>
                                        <td className="border p-2">{item.unit || "—"}</td>
                                        <td className="border p-2">{item.current_classifiers.join(", ") || "—"}</td>
                                        <td className="border p-2 text-muted-foreground">to be classified</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            )}
        </Card>
    );
}

export default function C969EntitlementTable({ data, licenceCount }: { data: C969Entitlement; licenceCount?: number }) {
    const columns = data.columns;
    const rows = data.rows;
    return (
        <>
            <Card className="mt-4 rounded-md border-2 border-primary shadow-none">
                <CardHeader className="border-b bg-primary py-3 text-primary-foreground">
                    <h2 className="text-base font-semibold">{TOTAL_SUMMARY_TITLE}</h2>
                    <p className="text-xs opacity-80">{licenceCount != null ? `${licenceCount} Licences · ` : ""}{rows.length} categories</p>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-xs">
                            <thead className="bg-muted">
                                <tr>
                                    {columns.map((column) => (
                                        <th key={column.key} className="whitespace-nowrap border p-2 text-left font-semibold">
                                            {column.label}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((row) => (
                                    <tr key={row.category} className="hover:bg-muted/30">
                                        {columns.map((column) => {
                                            const digits = NUMERIC_DIGITS[column.key];
                                            const value = (row as Record<string, unknown>)[column.key];
                                            if (digits === undefined) {
                                                const isDescription = column.key === "description";
                                                return (
                                                    <td
                                                        key={column.key}
                                                        className={cn("border p-2", isDescription && "font-semibold")}
                                                        title={isDescription ? row.source_descriptions.join("\n") || undefined : undefined}
                                                    >
                                                        {value == null || value === "" ? "—" : String(value)}
                                                    </td>
                                                );
                                            }
                                            return (
                                                <td key={column.key} className="whitespace-nowrap border p-2 text-right tabular-nums">
                                                    {formatValue(value, digits)}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
            <UnrecognisedTable items={data.unrecognised_items ?? []} />
        </>
    );
}

// Per-notification "Item Summary" for C969: one row per product category, summarising the
// same entitlement lines as the flat table. HSN CODES are the distinct codes of those lines.
const GROUP_SUMMARY_COLUMNS: { key: keyof EntitlementRow | "licenses"; label: string; digits?: number; align: "left" | "right" }[] = [
    { key: "description", label: "ITEM", align: "left" },
    { key: "hsn_code", label: "HSN CODES", align: "left" },
    { key: "license_count", label: "LICENCES", align: "right" },
    { key: "total_qty", label: "TOTAL QTY", digits: 3, align: "right" },
    { key: "allotted_qty", label: "ALLOTTED QTY", digits: 3, align: "right" },
    { key: "allotted_cif", label: "ALLOTTED CIF", digits: 2, align: "right" },
    { key: "debited_qty", label: "DEBITED QTY", digits: 3, align: "right" },
    { key: "debited_cif", label: "DEBITED CIF", digits: 2, align: "right" },
    { key: "balance_qty", label: "BALANCE QTY", digits: 3, align: "right" },
];

const SUM_KEYS = ["total_qty", "allotted_qty", "allotted_cif", "debited_qty", "debited_cif", "balance_qty"] as const;

export function C969GroupSummary({ group }: { group: { c969_entitlement: C969Entitlement } }) {
    const rows = group.c969_entitlement.rows;
    const totals: Record<string, number> = {};
    for (const key of SUM_KEYS) {
        totals[key] = rows.reduce((sum, row) => sum + (Number(row[key]) || 0), 0);
    }
    const licenseCount = rows.reduce((max, row) => Math.max(max, row.license_count), 0);
    return (
        <CardContent className="p-0">
            <div className="overflow-x-auto">
                <table className="w-full border-collapse text-xs">
                    <thead className="bg-muted">
                        <tr>
                            {GROUP_SUMMARY_COLUMNS.map((column) => (
                                <th key={column.label} className={cn("whitespace-nowrap border p-2 font-semibold", column.align === "right" ? "text-right" : "text-left")}>
                                    {column.label}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row) => (
                            <tr key={row.category} className="hover:bg-muted/30">
                                <td className="border p-2 font-semibold">{row.category}</td>
                                <td className="border p-2">{row.hsn_code || "—"}</td>
                                <td className="border p-2 text-right tabular-nums">{row.license_count}</td>
                                {SUM_KEYS.map((key) => (
                                    <td key={key} className="whitespace-nowrap border p-2 text-right tabular-nums">
                                        {formatValue(row[key], NUMERIC_DIGITS[key])}
                                    </td>
                                ))}
                            </tr>
                        ))}
                        <tr className="bg-muted font-bold">
                            <td className="border p-2">SUBTOTAL</td>
                            <td className="border p-2">—</td>
                            <td className="border p-2 text-right tabular-nums">{licenseCount}</td>
                            {SUM_KEYS.map((key) => (
                                <td key={key} className="whitespace-nowrap border p-2 text-right tabular-nums">
                                    {formatValue(totals[key], NUMERIC_DIGITS[key])}
                                </td>
                            ))}
                        </tr>
                    </tbody>
                </table>
            </div>
        </CardContent>
    );
}
