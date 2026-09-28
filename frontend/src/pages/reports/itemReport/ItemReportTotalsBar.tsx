import { Box, Paper, Stack, Typography, useTheme } from "@mui/material";

export interface ItemReportTotalsBarProps {
    items: any[];
}

/** Sticky totals summary shown above the Item Report / Planned Report table. */
export default function ItemReportTotalsBar({ items }: ItemReportTotalsBarProps) {
    const theme = useTheme();

    return (
        <Box sx={{ mb: 4 }}>
            <Paper
                elevation={0}
                sx={{
                    position: 'sticky',
                    top: '70px',
                    zIndex: 1020,
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: 1,
                    p: 2,
                }}
            >
                <Stack direction="row" spacing={3} sx={{ flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end' }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        Total:
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Avail Qty:
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                            {items.reduce((sum, item) => sum + (item.available_quantity || 0), 0).toLocaleString('en-IN', {
                                minimumFractionDigits: 3,
                                maximumFractionDigits: 3
                            })}
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Avail Bal:
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main', fontVariantNumeric: 'tabular-nums' }}>
                            {(() => {
                                const uniqueLicenses: Record<string, number> = {};
                                items.forEach((item: any) => {
                                    if (!uniqueLicenses[item.license_id]) {
                                        // Use canonical license_running_balance, fallback to deprecated available_balance
                                        uniqueLicenses[item.license_id] = item.license_running_balance || item.available_balance || 0;
                                    }
                                });
                                return Object.values(uniqueLicenses).reduce((sum: number, val: number) => sum + val, 0).toLocaleString('en-IN', {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                });
                            })()}
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Balance CIF:
                        </Typography>
                        <Typography variant="body2" sx={{ fontWeight: 600, color: 'info.main', fontVariantNumeric: 'tabular-nums' }}>
                            {(() => {
                                const uniqueLicenses: Record<string, number> = {};
                                items.forEach((item: any) => {
                                    if (!uniqueLicenses[item.license_id]) {
                                        uniqueLicenses[item.license_id] = item.balance_cif || 0;
                                    }
                                });
                                return Object.values(uniqueLicenses).reduce((sum: number, val: number) => sum + val, 0).toLocaleString('en-IN', {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                });
                            })()}
                        </Typography>
                    </Box>
                </Stack>
            </Paper>
        </Box>
    );
}
