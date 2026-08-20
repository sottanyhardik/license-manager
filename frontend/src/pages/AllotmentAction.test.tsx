import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import AllotmentAction from "./AllotmentAction";

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
            <button type="button" onClick={() => setFilters({ ...filters, item_id: "217" })}>Switch planning target</button>
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
});
