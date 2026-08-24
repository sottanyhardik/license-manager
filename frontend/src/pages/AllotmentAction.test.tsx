import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import AllotmentAction, { aggregateAllottedDetails } from "./AllotmentAction";

const navigate = vi.fn();

vi.mock("react-router-dom", () => ({
    useLocation: () => ({ state: null }),
    useNavigate: () => navigate,
    useParams: () => ({ id: "9722" }),
}));
vi.mock("../api/axios", () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn() } }));
vi.mock("../hooks/useBackButton", () => ({ useBackButton: vi.fn() }));
vi.mock("../hooks/useMasterOptions", () => ({ usePurchaseStatusOptions: () => ({ options: [] }) }));
vi.mock("../components/HybridSelect", () => ({ default: () => null }));
vi.mock("../components/ConditionBadge", () => ({ default: () => null }));
vi.mock("../components/TransferLetterForm", () => ({ default: () => null }));
vi.mock("../components/planning/LicensePlanningPanel", () => ({ default: () => null }));
vi.mock("../utils/pdfPreview", () => ({ openPdfPreview: vi.fn() }));

// This deliberately keeps the parent-owned filters real.  The production
// filter card is extensively tested separately; this small accessible test
// double lets these tests exercise target changes without coupling Max
// behavior to react-select's portal implementation.
vi.mock("./AllotmentFilters", () => ({
    default: ({ filters, setFilters }: { filters: Record<string, string>; setFilters: (next: Record<string, string>) => void }) => (
        <div>
            <output data-testid="planning-target">{filters.item_id}</output>
            <output data-testid="item-description">{filters.description}</output>
            <button type="button" onClick={() => setFilters({ ...filters, item_id: "217" })}>Switch planning target</button>
            <button type="button" onClick={() => setFilters({ ...filters, item_id: "" })}>Clear planning target</button>
            <button type="button" onClick={() => setFilters({ ...filters, description: "Independent description" })}>Set item description</button>
        </div>
    ),
}));

const mockedGet = vi.mocked(api.get);
const mockedPost = vi.mocked(api.post);

const allotment = {
    id: 9722,
    item_name: "BOPP",
    planning_target_item: 216,
    planning_target_item_name: "ALUMINIUM FOIL",
    unit_value_per_unit: "8.821",
    required_quantity: "500",
    required_value: "5000",
    required_value_with_buffer: "5020",
    alloted_quantity: "0",
    allotted_value: "0",
    balanced_quantity: "500",
    allotment_details: [],
};

const initialization = {
    default_search_mode: "PLAN",
    default_allocation_basis: "PLAN",
    default_item: { id: 216, name: "ALUMINIUM FOIL" },
    planning_target_item: { id: 216, name: "ALUMINIUM FOIL" },
    sion: "E1",
    has_active_plan: true,
    plan_status: "ACTIVE",
    plan_message: null,
};

function availableItem(id: number, description: string) {
    return {
        id,
        import_item_id: id,
        license_id: 11,
        license_number: "LIC-11",
        serial_number: "1",
        description,
        available_quantity: "1000.000",
        balance_cif_fc: "2066.75",
        has_plan: true,
        remaining_planned_quantity: "1000.000",
        remaining_planned_cif_fc: "2066.75",
        basis_options: {
            plan: {
                enabled: true,
                // These broad values intentionally disagree with the paired
                // ceiling.  The screen must submit the atomic server pair.
                max_qty: "999",
                max_cif: "2066.75",
                allocation_limit: {
                    paired_max_qty: "234",
                    paired_max_cif: "2064.12",
                    limiting_factor: "CIF",
                    can_allocate: true,
                },
            },
            actual: { enabled: false, max_qty: "0", max_cif: "0" },
        },
    };
}

function renderScreen() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    return render(<QueryClientProvider client={client}><AllotmentAction allotmentId={9722} onClose={vi.fn()} /></QueryClientProvider>);
}

