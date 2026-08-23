import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

vi.mock("sonner", () => ({
    toast: {
        error: vi.fn(),
        success: vi.fn(),
        info: vi.fn(),
        warning: vi.fn(),
        loading: vi.fn(() => "toast-id"),
    },
}));

import api from "@/api/axios";
import ReconciliationPanel from "./ReconciliationPanel";

// Only the summary card query + the default ("Missing BOE") tab's query fire
// on mount — the other 7 tabs are lazy (Radix `Tabs.Content` doesn't mount
// inactive panels), so this smoke test only needs to stub those two plus the
// always-visible audit log section.
function mockGet(url: string) {
    if (url === "reconciliation/summary/") {
        return Promise.resolve({
            data: {
                total_boe: 10,
                total_import_invoices: 8,
                matched: 5,
                unmatched_boe: 2,
                unmatched_invoice: 1,
                duplicate_debits: 0,
                cif_difference: 0,
            },
        });
    }
    if (url === "reconciliation/missing-boe/") {
        return Promise.resolve({
            data: {
                results: [
                    {
                        trade_id: 1,
                        invoice_number: "INV-1",
                        company_name: "Acme Exports",
                        invoice_date: "01-01-2026",
                        cif_fc: 1000,
                        qty_kg: 50,
                        licence_number: "LIC-001",
                        sr_number_id: 5,
                    },
                ],
                count: 1,
            },
        });
    }
    if (url === "reconciliation/audit-log/") {
        return Promise.resolve({ data: [] });
    }
    return Promise.resolve({ data: [] });
}

function renderPanel() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={["/reconciliation"]}>
                <ReconciliationPanel />
            </MemoryRouter>
        </QueryClientProvider>,
    );
}

describe("ReconciliationPanel smoke", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        (api.get as ReturnType<typeof vi.fn>).mockImplementation(mockGet);
    });

    it("mounts, loads the summary cards and the default tab without crashing", async () => {
        renderPanel();

        expect(await screen.findByText("BOE / Invoice Reconciliation")).toBeInTheDocument();
        expect(await screen.findByText("Total BOE")).toBeInTheDocument();

        await waitFor(() => {
            expect(screen.getByText("INV-1")).toBeInTheDocument();
        });

        expect(screen.getByText("Missing BOE")).toBeInTheDocument();
        expect(screen.getByText("Duplicate BOEs (Merge)")).toBeInTheDocument();
        expect(screen.getByText("Recalculate Licence Balance")).toBeInTheDocument();
    });
});
