import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import api from "@/api/axios";
import MappingChanges from "./MappingChanges";

const change = (version: number, status: string, extra = {}) => ({ version, kind: "MATCH_DECISION", status, source_refs: [1], import_items: 3, licences: 1, error: status === "FAILED" ? "licence 7: SION rule failed" : "",
    retries: 0, created_by: "mgr", created_on: "2026-11-19T00:00:00Z", completed_on: null, detail: {}, ...extra });
const impact = {
    change: change(2, "PUBLISHED"), provisional: false,
    totals: { before_planned_cif: "80.00", after_planned_cif: "60.00", before_boe_cif: "5.00", after_boe_cif: "5.00", before_allotment_cif: "0", after_allotment_cif: "0" },
    licences: [{ license_id: 7, license_number: "LIC-7", stale: false, superseded_lines: 1, active_lines: 1,
        items: [{ item: "PIVOT MILK", before_qty: "40", after_qty: "0", before_cif: "80", after_cif: "0", changed: true }, { item: "ALUMINIUM FOIL", before_qty: "0", after_qty: "30", before_cif: "0", after_cif: "60", changed: true }],
        actual: { boe_cif: { before: "5", after: "5" }, allotment_cif: { before: "0", after: "0" }, available_cif: { before: "900", after: "900" } }, replan: { status: "succeeded", error: "", failures: [] } }],
};

function setup(canRetry = true) {
    vi.mocked(api.get).mockImplementation(async (url: string) => (url.endsWith("mapping-changes/") ? { data: { changes: [change(3, "FAILED"), change(2, "PUBLISHED"), change(1, "NO_PLANNING_IMPACT", { kind: "MULTI_PRODUCT" })], can_retry: canRetry } } : { data: impact }));
    vi.mocked(api.post).mockResolvedValue({ data: {} });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MappingChanges /></QueryClientProvider>);
    return userEvent.setup();
}

beforeEach(() => vi.clearAllMocks());

describe("Mapping changes", () => {
    it("lists versions with propagation status and errors", async () => {
        setup();
        const table = await screen.findByRole("table", { name: "Mapping changes" });
        expect(within(table).getByText("Propagation failed")).toBeInTheDocument();
        expect(within(table).getByText("licence 7: SION rule failed")).toBeInTheDocument();
        expect(within(table).getByText("Item Pivot only")).toBeInTheDocument();
    });

    it("shows before / after plan impact per debit item with actuals separate", async () => {
        const user = setup();
        await user.click(await screen.findByRole("button", { name: "Impact of version 2" }));
        const plan = await screen.findByRole("table", { name: "Plan impact for LIC-7" });
        expect(within(plan).getByText("PIVOT MILK")).toBeInTheDocument();
        expect(within(plan).getByText("ALUMINIUM FOIL")).toBeInTheDocument();
        expect(screen.getByLabelText("Impact totals")).toHaveTextContent("80 → 60");
    });

    it("retries a failed change only with permission", async () => {
        const user = setup();
        await screen.findByRole("table", { name: "Mapping changes" });
        await user.click(screen.getByRole("button", { name: /Retry/ }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/mapping-changes/3/retry/"));
    });

    it("hides retry for viewers", async () => {
        setup(false);
        await screen.findByRole("table", { name: "Mapping changes" });
        expect(screen.queryByRole("button", { name: /Retry/ })).toBeNull();
    });
});
