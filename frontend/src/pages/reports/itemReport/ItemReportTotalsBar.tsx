import { Card, CardContent } from "@/components/ui/card";

export interface ItemReportTotalsBarProps {
    items: any[];
}

/** Sticky totals summary shown above the Item Report / Planned Report table. */
export default function ItemReportTotalsBar({ items }: ItemReportTotalsBarProps) {
    return (
        <div className="row mb-3">
            <div className="col-span-full">
                <Card style={{ position: 'sticky', top: '70px', zIndex: 1020 }}>
                    <CardContent className="py-2">
                        <div className="flex justify-end items-center gap-4">
                            <div className="font-bold">Total:</div>
                            <div className="flex items-center gap-2">
                                <span className="text-muted-foreground text-sm">Avail Qty:</span>
                                <span className="font-bold">
                                    {items.reduce((sum, item) => sum + (item.available_quantity || 0), 0).toLocaleString('en-IN', {
                                        minimumFractionDigits: 3,
                                        maximumFractionDigits: 3
                                    })}
                                </span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-muted-foreground text-sm">Avail Bal:</span>
                                <span className="font-bold text-success">
                                    {(() => {
                                        const uniqueLicenses: Record<string, number> = {};
                                        items.forEach((item: any) => {
                                            if (!uniqueLicenses[item.license_id]) {
                                                uniqueLicenses[item.license_id] = item.available_balance || 0;
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
                                <span className="text-muted-foreground text-sm">Balance CIF:</span>
                                <span className="font-bold text-primary">
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
        </div>
    );
}
