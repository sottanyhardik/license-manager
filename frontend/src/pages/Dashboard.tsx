import { useContext, useEffect, useMemo, useState } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import { Button } from "@/components/ui/button";
import { REPORT_ROLES } from "@/routes/authorizationRoles";
import AllotmentActivity, { ALLOTMENT_CARD_CLASS } from "@/components/dashboard/AllotmentActivity";
import AttentionCentre from "@/components/dashboard/AttentionCentre";
import { buildAttentionRows } from "@/components/dashboard/attention";
import BoeActivity, { BOE_CARD_CLASS } from "@/components/dashboard/BoeActivity";
import C969ReviewTable from "@/components/dashboard/C969ReviewTable";
import DashboardHeader, { type CompanyOption } from "@/components/dashboard/DashboardHeader";
import DashboardSection from "@/components/dashboard/DashboardSection";
import FinancialOverview from "@/components/dashboard/FinancialOverview";
import InvoiceActivity from "@/components/dashboard/InvoiceActivity";
import KpiRow from "@/components/dashboard/KpiRow";
import LicencePortfolio from "@/components/dashboard/LicencePortfolio";
import QuickActions, { type QuickActionPermissions } from "@/components/dashboard/QuickActions";
import { licenceList } from "@/components/dashboard/dashboardLinks";
import { useDashboardData } from "@/components/dashboard/useDashboardData";
import { formatClockTime } from "@/components/dashboard/formatters";
import { presetToDates, type RangePreset } from "@/components/dashboard/scope";
import { DASHBOARD_SECTION_ROLES, type DashboardResponse } from "./dashboardContract";

const SECTION_HEADING = "text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400";

const BOE_QUICK_ROLES = ["BOE_MANAGER", "TRADE_MANAGER", "ACCOUNT_ACCESS"] as const;

/**
 * Dashboard page: layout, scope state and role gates. Every figure comes from
 * `useDashboardData`; this component computes none.
 */
