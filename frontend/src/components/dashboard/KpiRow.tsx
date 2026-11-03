import type { Financial, LicencePortfolio, SectionError } from "@/pages/dashboardContract";
import { isSectionError } from "@/pages/dashboardContract";
import KpiCard from "./KpiCard";
import { formatCount, formatMoney, formatPercent, UNAVAILABLE } from "./formatters";
import { activeLicencesTarget, licenceList, LIST_PATHS } from "./dashboardLinks";

type KpiRowProps = {
    loading: boolean;
    showLicence: boolean;
    showAllotment: boolean;
    showBoe: boolean;
    financial: Financial | SectionError | undefined;
    portfolio: LicencePortfolio | SectionError | undefined;
    allotmentTotal: number | null;
    boeTotal: number | null;
    companyId: number | null;
};

function contextFor(section: Financial | SectionError | undefined, text: (financial: Financial) => string): string {
    if (!section) return "";
    return isSectionError(section) ? `Unavailable: ${section.error}` : text(section);
}

/**
 * Four primary financial KPIs (one component, every card the same) plus a
 * secondary strip of counts. Figures are from the payload only.
 */
export default function KpiRow({
    loading,
    showLicence,
    showAllotment,
    showBoe,
    financial,
    portfolio,
    allotmentTotal,
    boeTotal,
    companyId,
}: KpiRowProps) {
    const fin = financial && !isSectionError(financial) ? financial : null;
    const port = portfolio && !isSectionError(portfolio) ? portfolio : null;
    const money = (value: string | undefined) => (fin ? formatMoney(value, "cif") : UNAVAILABLE);

    return (
        <section aria-labelledby="dashboard-kpi-title" className="space-y-3">
            <h2 id="dashboard-kpi-title" className="sr-only">
                Key figures
            </h2>

            {showLicence && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <KpiCard
                        label="Authorised CIF"
                        unit="USD (FC)"
                        value={money(fin?.authorized_cif)}
                        loading={loading}
                        context={contextFor(financial, (f) => `${formatCount(f.licences_in_scope)} licences in scope`)}
                        tooltip="Sum of export CIF (credit) across every licence in scope. Foreign currency, not converted."
                        href={licenceList({ is_expired: "all" }, companyId)}
                    />
                    <KpiCard
                        label="Utilised CIF"
                        unit="USD (FC)"
                        value={money(fin?.utilized_cif)}
                        loading={loading}
                        context={contextFor(financial, (f) => `BOE ${formatMoney(f.bridge.boe_utilisation, "cif")} · sale ${formatMoney(f.bridge.sale_utilisation, "cif")}`)}
                        tooltip="BOE debits plus SALE trade lines. Allocation-aware: a BOE already matched to an allotment or invoice is counted once."
                        href={LIST_PATHS.boes}
                    />
                    <KpiCard
                        label="Reserved CIF"
                        unit="USD (FC)"
                        value={money(fin?.reserved_cif)}
                        loading={loading}
                        context={contextFor(financial, (f) => `Committed ${formatPercent(f.committed_pct)} of authorised`)}
                        tooltip="Outstanding allotment CIF from the balance engine. A partly used allotment's unused part is not yet released (ISS-008)."
                        href={LIST_PATHS.allotments}
                    />
                    <KpiCard
                        label="Available CIF"
                        unit="USD (FC)"
                        value={money(fin?.available_cif)}
                        loading={loading}
                        context={contextFor(financial, (f) => `${formatCount(f.over_utilised_licences)} over-utilised licences floored at zero`)}
                        tooltip="Financial available balance from the canonical engine: opening + purchases − sales − BOE debits − outstanding allotments, floored at zero per licence. Business definition pending DEC-010."
                        href={licenceList({ is_expired: false }, companyId)}
                    />
                </div>
            )}

            {(showLicence || showAllotment || showBoe) && (
                <div className="grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-slate-50/60 p-2 dark:border-slate-800 dark:bg-slate-900/40 sm:grid-cols-3 lg:grid-cols-5">
                    {showLicence && (
                        <>
                            <KpiCard variant="compact" label="Total licences" value={formatCount(port?.total)} loading={loading} tooltip="All licence records in scope." href={licenceList({ is_expired: "all" }, companyId)} />
                            <KpiCard variant="compact" label="Active licences" value={formatCount(port?.active)} loading={loading} tooltip="Licences flagged active whose expiry date has not passed." href={activeLicencesTarget(companyId)} />
                            <KpiCard variant="compact" label="Expired licences" value={formatCount(port?.expired)} loading={loading} tooltip="Licences whose expiry date is before the as-of date." href={licenceList({ is_expired: true }, companyId)} />
                        </>
                    )}
                    {showAllotment && (
                        <KpiCard variant="compact" label="Total allotments" value={formatCount(allotmentTotal)} loading={loading} tooltip="All allotments in scope." href={LIST_PATHS.allotments} />
                    )}
                    {showBoe && (
                        <KpiCard variant="compact" label="Total BOEs" value={formatCount(boeTotal)} loading={loading} tooltip="Bills of entry in scope, filtered by bill date and company." href={LIST_PATHS.boes} />
                    )}
                </div>
            )}
        </section>
    );
}
