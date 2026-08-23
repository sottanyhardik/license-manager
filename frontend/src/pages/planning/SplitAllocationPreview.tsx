import { Badge } from "@/components/ui/badge";
import type { SplitAllocationPreview as SplitAllocationPreviewData } from "@/services/api/planningRuleApi";

export function SplitAllocationPreview({ allocation }: { allocation: SplitAllocationPreviewData }) {
    const successful = allocation.status === "ALLOCATED";
    return <section aria-label="Split allocation preview" className="mt-2 rounded-md border bg-muted/20 p-3 text-xs">
        <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-semibold">Allocation</h4>
            <Badge variant={successful ? "default" : "destructive"}>{allocation.status.replace(/_/g, " ")}</Badge>
        </div>
        <dl className="mt-2 grid gap-2 sm:grid-cols-3">
            <div><dt className="text-muted-foreground">Total Qty</dt><dd className="font-medium tabular-nums">{allocation.total_quantity}</dd></div>
            <div><dt className="text-muted-foreground">Balance CIF</dt><dd className="font-medium tabular-nums">{allocation.balance_cif}</dd></div>
            <div><dt className="text-muted-foreground">Average Price</dt><dd className="font-medium tabular-nums">{allocation.effective_unit_price ?? "—"}</dd></div>
        </dl>
        {!!allocation.lines.length && <div className="mt-3 overflow-x-auto"><table className="w-full text-left">
            <thead><tr className="border-b text-muted-foreground"><th className="pb-1">Bucket</th><th className="pb-1">Qty</th><th className="pb-1">Unit Price</th><th className="pb-1">CIF</th></tr></thead>
            <tbody>{allocation.lines.map((line, index) => <tr key={`${line.bucket}-${index}`} className="border-b last:border-0"><td className="py-1 font-medium">{line.bucket}</td><td className="tabular-nums">{line.quantity}</td><td className="tabular-nums">{line.unit_price}</td><td className="tabular-nums">{line.cif}</td></tr>)}</tbody>
        </table></div>}
        <dl className="mt-3 grid gap-2 border-t pt-2 sm:grid-cols-2">
            <div><dt className="text-muted-foreground">Quantity Remaining</dt><dd className="font-semibold tabular-nums">{allocation.quantity_remaining}</dd></div>
            <div><dt className="text-muted-foreground">CIF Remaining</dt><dd className="font-semibold tabular-nums">{allocation.cif_remaining}</dd></div>
        </dl>
        {allocation.reason && <p className="mt-2 text-destructive">{allocation.reason}</p>}
    </section>;
}
