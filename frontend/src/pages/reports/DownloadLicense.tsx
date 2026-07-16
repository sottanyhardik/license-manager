import { useId, useState } from "react";
import { toast } from "sonner";
import {
    ScanBarcode, Funnel, FileSpreadsheet, Loader2, Info,
    CircleCheck, TriangleAlert, CheckCircle2,
} from "lucide-react";

import api from "../../api/axios";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const DEFAULT_DAYS = 365;
const MIN_DAYS = 1;
const MAX_DAYS = 3650;

const STATUS_OPTIONS = [
    { value: "active", label: "Active Licenses", Icon: CircleCheck, tone: "success" },
    { value: "expiring", label: "Expiring Soon", Icon: TriangleAlert, tone: "warning" },
] as const;

type LicenseStatus = (typeof STATUS_OPTIONS)[number]["value"];

type LicenseReportItem = {
    license_number?: unknown;
};

type LicenseReportResponse = {
    licenses?: unknown;
};

const EXCEL_INCLUDES = [
    "License number, date, expiry, exporter",
    "BOE & Allotment summary per license",
    "Balance quantity per item (HSN, description)",
    "Restriction percentage and CIF values",
    "Unit price and CIF FC calculations",
    "Each license in its own named sheet",
];

export function normalizeDownloadDays(value: unknown, fallback = DEFAULT_DAYS): number {
    const fallbackDays = Number.isFinite(fallback)
        ? Math.min(MAX_DAYS, Math.max(MIN_DAYS, Math.trunc(fallback)))
        : DEFAULT_DAYS;
    const parsed = Number.parseInt(String(value), 10);
    if (!Number.isFinite(parsed)) {
        return fallbackDays;
    }
    return Math.min(MAX_DAYS, Math.max(MIN_DAYS, parsed));
}

export function parseLicenseNumbers(value: string): string[] {
    const seen = new Set<string>();
    const numbers: string[] = [];

    for (const rawValue of value.split(/[\s,]+/)) {
        const licenseNumber = rawValue.trim();
        if (licenseNumber && !seen.has(licenseNumber)) {
            seen.add(licenseNumber);
            numbers.push(licenseNumber);
        }
    }

    return numbers;
}

function extractLicenseNumbers(data: LicenseReportResponse): string[] {
    if (!Array.isArray(data.licenses)) {
        return [];
    }

    return data.licenses
        .map((item: LicenseReportItem) => item.license_number)
        .filter((licenseNumber): licenseNumber is string => typeof licenseNumber === "string" && licenseNumber.trim().length > 0)
        .map((licenseNumber) => licenseNumber.trim());
}

function downloadBlob(data: BlobPart, filename: string): void {
    const blobUrl = window.URL.createObjectURL(data instanceof Blob ? data : new Blob([data]));
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60_000);
}

