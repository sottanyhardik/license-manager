import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";

import api from "../api/axios";
import TransferLetterForm from "../components/TransferLetterForm";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

function Detail({ label, value }) {
    return (
        <div>
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className="text-sm font-semibold text-foreground">{value ?? "—"}</div>
        </div>
    );
}

export default function TradeTransferLetter({ tradeId: propId, isModal = false, onClose: _onClose }: { tradeId?: number | string; isModal?: boolean; onClose?: () => void }) {
    const { id: paramId } = useParams();
    const navigate = useNavigate();
    const id = propId || paramId;

    const [trade, setTrade] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const fetchTrade = async () => {
            try {
                const { data } = await api.get(`trades/${id}/`);
                setTrade(data);
            } catch {
                setError("Failed to load Trade details");
            } finally {
                setLoading(false);
            }
        };
        fetchTrade();
    }, [id]);

    if (loading) return <div className="p-8 text-center text-sm text-muted-foreground">Loading…</div>;

    return (
        <div className={isModal ? "" : "py-1"}>
            {!isModal && (
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <h1 className="text-2xl font-bold tracking-tight text-foreground">
                        Generate Transfer Letter
                        {(trade?.invoice_number || trade?.id) && (
                            <span className="ml-2 text-base font-medium text-muted-foreground">· Trade {trade.invoice_number || trade.id}</span>
                        )}
                    </h1>
                    <Button variant="outline" onClick={() => navigate("/trades")}>
                        <ArrowLeft className="size-4" />Back to Trade List
                    </Button>
                </div>
            )}

            {error && (
                <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive">
                    {error}
                </div>
            )}

            {trade && (
                <>
                    <Card className="mb-4">
                        <CardContent className="pt-5">
                            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                                <Detail label="Direction" value={trade.direction} />
                                <Detail label="Invoice Number" value={trade.invoice_number || "-"} />
                                <Detail label="Invoice Date" value={trade.invoice_date} />
                                <Detail label="Total Items" value={trade.lines?.length || 0} />
                            </div>
                            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                                <Detail label="From Company" value={trade.from_company_name || "-"} />
                                <Detail label="To Company" value={trade.to_company_name || "-"} />
                            </div>
                        </CardContent>
                    </Card>

                    <TransferLetterForm
                        instanceId={id}
                        instanceType="trade"
                        instanceIdentifier={trade.invoice_number || trade.id}
                        items={trade.lines?.map((line) => ({
                            id: line.id,
                            license_number: line.sr_number_label || "-",
                            cif_fc: line.cif_fc || 0,
                            cif_inr: line.cif_inr || 0,
                            purchase_status: "N/A",
                        })) || []}
                        onSuccess={(msg) => toast.success(msg)}
                        onError={(msg) => toast.error(msg)}
                    />
                </>
            )}
        </div>
    );
}
