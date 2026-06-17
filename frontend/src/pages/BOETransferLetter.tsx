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

export default function BOETransferLetter({ boeId: propId, isModal = false, onClose: _onClose }: { boeId?: number | string; isModal?: boolean; onClose?: () => void }) {
    const { id: paramId } = useParams();
    const navigate = useNavigate();
    const id = propId || paramId;

    const [boe, setBoe] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const fetchBOE = async () => {
            try {
                const { data } = await api.get(`bill-of-entries/${id}/`);
                setBoe(data);
            } catch {
                setError("Failed to load BOE details");
            } finally {
                setLoading(false);
            }
        };
        fetchBOE();
    }, [id]);

    if (loading) return <div className="p-8 text-center text-sm text-muted-foreground">Loading…</div>;

    return (
        <div className={isModal ? "" : "py-1"}>
            {!isModal && (
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <h1 className="text-2xl font-bold tracking-tight text-foreground">
                        Generate Transfer Letter
                        {boe?.bill_of_entry_number && (
                            <span className="ml-2 text-base font-medium text-muted-foreground">· BOE {boe.bill_of_entry_number}</span>
                        )}
                    </h1>
                    <Button variant="outline" onClick={() => navigate("/bill-of-entries")}>
                        <ArrowLeft className="size-4" />Back to BOE List
                    </Button>
                </div>
            )}

            {error && (
                <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive">
                    {error}
                </div>
            )}

            {boe && (
                <>
                    <Card className="mb-4">
                        <CardContent className="grid grid-cols-2 gap-4 pt-5 md:grid-cols-4">
                            <Detail label="BOE Number" value={boe.bill_of_entry_number} />
                            <Detail label="BOE Date" value={boe.bill_of_entry_date} />
                            <Detail label="Company" value={boe.company_name || boe.company?.name} />
                            <Detail label="Total Items" value={boe.item_details?.length || 0} />
                        </CardContent>
                    </Card>

                    <TransferLetterForm
                        instanceId={id}
                        instanceType="boe"
                        instanceIdentifier={boe.bill_of_entry_number}
                        items={boe.item_details?.map((detail) => ({
                            id: detail.id,
                            license_number: detail.license_number || "-",
                            cif_fc: detail.cif_fc,
                            purchase_status: detail.purchase_status || "N/A",
                        })) || []}
                        onSuccess={(msg) => toast.success(msg)}
                        onError={(msg) => toast.error(msg)}
                    />
                </>
            )}
        </div>
    );
}
