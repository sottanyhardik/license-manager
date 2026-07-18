import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import api from "../../api/axios";
import { toast } from "sonner";
import { formatDate as formatDateUtil } from "../../utils/dateFormatter";
import PageHeader from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";

type SionNormReportProps = {
    sionNorm: string;
    title: string;
};

type SionReportFilters = {
    is_expired: string;
    is_null: string;
    sion_norm: string;
};

type ReportValueMap = Record<string, unknown>;

const BOOLEAN_FILTER_VALUES = new Set(["False", "True"]);

export function normalizeBooleanFilter(value: unknown, fallback = "False"): string {
    const normalized = String(value ?? "").trim();
    return BOOLEAN_FILTER_VALUES.has(normalized) ? normalized : fallback;
}

export function formatReportNumber(value: unknown, decimals = 2): string {
    if (value === null || value === undefined || value === "") return "—";

    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return "—";

    const fractionDigits = Number.isInteger(decimals) && decimals >= 0 && decimals <= 6 ? decimals : 2;
    return parsed.toLocaleString("en-IN", {
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
    });
}

export function buildSionReportPath(filters: SionReportFilters): string {
    const params = new URLSearchParams({
        is_expired: normalizeBooleanFilter(filters.is_expired),
        is_null: normalizeBooleanFilter(filters.is_null),
        sion_norm: String(filters.sion_norm ?? "").trim(),
    });

    return `licenses/active-dfia-report/?${params.toString()}`;
}

export function getSionReportGroups(data: unknown): any[] {
    if (!data || typeof data !== "object" || !("groups" in data)) {
        return [];
    }

    return Array.isArray(data.groups) ? data.groups : [];
}

/**
 * Reusable SION Norm Report — licenses for a specific SION norm, grouped by
 * notification. Pure presentation of API data; only markup chrome migrated to
 * Tailwind/shadcn. The dense table render helpers keep their exact data
 * bindings (Bootstrap text-end/text-center utilities remain until Phase 4).
 */