export default function Dashboard() {
    const { hasAnyRole, isSuperAdmin } = useContext(AuthContext);
    const superuser = isSuperAdmin();
    const allowed = (roles: readonly string[]) => superuser || hasAnyRole([...roles]);

    const canLicence = allowed(DASHBOARD_SECTION_ROLES.licence);
    const canAllotment = allowed(DASHBOARD_SECTION_ROLES.allotment);
    const canBoe = allowed(DASHBOARD_SECTION_ROLES.boe);
    const canInvoice = allowed(DASHBOARD_SECTION_ROLES.invoice);

    const [companyId, setCompanyId] = useState<number | null>(null);
    const [preset, setPreset] = useState<RangePreset>("all");
    const [search, setSearch] = useState("");

    const range = useMemo(() => presetToDates(preset, new Date()), [preset]);
    const { data, refreshing, failed, lastRefreshed, refresh, retrying, retrySection } = useDashboardData({
        companyId,
        dateFrom: range.date_from,
        dateTo: range.date_to,
    });

    const anySection = canLicence || canAllotment || canBoe || canInvoice;
    const [companies, setCompanies] = useState<CompanyOption[]>([]);
    const [companiesUnavailable, setCompaniesUnavailable] = useState(false);
    useEffect(() => {
        if (!anySection) return;
        let active = true;
        api.get("masters/companies/", { params: { page_size: 200 } })
            .then(({ data: body }) => {
                if (!active) return;
                const results = Array.isArray(body?.results) ? body.results : [];
                setCompanies(results.map((company: { id: number; name: string }) => ({ id: company.id, name: company.name })));
            })
            .catch(() => {
                if (active) setCompaniesUnavailable(true);
            });
        return () => {
            active = false;
        };
    }, [anySection]);

    const payload: DashboardResponse | null = data;
    const isLoading = payload === null;
    const showLicence = canLicence && (isLoading || payload.licence_portfolio !== undefined);
    const showAllotment = canAllotment && (isLoading || payload.allotment_activity !== undefined);
    const showBoe = canBoe && (isLoading || payload.boe_activity !== undefined);
    const showInvoice = canInvoice && (isLoading || payload.invoice_activity !== undefined);
    const asOf = payload?.meta.as_of ?? null;
    const notifications = payload ? buildAttentionRows(payload.attention, companyId) : null;

    const quickActions: QuickActionPermissions = {
        newLicence: allowed(["LICENSE_MANAGER"]),
        newAllotment: allowed(["ALLOTMENT_MANAGER"]),
        newBoe: allowed(["BOE_MANAGER"]),
        newInvoice: allowed(["TRADE_MANAGER"]),
        reconciliation: allowed(BOE_QUICK_ROLES),
        reports: allowed(REPORT_ROLES),
    };

    const errorBanner = failed ? (
        <div
            role="alert"
            className="flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-900/30 dark:bg-red-950/30 dark:text-red-200"
        >
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
            <span className="flex-1">
                {payload
                    ? `Some dashboard data may be unavailable. The last successful result is still shown (updated ${formatClockTime(lastRefreshed)}).`
                    : "The dashboard could not be loaded."}
            </span>
            <Button variant="secondary" size="sm" onClick={refresh}>
                <RotateCcw className="size-3.5" aria-hidden="true" />
                Retry
            </Button>
        </div>
    ) : null;

    const header = (
        <DashboardHeader
        asOf={asOf}
        asOfTimezone={payload?.meta.as_of_timezone ?? null}
        lastRefreshed={lastRefreshed}
        refreshing={refreshing}
        onRefresh={refresh}
        companies={companies}
        companiesUnavailable={companiesUnavailable}
        companyId={companyId}
        onCompanyChange={setCompanyId}
        preset={preset}
        onPresetChange={setPreset}
        search={search}
        onSearchChange={setSearch}
        notifications={notifications}
    />
    );

    if (payload === null && failed) {
        return (
            <section className="dashboard-page space-y-6" aria-label="Dashboard overview">
                {header}
                {errorBanner}
            </section>
        );
    }

    return (
        <section className="dashboard-page space-y-6" aria-label="Dashboard overview" aria-busy={isLoading || refreshing || undefined}>
            {header}

            {errorBanner}

            <QuickActions permissions={quickActions} />

            {(showLicence || showAllotment || showBoe || showInvoice) && (
                <KpiRow
                    loading={isLoading}
                    showLicence={showLicence}
                    showAllotment={showAllotment}
                    showBoe={showBoe}
                    financial={payload?.financial}
                    portfolio={payload?.licence_portfolio}
                    allotmentTotal={payload?.allotment_activity && !("error" in payload.allotment_activity) ? payload.allotment_activity.total : null}
                    boeTotal={payload?.boe_activity && !("error" in payload.boe_activity) ? payload.boe_activity.total : null}
                    companyId={companyId}
                />
            )}

            {(isLoading || payload) && (
                <div className={showLicence ? "grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]" : "grid grid-cols-1 gap-6"}>
                    {payload ? (
                        <AttentionCentre
                            items={payload.attention}
                            notMonitored={payload.not_monitored}
                            exceptions={payload.licence_exceptions}
                            companyId={companyId}
                        />
                    ) : (
                        <DashboardSection title="Attention required" loading />
                    )}
                    {showLicence && (
                        <DashboardSection
                            id="dashboard-financial"
                            title="Financial overview"
                            description="Authorised to available CIF, in USD (FC). Values come from the balance engine."
                            loading={isLoading}
                            error={payload?.financial && "error" in payload.financial ? payload.financial.error : null}
                        >
                            {payload?.financial && !("error" in payload.financial) && (
                                <FinancialOverview financial={payload.financial} licencesHref={licenceList({ is_expired: "all" }, companyId)} />
                            )}
                        </DashboardSection>
                    )}
                </div>
            )}

            {showLicence && (
                <section aria-labelledby="dashboard-licence-title" className="space-y-4">
                    <h2 id="dashboard-licence-title" className={SECTION_HEADING}>
                        Licence portfolio
                    </h2>
                    {isLoading ? (
                        <DashboardSection title="Expiring licences" loading />
                    ) : (
                        <>
                            <LicencePortfolio
                                portfolio={payload.licence_portfolio}
                                expiring={payload.expiring_licences}
                                asOf={payload.meta.as_of}
                                companyId={companyId}
                                search={search}
                            />
                            <C969ReviewTable review={payload.c969_link_review} search={search} />
                        </>
                    )}
                </section>
            )}

            {(showAllotment || showBoe) && (
                <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                    {showAllotment &&
                        (isLoading ? (
                            <DashboardSection title="Allotment activity" className={ALLOTMENT_CARD_CLASS} loading />
                        ) : (
                            <AllotmentActivity
                                section={payload.allotment_activity}
                                search={search}
                                allotmentsHref="/allotments"
                                retrying={retrying.has("allotment_activity")}
                                onRetry={() => retrySection("allotment_activity")}
                            />
                        ))}
                    {showBoe &&
                        (isLoading ? (
                            <DashboardSection title="BOE activity" className={BOE_CARD_CLASS} loading />
                        ) : (
                            <BoeActivity
                                section={payload.boe_activity}
                                search={search}
                                retrying={retrying.has("boe_activity")}
                                onRetry={() => retrySection("boe_activity")}
                            />
                        ))}
                </div>
            )}

            {showInvoice &&
                (isLoading ? (
                    <DashboardSection title="Invoice activity" loading />
                ) : (
                    <InvoiceActivity
                        section={payload.invoice_activity}
                        search={search}
                        retrying={retrying.has("invoice_activity")}
                        onRetry={() => retrySection("invoice_activity")}
                    />
                ))}

            <p className="text-xs text-slate-500 dark:text-slate-400">
                Notes: BOE and invoice links open the unfiltered lists. Activity date presets use your local date, while the as-of date is UTC.
            </p>

            {!anySection && (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                    Your account has no dashboard sections. Ask an administrator for a role that includes a dashboard view.
                </p>
            )}
        </section>
    );
}
