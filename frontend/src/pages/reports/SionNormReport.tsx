import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import api from "../../api/axios";
import { toast } from "sonner";
import { formatDate as formatDateUtil } from "../../utils/dateFormatter";
import PageHeader from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Reusable SION Norm Report — licenses for a specific SION norm, grouped by
 * notification. Pure presentation of API data; only markup chrome migrated to
 * Tailwind/shadcn. The dense table render helpers keep their exact data
 * bindings (Bootstrap text-end/text-center utilities remain until Phase 4).
 */
export default function SionNormReport({ sionNorm, title }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState({
        is_expired: "False",
        is_null: "False",
        sion_norm: sionNorm,
    });

    useEffect(() => {
        const fetchReport = async () => {
            try {
                setLoading(true);
                const params = new URLSearchParams(filters).toString();
                const response = await api.get(`licenses/active-dfia-report/?${params}`);
                setData(response.data);
            } catch (error) {
                toast.error("Failed to load report data. Please try again.");
            } finally {
                setLoading(false);
            }
        };
        fetchReport();
    }, [filters]);

    const handleFilterChange = (filterName, value) =>
        setFilters((prev) => ({ ...prev, [filterName]: value }));

    const formatNumber = (num, decimals = 2) => {
        if (num === null || num === undefined) return "—";
        return Number(num).toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return "—";
        return formatDateUtil(dateStr) || "—";
    };

    // Tailwind/token-styled header (replaces Bootstrap table-primary)
    const renderTableHeaders = () => (
        <thead className="sticky top-0 z-10 bg-primary/10 text-[10px] text-foreground [&_th]:border [&_th]:border-border [&_th]:px-1.5 [&_th]:py-1 [&_th]:font-semibold">
            <tr>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '40px'}}>Sr</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '120px'}}>DFIA No</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '90px'}}>DFIA Dt</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '90px'}}>Expiry Dt</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '200px'}}>Exporter</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '100px'}}>Total CIF</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '100px'}}>Balance CIF</th>
                <th colSpan={9} className="text-center">Vegetable Oil</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '80px'}}>10% Bal</th>
                <th colSpan={4} className="text-center">Juice</th>
                <th colSpan={4} className="text-center">Food Flavour</th>
                <th colSpan={2} className="text-center">Fruit</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '60px'}}>Lvng Agt</th>
                <th colSpan={2} className="text-center">Starch 1108</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '60px'}}>Strch 3505</th>
                <th colSpan={8} className="text-center">Milk & Milk</th>
                <th colSpan={3} className="text-center">PP</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '60px'}}>Al Foil</th>
                <th rowSpan={2} style={{verticalAlign: 'middle', minWidth: '80px'}}>Wastage</th>
            </tr>
            <tr>
                <th style={{minWidth: '80px'}}>HSN</th>
                <th style={{minWidth: '120px'}}>PD</th>
                <th style={{minWidth: '70px'}}>Tot Qty</th>
                <th style={{minWidth: '70px'}}>RBD Qty</th>
                <th style={{minWidth: '80px'}}>RBD CIF</th>
                <th style={{minWidth: '70px'}}>PKO Qty</th>
                <th style={{minWidth: '80px'}}>PKO CIF</th>
                <th style={{minWidth: '70px'}}>Olv Qty</th>
                <th style={{minWidth: '80px'}}>Olv CIF</th>
                <th style={{minWidth: '80px'}}>HSN</th>
                <th style={{minWidth: '100px'}}>PD</th>
                <th style={{minWidth: '70px'}}>Qty</th>
                <th style={{minWidth: '80px'}}>CIF</th>
                <th style={{minWidth: '80px'}}>HSN</th>
                <th style={{minWidth: '100px'}}>PD</th>
                <th style={{minWidth: '60px'}}>FF Qty</th>
                <th style={{minWidth: '60px'}}>DF Qty</th>
                <th style={{minWidth: '60px'}}>Qty</th>
                <th style={{minWidth: '80px'}}>CIF</th>
                <th style={{minWidth: '60px'}}>Qty</th>
                <th style={{minWidth: '80px'}}>CIF</th>
                <th style={{minWidth: '120px'}}>PD</th>
                <th style={{minWidth: '70px'}}>Tot Qty</th>
                <th style={{minWidth: '60px'}}>Chz Qty</th>
                <th style={{minWidth: '80px'}}>Chz CIF</th>
                <th style={{minWidth: '60px'}}>SWP Qty</th>
                <th style={{minWidth: '80px'}}>SWP CIF</th>
                <th style={{minWidth: '60px'}}>WPC Qty</th>
                <th style={{minWidth: '80px'}}>WPC CIF</th>
                <th style={{minWidth: '80px'}}>HSN</th>
                <th style={{minWidth: '100px'}}>PD</th>
                <th style={{minWidth: '60px'}}>Qty</th>
            </tr>
        </thead>
    );

    const renderLicenseRow = (license, index) => (
        <tr key={license.id} className="border-b border-border/60 [&_td]:border [&_td]:border-border/50 [&_td]:px-1.5 [&_td]:py-1" style={{fontSize: '9px'}}>
            <td>{index + 1}</td>
            <td>
                <a href={`/licenses/${license.id}`} target="_blank" rel="noopener noreferrer"
                   className="text-primary no-underline" style={{fontSize: '9px'}}>
                    {license.license_number}
                </a>
            </td>
            <td>{formatDate(license.license_date)}</td>
            <td>{formatDate(license.license_expiry_date)}</td>
            <td style={{fontSize: '8px'}}>{license.exporter_name}</td>
            <td className="text-end">{formatNumber(license.total_cif)}</td>
            <td className="text-end">{formatNumber(license.balance_cif)}</td>
            <td>{license.vegetable_oil?.hsn_code}</td>
            <td style={{fontSize: '7px'}}>{license.vegetable_oil?.description}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil?.total_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil?.rbd_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil?.rbd_cif)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil?.pko_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil?.pko_cif)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil?.olive_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil?.olive_cif)}</td>
            <td className="text-end">{formatNumber(license.ten_percent_balance)}</td>
            <td>{license.juice?.hsn_code}</td>
            <td style={{fontSize: '7px'}}>{license.juice?.description}</td>
            <td className="text-end">{formatNumber(license.juice?.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.juice?.cif)}</td>
            <td>{license.food_flavour?.hsn_code}</td>
            <td style={{fontSize: '7px'}}>{license.food_flavour?.description}</td>
            <td className="text-end">{formatNumber(license.food_flavour?.ff_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.food_flavour?.df_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.fruit_cocoa?.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.fruit_cocoa?.cif)}</td>
            <td className="text-end">{formatNumber(license.leavening_agent?.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.starch_1108?.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.starch_1108?.cif)}</td>
            <td className="text-end">{formatNumber(license.starch_3505?.qty, 2)}</td>
            <td style={{fontSize: '7px'}}>{license.milk_and_milk?.description}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk?.total_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk?.cheese_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk?.cheese_cif)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk?.swp_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk?.swp_cif)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk?.wpc_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk?.wpc_cif)}</td>
            <td>{license.pp?.hsn_code}</td>
            <td style={{fontSize: '7px'}}>{license.pp?.description}</td>
            <td className="text-end">{formatNumber(license.pp?.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.aluminium_foil?.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.wastage_cif)}</td>
        </tr>
    );

    const renderTotalsRow = (totals, label) => (
        <tr className="bg-warning/15 font-bold text-warning [&_td]:border [&_td]:border-border/50 [&_td]:px-1.5 [&_td]:py-1" style={{fontSize: '9px'}}>
            <td colSpan={5} className="text-end">{label}:</td>
            <td className="text-end">{formatNumber(totals.total_cif)}</td>
            <td className="text-end">{formatNumber(totals.balance_cif)}</td>
            <td colSpan={2}></td>
            <td className="text-end">{formatNumber(totals.veg_oil_total_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.rbd_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.rbd_cif)}</td>
            <td className="text-end">{formatNumber(totals.pko_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.pko_cif)}</td>
            <td className="text-end">{formatNumber(totals.olive_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.olive_cif)}</td>
            <td className="text-end">{formatNumber(totals.ten_percent_balance)}</td>
            <td colSpan={2}></td>
            <td className="text-end">{formatNumber(totals.juice_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.juice_cif)}</td>
            <td colSpan={2}></td>
            <td className="text-end">{formatNumber(totals.ff_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.df_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.fruit_cocoa_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.fruit_cocoa_cif)}</td>
            <td className="text-end">{formatNumber(totals.leavening_agent_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.starch_1108_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.starch_1108_cif)}</td>
            <td className="text-end">{formatNumber(totals.starch_3505_qty, 2)}</td>
            <td></td>
            <td className="text-end">{formatNumber(totals.milk_total_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.cheese_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.cheese_cif)}</td>
            <td className="text-end">{formatNumber(totals.swp_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.swp_cif)}</td>
            <td className="text-end">{formatNumber(totals.wpc_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.wpc_cif)}</td>
            <td colSpan={2}></td>
            <td className="text-end">{formatNumber(totals.pp_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.aluminium_foil_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.wastage_cif)}</td>
        </tr>
    );

    // Radio filter group
    const FilterRadios = () => (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
                <div className="mb-1.5 text-xs font-medium text-muted-foreground">Active / Expired</div>
                <div className="flex gap-4">
                    {[["False", "Active"], ["True", "Expired"]].map(([val, lbl]) => (
                        <label key={val} className="flex cursor-pointer items-center gap-1.5 text-sm">
                            <input type="radio" className="accent-primary" checked={filters.is_expired === val} onChange={() => handleFilterChange("is_expired", val)} />
                            {lbl}
                        </label>
                    ))}
                </div>
            </div>
            <div>
                <div className="mb-1.5 text-xs font-medium text-muted-foreground">Balance CIF</div>
                <div className="flex gap-4">
                    {[["False", "> 200"], ["True", "< 200"]].map(([val, lbl]) => (
                        <label key={val} className="flex cursor-pointer items-center gap-1.5 text-sm">
                            <input type="radio" className="accent-primary" checked={filters.is_null === val} onChange={() => handleFilterChange("is_null", val)} />
                            {lbl}
                        </label>
                    ))}
                </div>
            </div>
        </div>
    );

    if (loading) {
        return (
            <>
                <PageHeader pretitle="Reports" title={title} />
                <div className="flex items-center gap-2 p-6 text-muted-foreground">
                    <Loader2 className="size-5 animate-spin text-primary" /> Loading…
                </div>
            </>
        );
    }

    if (!data || !data.groups || data.groups.length === 0) {
        return (
            <>
                <PageHeader pretitle="Reports" title={title} />
                <Card className="mb-4"><CardContent className="pt-5"><FilterRadios /></CardContent></Card>
                <p className="text-sm text-muted-foreground">No records found for SION Norm {sionNorm}</p>
            </>
        );
    }

    const sionGroup = data.groups[0];
    let globalSrNo = 0;

    return (
        <>
            <PageHeader pretitle="Reports" title={title} />

            {/* Filters */}
            <Card className="mb-4"><CardContent className="pt-5"><FilterRadios /></CardContent></Card>

            {/* Summary cards */}
            <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                {[
                    ["Total Licenses", sionGroup.license_count],
                    ["Total CIF", formatNumber(sionGroup.totals.total_cif)],
                    ["Balance CIF", formatNumber(sionGroup.totals.balance_cif)],
                ].map(([label, value]) => (
                    <Card key={label}>
                        <CardContent className="pt-5">
                            <div className="text-xs font-medium text-muted-foreground">{label}</div>
                            <div className="mt-1 text-2xl font-semibold tracking-tight text-foreground tabular-nums">{value}</div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Tables by notification */}
            {sionGroup.notifications.map((notifGroup, notifIndex) => (
                <div key={notifIndex} className="mb-4">
                    <div className="mb-3 flex items-center gap-3 rounded-md bg-muted px-3 py-2">
                        <span className="text-sm font-semibold text-foreground">Notification: {notifGroup.notification_number}</span>
                        <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">{notifGroup.license_count} licenses</span>
                    </div>
                    <Card>
                        <CardContent className="p-0">
                            <div className="overflow-auto" style={{maxHeight: '600px'}}>
                                <table className="w-full border-collapse">
                                    {renderTableHeaders()}
                                    <tbody>
                                        {notifGroup.licenses.map((license) => {
                                            globalSrNo++;
                                            return renderLicenseRow(license, globalSrNo - 1);
                                        })}
                                        {renderTotalsRow(notifGroup.totals, `Total - ${notifGroup.notification_number}`)}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            ))}

            {/* Grand total */}
            <Card className="mt-4 border-success/40">
                <div className="rounded-t-xl border-b border-success/30 bg-success/10 px-4 py-2.5 text-sm font-semibold text-success">
                    Grand Total — SION Norm {sionNorm}
                </div>
                <CardContent className="p-0">
                    <div className="overflow-auto">
                        <table className="w-full border-collapse">
                            {renderTableHeaders()}
                            <tbody>{renderTotalsRow(sionGroup.totals, "Grand Total")}</tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </>
    );
}
