import { useId, useState, useMemo } from "react";
import { toast } from "sonner";
import { Download, Loader2, CheckCircle2 } from "lucide-react";
import {
  Box,
  Stack,
  Paper,
  TextField,
  Typography,
  Button as MuiButton,
  useTheme,
} from "@mui/material";

import PageHeader from "@/components/PageHeader";
import ActiveFilters, { type ActiveFilterItem } from "@/components/ActiveFilters";
import { openAuthedFile } from "@/utils/documentDownload";
import { MAX_DAYS, MIN_DAYS, normalizeExportDays } from "./licenseExportHelpers";


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
    const theme = useTheme();
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
        <Box>
            <PageHeader pretitle="Reports" title={title} description={description} />

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 2, mt: 0 }}>
                <Box>
                    <Paper
                        elevation={0}
                        sx={{
                            border: `1px solid ${theme.palette.divider}`,
                            borderRadius: 1,
                            overflow: 'hidden',
                        }}
                    >
                        {/* Card Header */}
                        <Box
                            sx={{
                                borderBottom: `1px solid ${theme.palette.divider}`,
                                px: 3,
                                py: 2,
                            }}
                        >
                            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                                Export Settings
                            </Typography>
                        </Box>

                        {/* Card Content */}
                        <Box sx={{ p: 3 }}>
                            <Stack spacing={3}>
                                <Box>
                                    <Typography
                                        component="label"
                                        htmlFor={daysInputId}
                                        variant="body2"
                                        sx={{ display: 'block', mb: 1.5, fontWeight: 500 }}
                                    >
                                        {daysLabel}
                                    </Typography>
                                    <TextField
                                        id={daysInputId}
                                        type="number"
                                        slotProps={{
                                            htmlInput: {
                                                min: MIN_DAYS,
                                                max: MAX_DAYS,
                                            },
                                        }}
                                        value={days}
                                        onChange={(e) => setDays(normalizeExportDays(e.target.value, defaultDays))}
                                        aria-describedby={daysHelpId}
                                        fullWidth
                                        size="small"
                                    />
                                    <Typography
                                        id={daysHelpId}
                                        variant="caption"
                                        sx={{ display: 'block', mt: 1, color: 'text.secondary' }}
                                    >
                                        {helpText(days)}
                                    </Typography>
                                </Box>

                                {/* Active Filters Display */}
                                <LicenseExportPanelActiveFiltersDisplay
                                    days={days}
                                    defaultDays={defaultDays}
                                    onRemoveFilter={() => setDays(normalizeExportDays(defaultDays))}
                                    onClearAll={() => setDays(normalizeExportDays(defaultDays))}
                                />

                                <MuiButton
                                    variant="contained"
                                    onClick={handleExport}
                                    disabled={loading}
                                    startIcon={loading ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                                >
                                    {loading ? "Generating…" : "Download Excel Report"}
                                </MuiButton>
                            </Stack>
                        </Box>
                    </Paper>
                </Box>

                {features.length > 0 && (
                    <Box>
                        <Paper
                            elevation={0}
                            sx={{
                                border: `1px solid ${theme.palette.divider}`,
                                borderRadius: 1,
                                overflow: 'hidden',
                            }}
                        >
                            {/* Card Header */}
                            <Box
                                sx={{
                                    borderBottom: `1px solid ${theme.palette.divider}`,
                                    px: 3,
                                    py: 2,
                                }}
                            >
                                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                                    Report Features
                                </Typography>
                            </Box>

                            {/* Card Content */}
                            <Box sx={{ p: 3 }}>
                                <Stack component="ul" spacing={1.5} sx={{ listStyle: 'none', p: 0, m: 0 }}>
                                    {features.map((f, i) => (
                                        <Stack
                                            key={`${f}-${i}`}
                                            component="li"
                                            direction="row"
                                            spacing={1.5}
                                            sx={{ alignItems: 'flex-start' }}
                                        >
                                            <CheckCircle2
                                                className="size-4 shrink-0"
                                                style={{ marginTop: 2, color: theme.palette.success.main }}
                                            />
                                            <Typography variant="body2" sx={{ pt: 0.25 }}>
                                                {f}
                                            </Typography>
                                        </Stack>
                                    ))}
                                </Stack>
                            </Box>
                        </Paper>
                    </Box>
                )}
            </Box>
        </Box>
    );
}

/**
 * LicenseExportPanelActiveFiltersDisplay — shows the active days filter
 */
function LicenseExportPanelActiveFiltersDisplay({
    days,
    defaultDays,
    onRemoveFilter,
    onClearAll,
}: {
    days: number;
    defaultDays: number;
    onRemoveFilter: () => void;
    onClearAll: () => void;
}) {
    const activeFilters: ActiveFilterItem[] = useMemo(() => {
        const items: ActiveFilterItem[] = [];

        if (days !== defaultDays) {
            items.push({
                key: 'days',
                label: 'Days Filter',
                value: `${days} days`,
            });
        }

        return items;
    }, [days, defaultDays]);

    if (activeFilters.length === 0) {
        return null;
    }

    return (
        <Box sx={{ mb: 2 }}>
            <ActiveFilters
                filters={activeFilters}
                onRemove={onRemoveFilter}
                onClearAll={onClearAll}
                showCount={false}
            />
        </Box>
    );
}
