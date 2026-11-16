import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";

const get = vi.fn();
vi.mock("@/api/axios", () => ({ default: { get: (...a: unknown[]) => get(...a) } }));

import { useReconTabQuery } from "./useReconTabQuery";
import ReconPagination from "./ReconPagination";

const ROWS = Array.from({ length: 120 }, (_, i) => ({ id: i + 1 }));

function Tab({ tabKey }: { tabKey: string }) {
    const { data, pagination } = useReconTabQuery(tabKey, `reconciliation/${tabKey}/`);
    return (
        <div>
            <ul>{(data ?? []).map((r) => <li key={String(r.id)}>row-{String(r.id)}</li>)}</ul>
            <ReconPagination pagination={pagination} />
        </div>
    );
}

function Loc() {
    return <span data-testid="loc">{useLocation().search}</span>;
}

function Harness({ initial = "/", tab = "missing-boe" }: { initial?: string; tab?: string }) {
    return (
        <QueryClientProvider client={new QueryClient()}>
            <MemoryRouter initialEntries={[initial]}>
                <Tab tabKey={tab} />
                <Loc />
            </MemoryRouter>
        </QueryClientProvider>
    );
}

describe("reconciliation tab pagination", () => {
    beforeEach(() => {
        get.mockReset();
        get.mockImplementation(async (_u: string, { params }: { params: { page: number; page_size: number } }) => {
            const start = (params.page - 1) * params.page_size;
            return { data: { count: 120, results: ROWS.slice(start, start + params.page_size) } };
        });
    });

    it("1 GET on load, 1 per page change, page in URL", async () => {
        render(<Harness />);
        await screen.findByText("row-1");
        expect(get).toHaveBeenCalledTimes(1);
        expect(get.mock.calls[0][1].params).toEqual({ page: 1, page_size: 50 });
        fireEvent.click(screen.getByRole("button", { name: "Page 3" }));
        await screen.findByText("row-120");
        await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
        expect(screen.getByTestId("loc").textContent).toBe("?missing-boe_page=3");
        expect(get.mock.calls.every((c) => c[1].params.page_size <= 200)).toBe(true);
    });

    it("deep link restores the tab's page", async () => {
        render(<Harness initial="/?missing-boe_page=3" />);
        await screen.findByText("row-101");
        expect(get).toHaveBeenCalledTimes(1);
        expect(get.mock.calls[0][1].params).toEqual({ page: 3, page_size: 50 });
    });

    it("tabs do not clash: another tab's page param is ignored", async () => {
        render(<Harness initial="/?missing-boe_page=3" tab="missing-invoice" />);
        await screen.findByText("row-1");
        expect(get.mock.calls[0][1].params.page).toBe(1);
    });
});