export default function SionNormReport({ sionNorm, title }: SionNormReportProps) {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState({
        is_expired: "False",
        is_null: "False",
        sion_norm: sionNorm,
    });

    useEffect(() => {
        let isMounted = true;

        const fetchReport = async () => {
            try {
                setLoading(true);
                const response = await api.get(buildSionReportPath(filters));
                if (isMounted) {
                    setData(response.data);
                }
            } catch {
                if (isMounted) {
                    toast.error("Failed to load report data. Please try again.");
                    setData(null);
                }
            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        };
        fetchReport();

        return () => {
            isMounted = false;
        };
    }, [filters]);

    useEffect(() => {
        setFilters((prev) => ({ ...prev, sion_norm: sionNorm }));
    }, [sionNorm]);

    const handleFilterChange = (filterName: "is_expired" | "is_null", value: string) =>
        setFilters((prev) => ({ ...prev, [filterName]: normalizeBooleanFilter(value, prev[filterName]) }));

    const formatNumber = (num: unknown, decimals = 2) => {
        return formatReportNumber(num, decimals);
    };

    const formatDate = (dateStr: unknown) => {
        if (!dateStr) return "—";
        return formatDateUtil(String(dateStr)) || "—";
    };

    // Tailwind/token-styled header (replaces Bootstrap table-primary)
    const renderTableHeaders = () => (
        <thead className="sticky top-0 z-10 bg-primary/10 text-[10px] text-foreground [&_th]:border [&_th]:border-border [&_th]:px-1.5 [&_th]:py-1 [&_th]:font-semibold">
            <tr>
                <th scope="col" rowSpan={2} className="min-w-[40px] align-middle">Sr</th>
                <th scope="col" rowSpan={2} className="min-w-[120px] align-middle">DFIA No</th>
                <th scope="col" rowSpan={2} className="min-w-[90px] align-middle">DFIA Dt</th>
                <th scope="col" rowSpan={2} className="min-w-[90px] align-middle">Expiry Dt</th>
                <th scope="col" rowSpan={2} className="min-w-[200px] align-middle">Exporter</th>
                <th scope="col" rowSpan={2} className="min-w-[100px] align-middle">Total CIF</th>
                <th scope="col" rowSpan={2} className="min-w-[100px] align-middle">Balance CIF</th>
                <th scope="colgroup" colSpan={9} className="text-center">Vegetable Oil</th>
                <th scope="col" rowSpan={2} className="min-w-[80px] align-middle">10% Bal</th>
                <th scope="colgroup" colSpan={4} className="text-center">Juice</th>
                <th scope="colgroup" colSpan={4} className="text-center">Food Flavour</th>
                <th scope="colgroup" colSpan={2} className="text-center">Fruit</th>
                <th scope="col" rowSpan={2} className="min-w-[60px] align-middle">Lvng Agt</th>
                <th scope="colgroup" colSpan={2} className="text-center">Starch 1108</th>
                <th scope="col" rowSpan={2} className="min-w-[60px] align-middle">Strch 3505</th>
                <th scope="colgroup" colSpan={8} className="text-center">Milk &amp; Milk</th>
                <th scope="colgroup" colSpan={3} className="text-center">PP</th>
                <th scope="col" rowSpan={2} className="min-w-[60px] align-middle">Al Foil</th>
                <th scope="col" rowSpan={2} className="min-w-[80px] align-middle">Wastage</th>
            </tr>
            <tr>
                <th scope="col" className="min-w-[80px]">HSN</th>
                <th scope="col" className="min-w-[120px]">PD</th>
                <th scope="col" className="min-w-[70px]">Tot Qty</th>
                <th scope="col" className="min-w-[70px]">RBD Qty</th>
                <th scope="col" className="min-w-[80px]">RBD CIF</th>
                <th scope="col" className="min-w-[70px]">PKO Qty</th>
                <th scope="col" className="min-w-[80px]">PKO CIF</th>
                <th scope="col" className="min-w-[70px]">Olv Qty</th>
                <th scope="col" className="min-w-[80px]">Olv CIF</th>
                <th scope="col" className="min-w-[80px]">HSN</th>
                <th scope="col" className="min-w-[100px]">PD</th>
                <th scope="col" className="min-w-[70px]">Qty</th>
                <th scope="col" className="min-w-[80px]">CIF</th>
                <th scope="col" className="min-w-[80px]">HSN</th>
                <th scope="col" className="min-w-[100px]">PD</th>
                <th scope="col" className="min-w-[60px]">FF Qty</th>
                <th scope="col" className="min-w-[60px]">DF Qty</th>
                <th scope="col" className="min-w-[60px]">Qty</th>
                <th scope="col" className="min-w-[80px]">CIF</th>
                <th scope="col" className="min-w-[60px]">Qty</th>
                <th scope="col" className="min-w-[80px]">CIF</th>
                <th scope="col" className="min-w-[120px]">PD</th>
                <th scope="col" className="min-w-[70px]">Tot Qty</th>
                <th scope="col" className="min-w-[60px]">Chz Qty</th>
                <th scope="col" className="min-w-[80px]">Chz CIF</th>
                <th scope="col" className="min-w-[60px]">SWP Qty</th>
                <th scope="col" className="min-w-[80px]">SWP CIF</th>
                <th scope="col" className="min-w-[60px]">WPC Qty</th>
                <th scope="col" className="min-w-[80px]">WPC CIF</th>
                <th scope="col" className="min-w-[80px]">HSN</th>
                <th scope="col" className="min-w-[100px]">PD</th>
                <th scope="col" className="min-w-[60px]">Qty</th>
            </tr>
        </thead>
    );

    const renderLicenseRow = (license, index) => {
        const licenseId = license?.id ?? license?.license_id;
        const licenseNumber = license?.license_number || "—";

        return (
        <tr key={licenseId ?? `license-${index}`} className="border-b border-border/60 [&_td]:border [&_td]:border-border/50 [&_td]:px-1.5 [&_td]:py-1" style={{fontSize: '9px'}}>
            <td>{index + 1}</td>
            <td>
                {licenseId ? (
                    <a href={`/licenses/${encodeURIComponent(String(licenseId))}`} target="_blank" rel="noopener noreferrer"
                       className="text-primary no-underline" style={{fontSize: '9px'}}>
                        {licenseNumber}
                    </a>
                ) : licenseNumber}
            </td>
            <td>{formatDate(license.license_date)}</td>
            <td>{formatDate(license.license_expiry_date)}</td>
            <td style={{fontSize: '8px'}}>{license.exporter_name || "—"}</td>
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
    };

    const renderTotalsRow = (totals: ReportValueMap = {}, label: string) => (
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
            <fieldset>
                <legend className="mb-1.5 text-xs font-medium text-muted-foreground">Active / Expired</legend>
                <div className="flex gap-4">
                    {[["False", "Active"], ["True", "Expired"]].map(([val, lbl]) => (
                        <label key={val} className="flex cursor-pointer items-center gap-1.5 text-sm">
                            <input type="radio" name={`${sionNorm}-is-expired`} className="accent-primary" checked={filters.is_expired === val} onChange={() => handleFilterChange("is_expired", val)} />
                            {lbl}
                        </label>
                    ))}
                </div>
            </fieldset>
            <fieldset>
                <legend className="mb-1.5 text-xs font-medium text-muted-foreground">Balance CIF</legend>
                <div className="flex gap-4">
                    {[["False", "> 200"], ["True", "< 200"]].map(([val, lbl]) => (
                        <label key={val} className="flex cursor-pointer items-center gap-1.5 text-sm">
                            <input type="radio" name={`${sionNorm}-is-null`} className="accent-primary" checked={filters.is_null === val} onChange={() => handleFilterChange("is_null", val)} />
                            {lbl}
                        </label>
                    ))}
                </div>
            </fieldset>
        </div>
    );

    if (loading) {
        return (
            <>
                <PageHeader pretitle="Reports" title={title} />
                <div className="flex items-center gap-2 p-6 text-muted-foreground">
                    <Loader2 className="size-5 animate-spin text-primary" aria-hidden="true" /> Loading…
                </div>
            </>
        );
    }

    const groups = getSionReportGroups(data);

    if (groups.length === 0) {
        return (
            <>
                <PageHeader pretitle="Reports" title={title} />
                <Card className="mb-4"><CardContent className="pt-5"><FilterRadios /></CardContent></Card>
                <p className="text-sm text-muted-foreground">No records found for SION Norm {sionNorm}</p>
            </>
        );
    }

    const sionGroup = groups[0] ?? {};
    const notifications = Array.isArray(sionGroup.notifications) ? sionGroup.notifications : [];
    const totals = sionGroup.totals ?? {};
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
                    ["Total CIF", formatNumber(totals.total_cif)],
                    ["Balance CIF", formatNumber(totals.balance_cif)],
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
            {notifications.map((notifGroup, notifIndex) => {
                const licenses = Array.isArray(notifGroup.licenses) ? notifGroup.licenses : [];
                const notificationNumber = notifGroup.notification_number || "—";

                return (
                <div key={`${notificationNumber}-${notifIndex}`} className="mb-4">
                    <div className="mb-3 flex items-center gap-3 rounded-md bg-muted px-3 py-2">
                        <span className="text-sm font-semibold text-foreground">Notification: {notificationNumber}</span>
                        <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">{notifGroup.license_count ?? licenses.length} licenses</span>
                    </div>
                    <Card>
                        <CardContent className="p-0">
                            <div className="overflow-auto" style={{maxHeight: '600px'}}>
                                <table className="w-full border-collapse">
                                    {renderTableHeaders()}
                                    <tbody>
                                        {licenses.map((license) => {
                                            globalSrNo++;
                                            return renderLicenseRow(license, globalSrNo - 1);
                                        })}
                                        {renderTotalsRow(notifGroup.totals, `Total - ${notificationNumber}`)}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>
                </div>
                );
            })}

            {/* Grand total */}
            <Card className="mt-4 border-success/40">
                <div className="rounded-t-xl border-b border-success/30 bg-success/10 px-4 py-2.5 text-sm font-semibold text-success">
                    Grand Total — SION Norm {sionNorm}
                </div>
                <CardContent className="p-0">
                    <div className="overflow-auto">
                        <table className="w-full border-collapse">
                            {renderTableHeaders()}
                            <tbody>{renderTotalsRow(totals, "Grand Total")}</tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </>
    );
}