describe("AllotmentAction canonical paired Max", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGet.mockImplementation((url: string, config?: { params?: Record<string, string> }) => {
            if (url === "masters/notification-numbers/") return Promise.resolve({ data: { results: [] } });
            if (url === "item-report/available-items/") return Promise.resolve({ data: [] });
            if (url === "item-report/planned-item-names/") return Promise.resolve({ data: [{ id: 216, name: "ALUMINIUM FOIL" }, { id: 217, name: "CHEESE" }] });
            if (url === "allotments/9722/") return Promise.resolve({ data: allotment });
            if (url === "allotment-actions/9722/allocation-initialization/") return Promise.resolve({ data: initialization });
            if (url === "allotment-actions/9722/available-licenses/") {
                return Promise.resolve({ data: { count: 1, available_items: [availableItem(config?.params?.planning_target_item_id === "217" ? 2 : 1, config?.params?.planning_target_item_id === "217" ? "CHEESE" : "ALUMINIUM FOIL")] } });
            }
            return Promise.reject(new Error(`Unexpected GET ${url}`));
        });
        mockedPost.mockResolvedValue({ data: { allotment } });
    });

    afterEach(() => vi.clearAllMocks());

    it("uses the API's atomic Qty/CIF pair on repeated Max clicks and persists that exact pair", async () => {
        renderScreen();

        const qtyInput = await screen.findByPlaceholderText("Qty");
        const valueInput = screen.getByPlaceholderText("Value");
        expect(screen.getByText("ALUMINIUM FOIL")).toBeInTheDocument();

        const maxButtons = screen.getAllByRole("button", { name: "Max" });
        fireEvent.click(maxButtons[0]);
        fireEvent.click(maxButtons[1]);
        fireEvent.click(maxButtons[0]);

        expect(qtyInput).toHaveValue(234);
        expect(valueInput).toHaveValue(2064.12);

        fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
        await waitFor(() => expect(mockedPost).toHaveBeenCalledTimes(1));
        expect(mockedPost).toHaveBeenCalledWith("allotment-actions/9722/allocate-items/", {
            allocations: [expect.objectContaining({
                item_id: 1,
                plan_line_id: 1,
                qty: "234",
                cif_fc: "2064.12",
                debit_based_on: "PLAN",
                allocation_basis: "PLAN",
                planning_target_item_id: "216",
            })],
        });
    });

    it("updates Value from Qty and clamps both fields to the server Max pair", async () => {
        renderScreen();
        const qtyInput = await screen.findByPlaceholderText("Qty");
        const valueInput = screen.getByPlaceholderText("Value");

        fireEvent.change(qtyInput, { target: { value: "100" } });
        expect(valueInput).toHaveValue(882.1);

        // The fixture's server pair is 234 / 2064.12.  Typing past it must
        // never leave a CIF-invalid pair in the row.
        fireEvent.change(qtyInput, { target: { value: "300" } });
        expect(qtyInput).toHaveValue(234);
        expect(valueInput).toHaveValue(2064.12);
    });

    it("clears a Max draft when the planning target changes, so it cannot be saved against the later target", async () => {
        renderScreen();
        await screen.findByPlaceholderText("Qty");

        fireEvent.click(screen.getAllByRole("button", { name: "Max" })[0]);
        expect(screen.getByPlaceholderText("Qty")).toHaveValue(234);

        fireEvent.click(screen.getByRole("button", { name: "Switch planning target" }));
        await waitFor(() => expect(screen.getByTestId("planning-target")).toHaveTextContent("217"));
        await waitFor(() => expect(screen.getByText("CHEESE")).toBeInTheDocument());

        expect(screen.getByPlaceholderText("Qty")).toHaveValue(null);
        expect(screen.getByPlaceholderText("Value")).toHaveValue(null);
        expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
        expect(mockedPost).not.toHaveBeenCalled();
    });

    it("keeps PLAN candidate retrieval active after clearing the optional planning target", async () => {
        renderScreen();
        await screen.findByPlaceholderText("Qty");

        fireEvent.click(screen.getByRole("button", { name: "Clear planning target" }));
        await waitFor(() => expect(screen.getByTestId("planning-target")).toHaveTextContent(""));
        await waitFor(() => expect(mockedGet).toHaveBeenCalledWith(
            "allotment-actions/9722/available-licenses/",
            expect.objectContaining({ params: expect.objectContaining({ page: 1, page_size: 10 }) }),
        ));
        const planCalls = mockedGet.mock.calls.filter(([url]) => url === "allotment-actions/9722/available-licenses/");
        const lastParams = planCalls[planCalls.length - 1]?.[1]?.params as Record<string, unknown>;
        expect(lastParams).not.toHaveProperty("planning_target_item_id");
    });

    it("sends an independently entered description after the normal debounce", async () => {
        renderScreen();
        await screen.findByPlaceholderText("Qty");
        fireEvent.click(screen.getByRole("button", { name: "Set item description" }));
        await waitFor(() => {
            const planCalls = mockedGet.mock.calls.filter(([url]) => url === "allotment-actions/9722/available-licenses/");
            const params = planCalls[planCalls.length - 1]?.[1]?.params as Record<string, unknown>;
            expect(params.description).toBe("Independent description");
        }, { timeout: 1000 });
    });

    it("initializes Item Description from the allotment header and sends it in PLAN mode", async () => {
        renderScreen();
        await screen.findByPlaceholderText("Qty");
        expect(screen.getByTestId("item-description")).toHaveTextContent("BOPP");
        await waitFor(() => {
            const calls = mockedGet.mock.calls.filter(([url]) => url === "allotment-actions/9722/available-licenses/");
            const params = calls[calls.length - 1]?.[1]?.params as Record<string, unknown>;
            expect(params.description).toBe("BOPP");
        }, { timeout: 1000 });
    });

    it("does not let planning-target changes overwrite the initialized description", async () => {
        renderScreen();
        await screen.findByPlaceholderText("Qty");
        expect(screen.getByTestId("item-description")).toHaveTextContent("BOPP");
        fireEvent.click(screen.getByRole("button", { name: "Switch planning target" }));
        await waitFor(() => expect(screen.getByTestId("planning-target")).toHaveTextContent("217"));
        expect(screen.getByTestId("item-description")).toHaveTextContent("BOPP");
        fireEvent.click(screen.getByRole("button", { name: "Clear planning target" }));
        expect(screen.getByTestId("item-description")).toHaveTextContent("BOPP");
    });

    it("keeps Actual mode on the canonical Actual path even when a row has plan metadata", async () => {
        const actualInitialization = {
            ...initialization,
            default_search_mode: "ACTUAL",
            default_allocation_basis: "ACTUAL",
            default_item: { id: 216, name: "ALUMINIUM FOIL" },
            has_active_plan: false,
            plan_status: "NO_ACTIVE_PLAN",
        };
        const actualItem = {
            ...availableItem(1, "ALUMINIUM FOIL"),
            basis_options: {
                actual: {
                    enabled: true,
                    allocation_limit: { paired_max_qty: "50", paired_max_cif: "441.05", can_allocate: true },
                },
                plan: { enabled: false, allocation_limit: { paired_max_qty: "0", paired_max_cif: "0", can_allocate: false } },
            },
            planning_options: [{ plan_line_id: 99, item_name: "UNRELATED PLAN", remaining_quantity: "1", remaining_cif_fc: "1" }],
        };
        mockedGet.mockImplementation((url: string) => {
            if (url === "masters/notification-numbers/") return Promise.resolve({ data: { results: [] } });
            if (url === "item-report/available-items/") return Promise.resolve({ data: [{ id: 216, name: "ALUMINIUM FOIL" }] });
            if (url === "item-report/planned-item-names/") return Promise.resolve({ data: [] });
            if (url === "allotments/9722/") return Promise.resolve({ data: allotment });
            if (url === "allotment-actions/9722/allocation-initialization/") return Promise.resolve({ data: actualInitialization });
            if (url === "allotment-actions/9722/available-licenses/") return Promise.resolve({ data: { count: 1, available_items: [actualItem] } });
            return Promise.reject(new Error(`Unexpected GET ${url}`));
        });

        renderScreen();
        await screen.findByPlaceholderText("Qty");
        expect(screen.queryByText("Follow Plan: UNRELATED PLAN")).not.toBeInTheDocument();
        fireEvent.click(screen.getAllByRole("button", { name: "Max" })[0]);
        fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
        await waitFor(() => expect(mockedPost).toHaveBeenCalledTimes(1));
        expect(mockedPost.mock.calls[0][1]).toEqual({
            allocations: [expect.objectContaining({
                item_id: 1,
                qty: "50",
                cif_fc: "441.05",
                debit_based_on: "ACTUAL",
                allocation_basis: "ACTUAL",
                actual_item_id: "216",
            })],
        });
        const submittedPayload = mockedPost.mock.calls[0][1] as { allocations: Record<string, unknown>[] };
        expect(submittedPayload.allocations[0]).not.toHaveProperty("plan_line_id");
    });
});

