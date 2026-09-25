import { Card, CardContent } from "@/components/ui/card";

export interface ItemReportTotalsBarProps {
    items: any[];
}

/** Sticky totals summary shown above the Item Report / Planned Report table. */
export default function ItemReportTotalsBar({ items }: ItemReportTotalsBarProps) {
    return (
        <div className="mb-4">
            <Card className="sticky top-[70px] z-[1020]">
                <CardContent className="py-3 px-4">
                    <div className="flex flex-wrap items-center justify-end gap-4">
                        <div className="font-semibold">Total:</div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs sm:text-sm text-muted-foreground">Avail Qty:</span>
                            <span className="font-semibold tabular-nums">
                                {items.reduce((sum, item) => sum + (item.available_quantity || 0), 0).toLocaleString('en-IN', {
                                    minimumFractionDigits: 3,
                                    maximumFractionDigits: 3
                                })}
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs sm:text-sm text-muted-foreground">Avail Bal:</span>
                            <span className="font-semibold text-green-700 tabular-nums">
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
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs sm:text-sm text-muted-foreground">Balance CIF:</span>
                            <span className="font-semibold text-blue-700 tabular-nums">
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
                            </span>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
