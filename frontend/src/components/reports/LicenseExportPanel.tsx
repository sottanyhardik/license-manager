import { useId, useState } from "react";
import { toast } from "sonner";
import { Download, Loader2, CheckCircle2 } from "lucide-react";

import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { openAuthedFile } from "@/utils/documentDownload";

const MIN_DAYS = 1;
const MAX_DAYS = 365;

type LicenseExportPanelProps = {
    title: string;
    description: string;
    daysLabel: string;
    helpText: (days: number) => string;
    endpoint: (days: number) => string;
    filename: (days: number) => string;
    features?: string[];
    defaultDays?: number;
};

export function normalizeExportDays(value: unknown, fallback = 30): number {
    const fallbackDays = Number.isFinite(fallback)
        ? Math.min(MAX_DAYS, Math.max(MIN_DAYS, Math.trunc(fallback)))
        : 30;
    const parsed = Number.parseInt(String(value), 10);
    if (!Number.isFinite(parsed)) {
        return fallbackDays;
    }
    return Math.min(MAX_DAYS, Math.max(MIN_DAYS, parsed));
}

/**
 * Shared export panel for the near-identical Expiring/Active license reports.
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
}: LicenseExportPanelProps) {
    const [days, setDays] = useState(() => normalizeExportDays(defaultDays));
    const [loading, setLoading] = useState(false);
    const daysInputId = useId();
    const daysHelpId = `${daysInputId}-help`;

    const handleExport = async () => {
        const exportDays = normalizeExportDays(days, defaultDays);
        if (exportDays !== days) {
            setDays(exportDays);
        }
        setLoading(true);
        try {
            await openAuthedFile(endpoint(exportDays), filename(exportDays));
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
                            <Label className="mb-1.5" htmlFor={daysInputId}>{daysLabel}</Label>
                            <Input
                                id={daysInputId}
                                type="number"
                                min={MIN_DAYS}
                                max={MAX_DAYS}
                                value={days}
                                aria-describedby={daysHelpId}
                                onChange={(e) => setDays(normalizeExportDays(e.target.value, defaultDays))}
                            />
                            <p id={daysHelpId} className="mt-1.5 text-[11.5px] text-muted-foreground">{helpText(days)}</p>
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
                                    <li key={`${f}-${i}`} className="flex items-start gap-2 text-[13px] text-foreground">
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