describe("Allotted Items display aggregation", () => {
    it("merges only matching licence and serial display rows with exact Qty and CIF totals", () => {
        const groups = aggregateAllottedDetails([
            { id: 41, license_number: "0311054264", serial_number: "3", qty: "13626.000", cif_fc: "9810.72" },
            { id: 42, license_number: "0311054264", serial_number: "3", qty: "0.125", cif_fc: "0.08" },
            { id: 43, license_number: "0311054264", serial_number: "4", qty: "1.000", cif_fc: "1.00" },
        ]);

        expect(groups).toHaveLength(2);
        expect(groups[0]).toMatchObject({
            license_number: "0311054264",
            serial_number: "3",
            qty: "13626.125",
            cif_fc: "9810.80",
            allocationIds: [41, 42],
            allocationCount: 2,
        });
        expect(groups[1].allocationIds).toEqual([43]);
    });

    it("does not merge ledger entries with incomplete source identifiers", () => {
        const groups = aggregateAllottedDetails([
            { id: 51, license_number: "", serial_number: "", qty: "1.000", cif_fc: "1.00" },
            { id: 52, license_number: "", serial_number: "", qty: "2.000", cif_fc: "2.00" },
        ]);

        expect(groups.map(group => group.allocationIds)).toEqual([[51], [52]]);
    });
});

