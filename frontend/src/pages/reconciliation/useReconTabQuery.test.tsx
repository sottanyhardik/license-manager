import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const get = vi.fn();
vi.mock("@/api/axios", () => ({ default: { get: (...a: unknown[]) => get(...a) } }));

import { useReconTabQuery } from "./useReconTabQuery";
import ReconPagination from "./ReconPagination";

const ROWS = Array.from({ length: 120 }, (_, i) => ({ id: i + 1 }));

function Tab() {
    const { data, pagination } = useReconTabQuery("missing-boe", "reconciliation/missing-boe/");
    return (
        <div>
            <ul>{(data ?? []).map((r) => <li key={String(r.id)}>row-{String(r.id)}</li>)}</ul>
            <ReconPagination pagination={pagination} />
        </div>
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

    it("can reach row 120 across 3 pages", async () => {
        render(<QueryClientProvider client={new QueryClient()}><Tab /></QueryClientProvider>);
        await screen.findByText("row-1");
        fireEvent.click(screen.getByRole("button", { name: "Page 3" }));
        await screen.findByText("row-120");
        expect(get.mock.calls.every((c) => c[1].params.page_size <= 200)).toBe(true);
        await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    });
});
