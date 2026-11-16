import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import LicenseRecordWorkspace from "./LicenseRecordWorkspace";

let hasTrading = false;
vi.mock("@/api/axios", () => ({
    default: {
        get: vi.fn((url: string) => {
            if (url.endsWith("/balance-ledger/")) {
                return Promise.resolve({
                    data: {
                        license: {},
                        financial_ledger: { rows: [], summary: { has_trading_activity: hasTrading, missing_purchase_warning: { show_warning: false, message: "" } } },
                        customs_ledger: { rows: [], summary: {} },
                        reconciliation: { financial_ledger_balance: 1, customs_ledger_balance: 1, balance_engine: 1, difference: 0, tolerance: 0.01, matched: true },
                        warnings: [],
                        timeline: [],
                    },
                });
            }
            return Promise.resolve({ data: { rows: [], results: [] } });
        }),
        post: vi.fn(),
    },
}));

function renderWorkspace() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={qc}>
            <MemoryRouter>
                <LicenseRecordWorkspace licenseId={7} canWrite={false} activeTab="overview" onTabChange={vi.fn()} renderHistory={() => null} />
            </MemoryRouter>
        </QueryClientProvider>,
    );
}

describe("LicenseRecordWorkspace reconciliation tab", () => {
    beforeEach(() => vi.clearAllMocks());

    it("is hidden when the licence has no trading activity (same gate as the overview page)", async () => {
        hasTrading = false;
        renderWorkspace();
        await waitFor(() => expect(screen.getByRole("tab", { name: "History" })).toBeInTheDocument());
        await new Promise((r) => setTimeout(r, 50));
        expect(screen.queryByRole("tab", { name: "Reconciliation" })).not.toBeInTheDocument();
    });

    it("is shown when the licence has trading activity", async () => {
        hasTrading = true;
        renderWorkspace();
        expect(await screen.findByRole("tab", { name: "Reconciliation" })).toBeInTheDocument();
    });
});
