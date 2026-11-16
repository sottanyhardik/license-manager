import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { invalidateLicence, qk } from "@/lib/queryKeys";
import { licenseBalanceKeys } from "@/pages/license-balance/useLicenseBalanceLedger";
import LicenseOverviewPage from "./LicenseOverviewPage";
import { licenseOverviewKeys } from "./useLicenseOverviewSummary";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("@/utils/documentDownload", () => ({ openDocument: vi.fn(), openAuthedFile: vi.fn() }));
vi.mock("@/utils/pdfPreview", () => ({ openPdfPreview: vi.fn() }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/PageHeader", () => ({
    default: ({ title, actions }: { title: string; actions: React.ReactNode }) => <header><h1>{title}</h1>{actions}</header>,
}));
vi.mock("@/components/PermissionGate", () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("./ReplanStatus", () => ({ default: () => null }));

const mockedGet = vi.mocked(api.get);
const summary = {
    license_number: "L-9", authorisation_number: null, file_number: null, license_date: null, license_expiry_date: null,
    importer: null, status: "Active", purchase_status_id: null, purchase_status_code: null, purchase_status_label: null,
    port_code: null, port_name: null,
    summary: { total_boes: 0, total_allotments: 0, total_planned_cif: 0, total_cif: 0, total_debited_cif: 0, total_allotted_cif: 0, total_balance_cif: 0 },
};
const ledger = {
    license: {},
    financial_ledger: { rows: [], summary: { has_trading_activity: false, missing_purchase_warning: { show_warning: false, message: "" } } },
    customs_ledger: { rows: [], summary: {} },
    reconciliation: { financial_ledger_balance: 1, customs_ledger_balance: 1, balance_engine: 1, difference: 0, tolerance: 0.01, matched: true },
    warnings: [],
    timeline: [],
};
const detail = { license_documents: [], export_license: [{ id: 1, norm_class: null, norm_class_detail: null }], import_license: [] };

function installApi() {
    mockedGet.mockImplementation((url: string) => {
        if (url.endsWith("overview-summary/")) return Promise.resolve({ data: summary });
        if (url.endsWith("/balance-ledger/")) return Promise.resolve({ data: ledger });
        if (/^licenses\/\d+\/$/.test(url)) return Promise.resolve({ data: detail });
        return Promise.resolve({ data: [] });
    });
}
const detailGets = (id: number) => mockedGet.mock.calls.filter(([u]) => u === `licenses/${id}/`).length;

function renderPage(queryClient: QueryClient, entry = "/licenses/9/overview") {
    return render(
        <QueryClientProvider client={queryClient}>
            <AuthContext.Provider value={{ hasRole: () => true } as never}>
                <MemoryRouter initialEntries={[entry]}>
                    <Routes><Route path="/licenses/:id/overview" element={<LicenseOverviewPage />} /></Routes>
                </MemoryRouter>
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
}
const newClient = () => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } });

describe("licence query keys", () => {
    beforeEach(() => { vi.clearAllMocks(); installApi(); });

    it("issues one licenses/:id/ GET across the Overview and Planning tabs (was 3)", async () => {
        renderPage(newClient());
        await waitFor(() => expect(mockedGet.mock.calls.some(([u]) => String(u).endsWith("overview-summary/"))).toBe(true));
        await waitFor(() => expect(detailGets(9)).toBeGreaterThan(0));
        await userEvent.click(await screen.findByRole("tab", { name: /planning/i }));
        await waitFor(() => expect(mockedGet.mock.calls.some(([u]) => String(u).includes("item-plan"))).toBe(true));
        expect(detailGets(9)).toBe(1);
    });

    it("shares the cache between the register card and the overview page", async () => {
        const qc = newClient();
        // register card expand populates the ledger under the shared key
        await qc.fetchQuery({ queryKey: licenseBalanceKeys.ledger(9), queryFn: () => ledger });
        expect(qc.getQueryState(qk.licenses.ledger("9"))?.dataUpdatedAt).toBeGreaterThan(0);
        renderPage(qc);
        await waitFor(() => expect(detailGets(9)).toBe(1));
        expect(mockedGet.mock.calls.filter(([u]) => String(u).includes("balance-ledger"))).toHaveLength(0);
    });

    it("invalidateLicence refetches every active licence query for that licence", async () => {
        const qc = newClient();
        renderPage(qc);
        await waitFor(() => expect(detailGets(9)).toBe(1));
        const summaryCalls = () => mockedGet.mock.calls.filter(([u]) => String(u).endsWith("overview-summary/")).length;
        await waitFor(() => expect(summaryCalls()).toBe(1));
        await invalidateLicence(qc, 9);
        await waitFor(() => expect(detailGets(9)).toBe(2));
        await waitFor(() => expect(summaryCalls()).toBe(2));
    });

    it("keeps licences isolated and wrappers on the shared prefix", () => {
        expect(licenseOverviewKeys.summary(1)).not.toEqual(licenseOverviewKeys.summary(2));
        expect(licenseBalanceKeys.ledger(1)).not.toEqual(licenseBalanceKeys.ledger(2));
        expect(qk.licenses.detail("1")).not.toEqual(qk.licenses.detail("2"));
        const prefix = qk.licenses.detail("1");
        for (const k of [licenseOverviewKeys.summary(1), licenseOverviewKeys.items(1), licenseOverviewKeys.boes(1),
            licenseOverviewKeys.allotments(1), licenseOverviewKeys.invoiceLedger(1), licenseBalanceKeys.ledger(1), licenseBalanceKeys.ledger(1, true)]) {
            expect(k.slice(0, 3)).toEqual(prefix);
        }
        expect(licenseOverviewKeys.planning(1)).toEqual(prefix);
        expect(licenseBalanceKeys.ledger(1)).toEqual(licenseBalanceKeys.ledger("1"));
    });
});
