import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Download, FileUp, RefreshCw, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { decideSaleClassification, downloadReadinessCsv, getPackageReadiness, postReadinessAction, recoverUniqueOrphan, uploadPurchaseDocument, type ReadinessRow } from "@/services/licenseLedgerReadiness";

const text = (row: ReadinessRow, ...keys: string[]) => {
    for (const key of keys) { const value = row[key]; if (value !== null && value !== undefined && value !== "") return Array.isArray(value) ? value.join(", ") : String(value); }
    return "—";
};
const id = (row: ReadinessRow, ...keys: string[]) => text(row, ...keys);
function RowTable({ rows, columns }: { rows: ReadinessRow[]; columns: Array<[string, string]> }) {
    if (!rows.length) return <p className="p-4 text-sm text-muted-foreground">No records.</p>;
    return <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead><tr className="border-b bg-muted/60">{columns.map(([key, label]) => <th key={key} className="px-3 py-2 font-semibold">{label}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={id(row, "id", "trade_id", "sale_id", "association_id") + index} className="border-b last:border-0">{columns.map(([key]) => <td key={key} className="px-3 py-2 align-top">{text(row, key)}</td>)}</tr>)}</tbody></table></div>;
}

function UploadPurchase({ jobId, row, onDone }: { jobId: string; row: ReadinessRow; onDone: () => void }) {
    const input = useRef<HTMLInputElement>(null); const [busy, setBusy] = useState(false);
    const tradeId = id(row, "trade_id", "purchase_trade_id");
    const upload = async (file?: File) => { if (!file || tradeId === "—") return; setBusy(true); try { await uploadPurchaseDocument(jobId, tradeId, file); toast.success("Supplier invoice uploaded and queued for validation."); onDone(); } catch (error) { toast.error(error instanceof Error ? error.message : "Upload failed."); } finally { setBusy(false); } };
    return <><input ref={input} type="file" accept="application/pdf,image/png,image/jpeg,image/tiff" className="hidden" onChange={e => void upload(e.target.files?.[0])} /><Button size="sm" variant="outline" disabled={busy} onClick={() => input.current?.click()}><FileUp className="mr-1 size-3" />Upload invoice</Button></>;
}

function MissingPurchases({ jobId, rows, refresh }: { jobId: string; rows: ReadinessRow[]; refresh: () => void }) {
    return <div className="space-y-3">{rows.length === 0 ? <p className="p-4 text-sm text-muted-foreground">No purchase-document blockers.</p> : rows.map(row => <Card key={id(row, "trade_id", "id")}><CardContent className="flex flex-wrap items-center gap-3 p-3 text-sm"><div className="min-w-[240px]"><b>{text(row, "licence_number", "license_number")}</b> · Trade {text(row, "trade_id")}<div className="text-muted-foreground">{text(row, "supplier", "supplier_name")} · Invoice {text(row, "purchase_invoice_number", "invoice_number")}</div><div className="text-muted-foreground">{text(row, "invoice_date")} · {text(row, "invoice_amount", "amount")}</div></div><span className="text-xs text-destructive">{text(row, "status", "blocking_reason")}</span><UploadPurchase jobId={jobId} row={row} onDone={refresh} /></CardContent></Card>)}</div>;
}

function Orphans({ jobId, rows, refresh }: { jobId: string; rows: ReadinessRow[]; refresh: () => void }) {
    const act = async (row: ReadinessRow, action: "link-orphan" | "reject-orphan") => { try {
        if (action === "link-orphan") await recoverUniqueOrphan(jobId, String(row.trade_id), String(row.source_storage_key), (row.evidence ?? {}) as Record<string, unknown>);
        else await postReadinessAction(jobId, "reject-orphan", { orphan_id: row.orphan_id ?? row.id, trade_id: row.trade_id, note: "Rejected during readiness review" });
        toast.success(action === "link-orphan" ? "Audited recovery link created." : "Candidate rejected."); refresh();
    } catch (e) { toast.error(e instanceof Error ? e.message : "Review action failed."); } };
    return <div className="space-y-3">{rows.map(row => <Card key={id(row, "orphan_id", "id")}><CardContent className="flex flex-wrap items-center gap-3 p-3 text-sm"><div className="min-w-[300px]"><b>{text(row, "storage_name", "filename", "source_storage_key")}</b><div className="text-muted-foreground">SHA-256: {text(row, "sha256", "source_checksum")}</div><div>{text(row, "extracted_invoice_number", "invoice_number")} · {text(row, "extracted_supplier", "supplier")} · {text(row, "matching_rule", "match_reason")}</div></div>{text(row, "unique_deterministic_match", "can_link") === "true" && <Button size="sm" onClick={() => void act(row, "link-orphan")}>Link verified match</Button>}<Button size="sm" variant="outline" onClick={() => void act(row, "reject-orphan")}>Reject candidate</Button></CardContent></Card>)}{!rows.length && <p className="p-4 text-sm text-muted-foreground">No orphan recovery candidates.</p>}</div>;
}

