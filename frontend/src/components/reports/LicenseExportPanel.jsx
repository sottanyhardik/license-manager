import { useState } from "react";
import { toast } from "react-toastify";
import { Download, Loader2, CheckCircle2 } from "lucide-react";

import api from "../../api/axios";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Shared export panel for the near-identical Expiring/Active license reports.
 * Logic (blob download) is preserved exactly from the original pages.
 */
export default function LicenseExportPanel({
    title,
    description,
    daysLabel,
    helpText,            // (days) => string
    endpoint,            // (days) => string
    filename,            // (days) => string
    features = [],
    defaultDays = 30,
}) {
    const [days, setDays] = useState(defaultDays);
    const [loading, setLoading] = useState(false);

    const handleExport = async () => {
        setLoading(true);
        try {
            const response = await api.get(endpoint(days), { responseType: "blob" });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement("a");
            link.href = url;
            link.setAttribute("download", filename(days));
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            toast.error(error?.response?.data?.error || "Failed to download report. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <PageHeader pretitle="Reports" title={title} description={description} />

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <Card>
                    <CardHeader className="border-b"><CardTitle className="text-sm">Export Settings</CardTitle></CardHeader>
                    <CardContent className="pt-5">
                        <div className="mb-4">
                            <Label className="mb-1.5" htmlFor="days">{daysLabel}</Label>
                            <Input
                                id="days"
                                type="number"
                                min="1"
                                max="365"
                                value={days}
                                onChange={(e) => setDays(parseInt(e.target.value) || defaultDays)}
                            />
                            <p className="mt-1.5 text-[11.5px] text-muted-foreground">{helpText(days)}</p>
                        </div>
                        <Button onClick={handleExport} disabled={loading}>
                            {loading ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                            {loading ? "Generating…" : "Download Excel Report"}
                        </Button>
                    </CardContent>
                </Card>

                {features.length > 0 && (
                    <Card>
                        <CardHeader className="border-b"><CardTitle className="text-sm">Report Features</CardTitle></CardHeader>
                        <CardContent className="pt-5">
                            <ul className="flex flex-col gap-2.5">
                                {features.map((f, i) => (
                                    <li key={i} className="flex items-start gap-2 text-[13px] text-foreground">
                                        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
                                        {f}
                                    </li>
                                ))}
                            </ul>
                        </CardContent>
                    </Card>
                )}
            </div>
        </>
    );
}
