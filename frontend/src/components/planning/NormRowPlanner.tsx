import { useEffect, useMemo, useState } from "react";
import { Loader2, Search, Target } from "lucide-react";
import { toast } from "sonner";
import Select from "react-select";

import { Button } from "@/components/ui/button";
import { fetchPlanningNorm, planNorm } from "../../services/api/licenseApi";

export type PlanningLicenseOption = { id: number; number: string };
export type SionPlanningRow = {
    id: number;
    norm_class: string;
    description?: string | null;
    import_norm?: Array<{ hsn_code?: { hs_code?: string } | string | null; description?: string | null; unit?: string | null }>;
    export_norm?: Array<{ description?: string | null; quantity?: string | number | null; unit?: string | null }>;
    available_qty?: string | number | null;
    planned_qty?: string | number | null;
    allocated_qty?: string | number | null;
    remaining_qty?: string | number | null;
    shortage_qty?: string | number | null;
    license_count?: number;
    planned_count?: number;
    status?: string | null;
};

export function PlanNormButton({ sionId, licenseIds, label, onPlanned }: {
    sionId: number;
    licenseIds: number[];
    label: string;
    onPlanned?: (result: unknown) => void;
}) {
    const [saving, setSaving] = useState(false);
    const disabled = saving || licenseIds.length === 0;
    const apply = async () => {
        if (disabled) return;
        setSaving(true);
        try {
            const result = await planNorm(licenseIds, sionId);
            const counts = result as { created?: number; updated?: number; unchanged?: number };
            toast.success(`${label} planned for ${licenseIds.length} license${licenseIds.length === 1 ? "" : "s"}: ${counts.created ?? 0} created, ${counts.updated ?? 0} updated, ${counts.unchanged ?? 0} already existed.`);
            onPlanned?.(result);
        } catch (error: unknown) {
            const message = (error as { response?: { data?: { detail?: string; error?: string; message?: string } } })?.response?.data;
            toast.error(message?.message || message?.detail || message?.error || `Failed to plan ${label}.`);
        } finally {
            setSaving(false);
        }
    };
    return (
        <Button size="sm" onClick={apply} disabled={disabled} aria-label={`Plan ${label}`} title={licenseIds.length ? `Plan ${label} for selected licenses` : "Select at least one license"}>
            {saving ? <Loader2 className="size-3.5 animate-spin" /> : <Target className="size-3.5" />}
            {saving ? "Planning…" : "Plan"}
        </Button>
    );
}