function UnknownSales({ rows, refresh }: { rows: ReadinessRow[]; refresh: () => void }) {
    const decide = async (row: ReadinessRow, decision: string) => { const reason = window.prompt(`Reason and provenance for ${decision}:`); if (!reason?.trim()) return; try {
        // Sales decisions are intrinsic to the sale in the canonical trade
        // service. The service records scope/audit provenance and requeues
        // only licences associated with that sale.
        await decideSaleClassification(String(row.sale_id), { decision, reason, provenance: "Authorized readiness review" });
        toast.success("Classification recorded; affected licences will be re-evaluated."); refresh();
    } catch (e) { toast.error(e instanceof Error ? e.message : "Classification failed."); } };
    return <div className="space-y-3">{rows.map(row => <Card key={`${id(row, "sale_id")}-${id(row, "association_id")}`}><CardContent className="flex flex-wrap items-center gap-3 p-3 text-sm"><div className="min-w-[330px]"><b>Sale {text(row, "sale_id")}</b> · {text(row, "invoice_number")}<div>{text(row, "seller")} → {text(row, "buyer")}</div><div className="text-muted-foreground">Licence {text(row, "licence_number", "license_number")} · {text(row, "relationship_summary", "branch_path")}</div></div><Button size="sm" onClick={() => void decide(row, "FINAL_PARTY")}>Final party</Button><Button size="sm" variant="secondary" onClick={() => void decide(row, "INTERLINKED")}>Interlinked</Button><Button size="sm" variant="outline" onClick={() => void decide(row, "NOT_APPLICABLE")}>Not applicable</Button></CardContent></Card>)}{!rows.length && <p className="p-4 text-sm text-muted-foreground">No unknown sales classifications.</p>}</div>;
}

export default function LicenseLedgerPackageReadiness() {
    const { jobId = "" } = useParams();
    const { data, isLoading, error, refetch } = useQuery({ queryKey: ["license-package-readiness", jobId], queryFn: () => getPackageReadiness(jobId), enabled: Boolean(jobId) });
    const exportCsv = (key: string) => { const url = data?.csv_urls?.[key]; if (url) void downloadReadinessCsv(url).catch(e => toast.error(e instanceof Error ? e.message : "CSV export failed.")); };
    if (isLoading) return <p className="p-6 text-sm text-muted-foreground">Loading package readiness…</p>;
    if (error || !data) return <p className="p-6 text-sm text-destructive">Unable to load package readiness: {error instanceof Error ? error.message : "unknown error"}</p>;
    const missing = data.missing_purchases ?? [], orphans = data.orphan_candidates ?? [], unknown = data.unknown_sales ?? [], resolved = data.resolved ?? [];
    return <><PageHeader pretitle="License ledger package" title="Data Readiness" description="Resolve authoritative source and sales-classification blockers. Every decision is audited and affected licences re-evaluate automatically." actions={<div className="flex gap-2"><Button variant="outline" onClick={() => void refetch()}><RefreshCw className="mr-1 size-4" />Refresh</Button><Button asChild variant="outline"><Link to="/license-ledger">Back to ledger</Link></Button></div>} />
        <div className="mb-4 flex flex-wrap gap-2 text-sm"><span className="rounded bg-destructive/10 px-3 py-1 text-destructive"><TriangleAlert className="mr-1 inline size-4" />Missing purchases: {missing.length}</span><span className="rounded bg-warning/15 px-3 py-1">Orphan candidates: {orphans.length}</span><span className="rounded bg-warning/15 px-3 py-1">Unknown sales: {unknown.length}</span><span className="rounded bg-success/10 px-3 py-1 text-success"><CheckCircle2 className="mr-1 inline size-4" />Resolved: {resolved.length}</span></div>
        <Tabs defaultValue="missing"><TabsList><TabsTrigger value="missing">Missing Purchase Documents</TabsTrigger><TabsTrigger value="orphans">Orphan Recovery Candidates</TabsTrigger><TabsTrigger value="sales">Unknown Sales Classifications</TabsTrigger><TabsTrigger value="resolved">Resolved</TabsTrigger></TabsList><div className="mt-2 flex flex-wrap gap-2">{[["missing-purchase-documents", "Missing purchases"], ["orphan-recovery-review", "Orphan review"], ["unknown-sales-classification", "Unknown sales"], ["licence-readiness", "Licence readiness"]].map(([key, label]) => <Button key={key} size="sm" variant="ghost" disabled={!data.csv_urls?.[key]} onClick={() => exportCsv(key)}><Download className="mr-1 size-3" />{label} CSV</Button>)}</div><TabsContent value="missing"><MissingPurchases jobId={jobId} rows={missing} refresh={() => void refetch()} /></TabsContent><TabsContent value="orphans"><Orphans jobId={jobId} rows={orphans} refresh={() => void refetch()} /></TabsContent><TabsContent value="sales"><UnknownSales rows={unknown} refresh={() => void refetch()} /></TabsContent><TabsContent value="resolved"><RowTable rows={resolved} columns={[["licence_number", "Licence"], ["record_type", "Type"], ["record_id", "Record"], ["resolution", "Resolution"], ["decided_by", "By"], ["decided_at", "At"]]} /></TabsContent></Tabs>
    </>;
}