describe("AllotmentAction live candidate queue", () => {
    function queueCandidate(sequence: number) {
        return {
            ...availableItem(sequence, `Candidate ${sequence}`),
            license_id: sequence,
            license_number: `LIC-${String(sequence).padStart(2, "0")}`,
            serial_number: String(sequence),
        };
    }

    it("keeps a unique ten-row server queue and promotes 11 then 12 after confirmed completions", async () => {
        let candidates = Array.from({ length: 12 }, (_, index) => queueCandidate(index + 1));
        mockedGet.mockImplementation((url: string) => {
            if (url === "masters/notification-numbers/") return Promise.resolve({ data: { results: [] } });
            if (url === "item-report/available-items/") return Promise.resolve({ data: [] });
            if (url === "item-report/planned-item-names/") return Promise.resolve({ data: [{ id: 216, name: "ALUMINIUM FOIL" }] });
            if (url === "allotments/9722/") return Promise.resolve({ data: allotment });
            if (url === "allotment-actions/9722/allocation-initialization/") return Promise.resolve({ data: initialization });
            if (url === "allotment-actions/9722/available-licenses/") return Promise.resolve({ data: { count: candidates.length, available_items: candidates.slice(0, 10) } });
            return Promise.reject(new Error(`Unexpected GET ${url}`));
        });
        mockedPost.mockImplementation(() => {
            candidates = candidates.slice(1);
            return Promise.resolve({ data: { allotment } });
        });

        renderScreen();
        await screen.findByText("LIC-01");
        expect(screen.getByText("LIC-10")).toBeInTheDocument();
        expect(screen.queryByText("LIC-11")).not.toBeInTheDocument();

        fireEvent.click(screen.getAllByRole("button", { name: "Max" })[0]);
        fireEvent.click(screen.getAllByRole("button", { name: "Confirm" })[0]);
        await waitFor(() => expect(screen.queryByText("LIC-01")).not.toBeInTheDocument());
        expect(screen.getAllByTitle("View license document")).toHaveLength(10);

        fireEvent.click(screen.getAllByRole("button", { name: "Max" })[0]);
        fireEvent.click(screen.getAllByRole("button", { name: "Confirm" })[0]);
        await waitFor(() => expect(screen.queryByText("LIC-02")).not.toBeInTheDocument());
        expect(screen.getByText("LIC-12")).toBeInTheDocument();
        expect(screen.getAllByTitle("View license document")).toHaveLength(10);
    });

    it("keeps a partially allocated candidate in the queue after the authoritative refresh", async () => {
        const candidate = queueCandidate(1);
        mockedGet.mockImplementation((url: string) => {
            if (url === "masters/notification-numbers/") return Promise.resolve({ data: { results: [] } });
            if (url === "item-report/available-items/") return Promise.resolve({ data: [] });
            if (url === "item-report/planned-item-names/") return Promise.resolve({ data: [{ id: 216, name: "ALUMINIUM FOIL" }] });
            if (url === "allotments/9722/") return Promise.resolve({ data: allotment });
            if (url === "allotment-actions/9722/allocation-initialization/") return Promise.resolve({ data: initialization });
            if (url === "allotment-actions/9722/available-licenses/") return Promise.resolve({ data: { count: 1, available_items: [{ ...candidate, basis_options: { ...candidate.basis_options, plan: { ...candidate.basis_options.plan, allocation_limit: { paired_max_qty: "100", paired_max_cif: "882.10", can_allocate: true } } } }] } });
            return Promise.reject(new Error(`Unexpected GET ${url}`));
        });
        mockedPost.mockResolvedValue({ data: { allotment } });

        renderScreen();
        await screen.findByText("LIC-01");
        mockedPost.mockClear();
        fireEvent.click(screen.getAllByRole("button", { name: "Max" })[0]);
        fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
        await waitFor(() => expect(mockedPost.mock.calls.filter(([url]) => url === "allotment-actions/9722/allocate-items/")).toHaveLength(1));
        expect(await screen.findByText("LIC-01")).toBeInTheDocument();
        expect(screen.getByPlaceholderText("Qty")).toHaveValue(null);
    });

    it("does not remove a candidate after a failed allocation and prevents a rapid double submit", async () => {
        let rejectPost: (reason?: unknown) => void = () => undefined;
        const pendingPost = new Promise<{ data: unknown }>((_resolve, reject) => {
            rejectPost = reject;
        });
        mockedPost.mockReturnValue(pendingPost as never);
        renderScreen();
        await screen.findByPlaceholderText("Qty");
        mockedPost.mockClear();
        fireEvent.click(screen.getAllByRole("button", { name: "Max" })[0]);
        const confirm = screen.getByRole("button", { name: "Confirm" });
        fireEvent.click(confirm);
        fireEvent.click(confirm);
        await waitFor(() => expect(mockedPost.mock.calls.filter(([url]) => url === "allotment-actions/9722/allocate-items/")).toHaveLength(1));
        expect(screen.getAllByTitle("View license document")).toHaveLength(1);
        rejectPost({ response: { data: { message: "Server cap changed" } } });
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Server cap changed"));
        expect(screen.getAllByTitle("View license document")).toHaveLength(1);
    });

    it("refreshes the authoritative queue after an exhausted-plan rejection so a stale candidate is not left actionable", async () => {
        let candidateRequests = 0;
        mockedGet.mockImplementation((url: string) => {
            if (url === "masters/notification-numbers/") return Promise.resolve({ data: { results: [] } });
            if (url === "item-report/available-items/") return Promise.resolve({ data: [] });
            if (url === "item-report/planned-item-names/") return Promise.resolve({ data: [{ id: 216, name: "ALUMINIUM FOIL" }] });
            if (url === "allotments/9722/") return Promise.resolve({ data: allotment });
            if (url === "allotment-actions/9722/allocation-initialization/") return Promise.resolve({ data: initialization });
            if (url === "allotment-actions/9722/available-licenses/") {
                candidateRequests += 1;
                return Promise.resolve({ data: candidateRequests === 1 ? { count: 1, available_items: [availableItem(1, "ALUMINIUM FOIL")] } : { count: 0, available_items: [] } });
            }
            return Promise.reject(new Error(`Unexpected GET ${url}`));
        });
        mockedPost.mockRejectedValue({ response: { data: { errors: [{ code: "NO_PLANNED_BALANCE", error: "No planned balance" }] } } });

        renderScreen();
        await screen.findByPlaceholderText("Qty");
        fireEvent.click(screen.getAllByRole("button", { name: "Max" })[0]);
        fireEvent.click(screen.getByRole("button", { name: "Confirm" }));

        await waitFor(() => expect(candidateRequests).toBeGreaterThanOrEqual(2));
        expect(await screen.findByText("No applicable active plan")).toBeInTheDocument();
    });
});