export default function NormRowPlanner({ norms, licenses, onPlanned, initialSelectedLicenseIds = [], onSelectionChange, embeddedSnapshots = false }: {
    norms: SionPlanningRow[];
    licenses: PlanningLicenseOption[];
    onPlanned?: () => void;
    initialSelectedLicenseIds?: number[];
    onSelectionChange?: (ids: number[]) => void;
    /** Norm rows already contain canonical snapshot totals; never fan out requests. */
    embeddedSnapshots?: boolean;
}) {
    const [selected, setSelected] = useState<number[]>(initialSelectedLicenseIds);
    const [hsn, setHsn] = useState("");
    const [product, setProduct] = useState("");
    const [directNorm, setDirectNorm] = useState("");
    const [operator, setOperator] = useState<"AND" | "OR">("AND");
    const [snapshots, setSnapshots] = useState<Record<number, SionPlanningRow>>({});
    const [snapshotLoading, setSnapshotLoading] = useState<Record<number, boolean>>({});
    const [snapshotErrors, setSnapshotErrors] = useState<Record<number, string>>({});
    const [refreshVersion, setRefreshVersion] = useState(0);
    useEffect(() => setSelected(initialSelectedLicenseIds), [initialSelectedLicenseIds.join(",")]);

    const visible = useMemo(() => norms.filter((norm) => {
        if (directNorm && String(norm.id) !== directNorm) return false;
        const imports = norm.import_norm ?? [];
        const haystackHsn = imports.map((row) => typeof row.hsn_code === "object" ? row.hsn_code?.hs_code : row.hsn_code).join(" ").toLowerCase();
        const haystackProduct = [norm.description, ...imports.map((row) => row.description)].join(" ").toLowerCase();
        const hsnMatch = !hsn || haystackHsn.includes(hsn.trim().toLowerCase());
        const productMatch = !product || haystackProduct.includes(product.trim().toLowerCase());
        if (!hsn || !product) return hsnMatch && productMatch;
        return operator === "AND" ? hsnMatch && productMatch : hsnMatch || productMatch;
    }), [norms, directNorm, hsn, product, operator]);

    const licenseOptions = licenses.map((license) => ({ value: license.id, label: license.number }));
    const directOptions = norms.map((norm) => ({ value: String(norm.id), label: norm.norm_class }));
    useEffect(() => {
        if (embeddedSnapshots) { setSnapshots(Object.fromEntries(norms.map((norm) => [norm.id, norm]))); setSnapshotLoading({}); setSnapshotErrors({}); return; }
        if (selected.length === 0) { setSnapshots({}); return; }
        let active = true;
        setSnapshotLoading(Object.fromEntries(visible.map((norm) => [norm.id, true])));
        setSnapshotErrors({});
        Promise.allSettled(visible.map(async (norm) => [norm.id, await fetchPlanningNorm({ licenseIds: selected, sionId: norm.id, hsn, product, logic: operator })] as const))
            .then((results) => {
                if (!active) return;
                setSnapshots(Object.fromEntries(results.flatMap((result) => result.status === "fulfilled" ? [result.value] : [])));
                setSnapshotErrors(Object.fromEntries(results.flatMap((result, index) => result.status === "rejected" ? [[visible[index].id, (result.reason?.response?.data?.message || result.reason?.message || "Unable to load planning status.")]] : [])));
                setSnapshotLoading({});
            });
        return () => { active = false; };
    }, [selected, visible, hsn, product, operator, refreshVersion, embeddedSnapshots, norms]);

    return (
        <section className="mb-6 rounded-xl border border-border bg-card p-4" aria-labelledby="norm-planning-title">
            <h2 id="norm-planning-title" className="text-sm font-bold">Applicable SION Norm Planning</h2>
            <p className="mt-1 text-xs text-muted-foreground">Select licenses, then apply exactly one SION row.</p>

            <label className="mt-3 block text-xs font-semibold">Licenses
                <Select isMulti aria-label="Planning licenses" options={licenseOptions} value={licenseOptions.filter((option) => selected.includes(option.value))} onChange={(options) => { const ids = options.map((option) => option.value); setSelected(ids); onSelectionChange?.(ids); }} placeholder="Select one or more licenses…" className="mt-1 font-normal" />
            </label>
            {selected.length === 0 && <p role="status" className="mt-2 rounded-md bg-warning/10 px-3 py-2 text-xs text-warning">Select at least one license to enable planning.</p>}

            <div className="mt-4 grid gap-2 sm:grid-cols-4">
                <label className="text-xs font-medium">HSN
                    <span className="relative mt-1 block"><Search className="absolute left-2 top-2 size-3.5 text-muted-foreground" /><input aria-label="Filter SION by HSN" value={hsn} onChange={(e) => setHsn(e.target.value)} className="h-8 w-full rounded-md border border-input pl-7 pr-2" /></span>
                </label>
                <label className="text-xs font-medium">Product Description
                    <input aria-label="Filter SION by product" value={product} onChange={(e) => setProduct(e.target.value)} className="mt-1 h-8 w-full rounded-md border border-input px-2" />
                </label>
                <label className="text-xs font-medium">Logic
                    <Select aria-label="HSN and product match operator" options={[{ value: "AND", label: "AND" }, { value: "OR", label: "OR" }]} value={{ value: operator, label: operator }} onChange={(option) => setOperator((option?.value as "AND" | "OR") ?? "AND")} className="mt-1 font-normal" />
                </label>
                <label className="text-xs font-medium">Direct SION
                    <Select aria-label="Direct SION filter" isClearable options={directOptions} value={directOptions.find((option) => option.value === directNorm) ?? null} onChange={(option) => setDirectNorm(option?.value ?? "")} placeholder="All applicable norms" className="mt-1 font-normal" />
                </label>
            </div>

            <div className="mt-3 overflow-x-auto">
                {(hsn || product || directNorm) && <Button variant="ghost" size="sm" onClick={() => { setHsn(""); setProduct(""); setDirectNorm(""); setOperator("AND"); }}>Clear Filters</Button>}
                <table className="w-full text-sm"><thead><tr className="border-b text-left"><th className="p-2">SION Norm</th><th className="p-2">HSN</th><th className="p-2">Product Description</th><th className="p-2">Export Item</th><th className="p-2">Import / Input Item</th><th className="p-2">Unit</th><th className="p-2 text-right">Available Qty</th><th className="p-2 text-right">Existing Planned Qty</th><th className="p-2 text-right">Allocated Qty</th><th className="p-2 text-right">Remaining Qty</th><th className="p-2 text-right">Shortage Qty</th><th className="p-2">Status</th><th className="p-2 text-right">Action</th></tr></thead>
                    <tbody>{visible.map((norm) => {
                        const imports = norm.import_norm ?? [];
                        const hsns = imports.map((row) => typeof row.hsn_code === "object" ? row.hsn_code?.hs_code : row.hsn_code).filter(Boolean).join(", ") || "—";
                        const items = imports.map((row) => row.description).filter(Boolean).join(", ") || norm.description || "—";
                        const exportItems = (norm.export_norm ?? []).map((row) => row.description).filter(Boolean).join(", ") || "—";
                        const units = [...new Set(imports.map((row) => row.unit).filter(Boolean))].join(", ") || "—";
                        const snapshot = snapshots[norm.id];
                        const plannedProgress = snapshot?.license_count ? `Planned ${snapshot.planned_count ?? 0} / ${snapshot.license_count}` : null;
                        const statusLabel = snapshot?.status === "SHORT" ? "SHORTAGE" : snapshot?.status === "PARTIALLY_PLANNED" ? "PARTIAL" : snapshot?.status === "FEASIBLE" ? "PLANNED" : snapshot?.status || "UNPLANNED";
                        return <tr key={norm.id} className="border-b"><td className="p-2 font-semibold">{norm.norm_class}</td><td className="p-2">{hsns}</td><td className="p-2">{norm.description || "—"}</td><td className="p-2">{exportItems}</td><td className="p-2">{items}</td><td className="p-2">{units}</td><td className="p-2 text-right">{snapshotLoading[norm.id] ? <Loader2 aria-label={`Loading ${norm.norm_class}`} className="ml-auto size-3.5 animate-spin" /> : snapshot?.available_qty ?? "—"}</td><td className="p-2 text-right">{snapshot?.planned_qty ?? "—"}</td><td className="p-2 text-right">{snapshot?.allocated_qty ?? "—"}</td><td className="p-2 text-right">{snapshot?.remaining_qty ?? "—"}</td><td className="p-2 text-right text-destructive">{snapshot?.shortage_qty ?? "—"}</td><td className="p-2"><span className={snapshot?.status === "SHORT" || snapshot?.status === "CONFLICT" ? "font-semibold text-destructive" : ""}>{statusLabel}</span>{plannedProgress && <span className="block text-xs text-muted-foreground">{plannedProgress}</span>}{snapshotErrors[norm.id] ? <span role="alert" className="block text-xs text-destructive">{snapshotErrors[norm.id]}</span> : null}</td><td className="p-2 text-right"><PlanNormButton sionId={norm.id} licenseIds={selected} label={norm.norm_class} onPlanned={() => { setRefreshVersion((value) => value + 1); onPlanned?.(); }} /></td></tr>;
                    })}</tbody>
                </table>
                {visible.length === 0 && <p className="p-4 text-center text-sm text-muted-foreground">No SION rows match these filters.</p>}
            </div>
        </section>
    );
}
