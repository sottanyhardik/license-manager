import { useId, useState, useMemo } from "react";
import { toast } from "sonner";
import {
    ScanBarcode, Funnel, FileSpreadsheet, Loader2, Info,
    CircleCheck, TriangleAlert, CheckCircle2,
} from "lucide-react";
import {
    Box,
    Stack,
    Grid,
    Paper,
    TextField,
    Typography,
    Button as MuiButton,
    Chip,
    useTheme,
} from "@mui/material";

import api from "../../api/axios";
import PageHeader from "@/components/PageHeader";
import ActiveFilters, { type ActiveFilterItem } from "@/components/ActiveFilters";
import { MAX_DAYS, MIN_DAYS, normalizeDownloadDays, parseLicenseNumbers } from "./downloadLicenseHelpers";

const DEFAULT_DAYS = 365;

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
    const theme = useTheme();

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

            <Grid container spacing={2}>
                {/* Bulk by numbers */}
                <Grid item xs={12} lg={6}>
                    <Paper sx={{ p: 2, borderRadius: 1 }}>
                        <Box sx={{ mb: 2, pb: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
                            <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <ScanBarcode size={18} />
                                Download by License Numbers
                            </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <Typography variant="body2" color="text.secondary">
                                Enter DFIA license numbers separated by commas or new lines. Each license gets its own sheet.
                            </Typography>
                            <Box>
                                <Typography component="label" htmlFor={bulkInputId} variant="body2" sx={{ mb: 1, fontWeight: 500, display: 'flex', alignItems: 'center' }}>
                                    License Numbers
                                    {parsedCount > 0 && <Chip label={`${parsedCount} entered`} size="small" sx={{ ml: 1 }} />}
                                </Typography>
                                <TextField
                                    id={bulkInputId}
                                    fullWidth
                                    multiline
                                    rows={5}
                                    placeholder="e.g. 3011007415, 3011007018, 3011008321\nor one per line"
                                    value={bulkInput}
                                    onChange={(e) => setBulkInput(e.target.value)}
                                    variant="outlined"
                                    size="small"
                                />
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                    Comma- or newline-separated. Each license = one sheet named after the license number.
                                </Typography>
                            </Box>
                            <MuiButton
                                variant="contained"
                                fullWidth
                                onClick={handleBulkDownload}
                                disabled={bulkLoading || parsedCount === 0}
                                startIcon={bulkLoading ? <Loader2 size={18} /> : <FileSpreadsheet size={18} />}
                            >
                                {bulkLoading ? "Generating…" : `Download Excel (${parsedCount} license${parsedCount !== 1 ? "s" : ""})`}
                            </MuiButton>
                        </Box>
                    </Paper>
                </Grid>

                {/* By status */}
                <Grid item xs={12} lg={6}>
                    <Paper sx={{ p: 2, borderRadius: 1 }}>
                        <Box sx={{ mb: 2, pb: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
                            <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Funnel size={18} />
                                Download by Status
                            </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <Typography variant="body2" color="text.secondary">
                                Export all active or expiring licenses filtered by date range.
                            </Typography>

                            <Box>
                                <Typography variant="body2" sx={{ mb: 1, fontWeight: 500 }}>
                                    License Status
                                </Typography>
                                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                                    {STATUS_OPTIONS.map(({ value, label, Icon }) => {
                                        const active = licenseStatus === value;
                                        return (
                                            <MuiButton
                                                key={value}
                                                variant={active ? "contained" : "outlined"}
                                                size="small"
                                                onClick={() => setLicenseStatus(value)}
                                                startIcon={<Icon size={16} />}
                                            >
                                                {label}
                                            </MuiButton>
                                        );
                                    })}
                                </Stack>
                            </Box>

                            <Box>
                                <Typography component="label" htmlFor={daysInputId} variant="body2" sx={{ mb: 1, fontWeight: 500, display: 'block' }}>
                                    {licenseStatus === "expiring" ? "Expiring within (days)" : "Look-back period (days)"}
                                </Typography>
                                <TextField
                                    id={daysInputId}
                                    type="number"
                                    fullWidth
                                    inputProps={{ min: MIN_DAYS, max: MAX_DAYS }}
                                    value={days}
                                    onChange={(e) => setDays(normalizeDownloadDays(e.target.value))}
                                    variant="outlined"
                                    size="small"
                                />
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                    {licenseStatus === "expiring"
                                        ? `Licenses expiring within the next ${days} days`
                                        : `Active licenses expiring from ${days} days ago onward`}
                                </Typography>
                            </Box>

                            {/* Active Filters Display */}
                            <DownloadLicenseActiveFiltersDisplay
                                licenseStatus={licenseStatus}
                                days={days}
                                onRemoveFilter={(key) => {
                                    if (key === 'licenseStatus') setLicenseStatus('active');
                                    if (key === 'days') setDays(DEFAULT_DAYS);
                                }}
                                onClearAll={() => {
                                    setLicenseStatus('active');
                                    setDays(DEFAULT_DAYS);
                                }}
                            />

                            <MuiButton
                                variant="contained"
                                fullWidth
                                onClick={handleDownload}
                                disabled={loading}
                                startIcon={loading ? <Loader2 size={18} /> : <FileSpreadsheet size={18} />}
                            >
                                {loading ? "Generating…" : "Download Excel"}
                            </MuiButton>
                        </Box>
                    </Paper>
                </Grid>

                {/* Info */}
                <Grid item xs={12}>
                    <Paper sx={{ p: 2, borderRadius: 1 }}>
                        <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                            <Info size={18} />
                            Excel Report Includes
                        </Typography>
                        <Grid container spacing={2}>
                            {EXCEL_INCLUDES.map((f, i) => (
                                <Grid item xs={12} sm={6} lg={4} key={i}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <CheckCircle2 size={16} style={{ flexShrink: 0, color: theme.palette.success.main }} />
                                        <Typography variant="body2" color="text.secondary">{f}</Typography>
                                    </Box>
                                </Grid>
                            ))}
                        </Grid>
                    </Paper>
                </Grid>
            </Grid>
        </>
    );
}

/**
 * DownloadLicenseActiveFiltersDisplay — shows active status and days filters
 */
function DownloadLicenseActiveFiltersDisplay({
    licenseStatus,
    days,
    onRemoveFilter,
    onClearAll,
}: {
    licenseStatus: LicenseStatus;
    days: number;
    onRemoveFilter: (key: string) => void;
    onClearAll: () => void;
}) {
    const statusLabel = STATUS_OPTIONS.find(s => s.value === licenseStatus)?.label || 'Unknown';
    const hasFilters = licenseStatus !== 'active' || days !== DEFAULT_DAYS;

    if (!hasFilters) return null;

    return (
        <Box>
            <Typography variant="caption" sx={{ mb: 1, display: 'block', fontWeight: 500 }}>
                Active Filters:
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {licenseStatus !== 'active' && (
                    <Chip
                        label={`Status: ${statusLabel}`}
                        onDelete={() => onRemoveFilter('licenseStatus')}
                        size="small"
                        variant="outlined"
                    />
                )}
                {days !== DEFAULT_DAYS && (
                    <Chip
                        label={`Days: ${days}`}
                        onDelete={() => onRemoveFilter('days')}
                        size="small"
                        variant="outlined"
                    />
                )}
                {hasFilters && (
                    <MuiButton
                        size="small"
                        variant="text"
                        onClick={onClearAll}
                    >
                        Clear All
                    </MuiButton>
                )}
            </Box>
        </Box>
    );
}