export default function DownloadLicense() {
    const [licenseStatus, setLicenseStatus] = useState<LicenseStatus>("active");
    const [days, setDays] = useState(DEFAULT_DAYS);
    const [loading, setLoading] = useState(false);
    const [bulkInput, setBulkInput] = useState("");
    const [bulkLoading, setBulkLoading] = useState(false);
    const bulkInputId = useId();
    const bulkHelpId = `${bulkInputId}-help`;
    const daysInputId = useId();
    const daysHelpId = `${daysInputId}-help`;

    const handleDownload = async () => {
        const exportDays = normalizeDownloadDays(days);
        if (exportDays !== days) {
            setDays(exportDays);
        }
        setLoading(true);
        try {
            const url = licenseStatus === "expiring"
                ? `reports/expiring-licenses/?days=${exportDays}`
                : `reports/active-licenses/?days=${exportDays}`;
            const jsonResponse = await api.get<LicenseReportResponse>(url);
            const licenseNumbers = extractLicenseNumbers(jsonResponse.data);
            if (licenseNumbers.length === 0) {
                toast.error("No licenses found for the selected criteria.");
                return;
            }
            const response = await api.post("licenses/bulk-balance-excel/", { license_numbers: licenseNumbers }, { responseType: "blob" });
            downloadBlob(response.data, `licenses_${licenseStatus}_${exportDays}days.xlsx`);
            toast.success(`Downloaded Excel for ${licenseNumbers.length} license(s)`);
        } catch (error) {
            toast.error(error?.response?.data?.error || "Failed to download. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    const handleBulkDownload = async () => {
        const numbers = parseLicenseNumbers(bulkInput);
        if (numbers.length === 0) {
            toast.error("Please enter at least one license number.");
            return;
        }
        setBulkLoading(true);
        try {
            const response = await api.post("licenses/bulk-balance-excel/", { license_numbers: numbers }, { responseType: "blob" });
            downloadBlob(response.data, `bulk_license_summary_${numbers.length}_licenses.xlsx`);
            toast.success(`Downloaded Excel for ${numbers.length} license(s)`);
        } catch (error) {
            toast.error(error?.response?.data?.error || "Failed to download. Please try again.");
        } finally {
            setBulkLoading(false);
        }
    };

    const parsedCount = parseLicenseNumbers(bulkInput).length;

    return (
        <>
            <PageHeader
                pretitle="Reports / Download License"
                title="Download License"
                description="Export per-license balance summaries as Excel"
            />

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {/* Bulk by numbers */}
                <Card>
                    <CardHeader className="border-b">
                        <CardTitle className="flex items-center gap-2 text-sm">
                            <ScanBarcode className="size-4 text-primary" />
                            Download by License Numbers
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col pt-5">
                        <p className="mb-3 text-[13px] text-muted-foreground">
                            Enter DFIA license numbers separated by commas or new lines. Each license gets its own sheet.
                        </p>
                        <div className="mb-3 flex-1">
                            <Label className="mb-1.5 flex items-center gap-2" htmlFor={bulkInputId}>
                                License Numbers
                                {parsedCount > 0 && <Badge>{parsedCount} entered</Badge>}
                            </Label>
                            <Textarea
                                id={bulkInputId}
                                rows={5}
                                className="font-mono"
                                placeholder={"e.g. 3011007415, 3011007018, 3011008321\nor one per line"}
                                value={bulkInput}
                                aria-describedby={bulkHelpId}
                                onChange={(e) => setBulkInput(e.target.value)}
                            />
                            <p id={bulkHelpId} className="mt-1.5 text-[11.5px] text-muted-foreground">
                                Comma- or newline-separated. Each license = one sheet named after the license number.
                            </p>
                        </div>
                        <Button className="w-full" onClick={handleBulkDownload} disabled={bulkLoading || parsedCount === 0}>
                            {bulkLoading ? <Loader2 className="size-4 animate-spin" /> : <FileSpreadsheet className="size-4" />}
                            {bulkLoading ? "Generating…" : `Download Excel (${parsedCount} license${parsedCount !== 1 ? "s" : ""})`}
                        </Button>
                    </CardContent>
                </Card>

                {/* By status */}
                <Card>
                    <CardHeader className="border-b">
                        <CardTitle className="flex items-center gap-2 text-sm">
                            <Funnel className="size-4 text-success" />
                            Download by Status
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col pt-5">
                        <p className="mb-3 text-[13px] text-muted-foreground">
                            Export all active or expiring licenses filtered by date range.
                        </p>

                        <div className="mb-3">
                            <div className="mb-1.5 text-[13px] font-medium">License Status</div>
                            <div className="flex flex-wrap gap-2" role="group" aria-label="License status">
                                {STATUS_OPTIONS.map(({ value, label, Icon, tone }) => {
                                    const active = licenseStatus === value;
                                    return (
                                        <button
                                            key={value}
                                            type="button"
                                            aria-pressed={active}
                                            onClick={() => setLicenseStatus(value)}
                                            className={`flex flex-1 min-w-[140px] items-center gap-2 rounded-md border px-3 py-2 text-[13px] font-medium transition-colors cursor-pointer ${
                                                active
                                                    ? tone === "success"
                                                        ? "border-success/40 bg-success/10 text-success"
                                                        : "border-warning/40 bg-warning/10 text-warning"
                                                    : "border-border text-muted-foreground hover:bg-accent/50"
                                            }`}
                                        >
                                            <Icon className="size-4" />
                                            {label}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="mb-4">
                            <Label className="mb-1.5" htmlFor={daysInputId}>
                                {licenseStatus === "expiring" ? "Expiring within (days)" : "Look-back period (days)"}
                            </Label>
                            <Input
                                id={daysInputId}
                                type="number"
                                min={MIN_DAYS}
                                max={MAX_DAYS}
                                value={days}
                                aria-describedby={daysHelpId}
                                onChange={(e) => setDays(normalizeDownloadDays(e.target.value))}
                            />
                            <p id={daysHelpId} className="mt-1.5 text-[11.5px] text-muted-foreground">
                                {licenseStatus === "expiring"
                                    ? `Licenses expiring within the next ${days} days`
                                    : `Active licenses expiring from ${days} days ago onward`}
                            </p>
                        </div>

                        <Button className="mt-auto w-full" onClick={handleDownload} disabled={loading}>
                            {loading ? <Loader2 className="size-4 animate-spin" /> : <FileSpreadsheet className="size-4" />}
                            {loading ? "Generating…" : "Download Excel"}
                        </Button>
                    </CardContent>
                </Card>

                {/* Info */}
                <Card className="lg:col-span-2">
                    <CardContent className="pt-5">
                        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                            <Info className="size-4 text-primary" />
                            Excel Report Includes
                        </div>
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                            {EXCEL_INCLUDES.map((f, i) => (
                                <div key={i} className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
                                    <CheckCircle2 className="size-4 shrink-0 text-success" />
                                    {f}
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </>
    );
}
