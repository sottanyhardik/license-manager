import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render as testingLibraryRender, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AllocationStrategyEditor } from "./AllocationStrategyEditor";
import { SplitAllocationPreview } from "./SplitAllocationPreview";

vi.mock("@/services/api/planningRuleApi", () => ({
    searchSionImportItems: vi.fn().mockResolvedValue({ items: [], nextPage: null }),
    fetchSionImportItem: vi.fn().mockResolvedValue(null),
}));

const render = (ui: React.ReactElement) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
    return testingLibraryRender(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
};

describe("AllocationStrategyEditor", () => {
    it("offers all Level 1 strategies and clears strategy-specific rows on change", async () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor sionId={7} value={{ strategy: "STANDARD" }} onChange={onChange} />);

        expect(screen.getByRole("option", { name: "Standard (single item)" })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: "Split by Unit Value" })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: "Split by %" })).toBeInTheDocument();
        await userEvent.selectOptions(screen.getByLabelText("Allocation strategy"), "SPLIT_BY_UNIT_VALUE");
        expect(onChange).toHaveBeenCalledWith({
            strategy: "SPLIT_BY_UNIT_VALUE",
            import_item: null,
            unit_value_rows: [],
            percentage_rows: [],
        });
    });

    it("passes decimal unit-value row text through without calculating in React", () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor sionId={7} value={{
            strategy: "SPLIT_BY_UNIT_VALUE",
            unit_value_rows: [{ import_item: 0, min_unit_price: "0.00", max_unit_price: "1.50", preferred_unit_price: "1.25" }],
        }} onChange={onChange} />);

        fireEvent.change(screen.getByDisplayValue("1.50"), { target: { value: "1.75" } });
        expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
            unit_value_rows: [expect.objectContaining({ max_unit_price: "1.75" })],
        }));
    });

    it("renders an empty percentage strategy and its zero total", () => {
        render(<AllocationStrategyEditor sionId={7} value={{ strategy: "SPLIT_BY_PERCENT", percentage_rows: [] }} onChange={vi.fn()} />);
        expect(screen.getByText("Total: 0.00%")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "+ Add Item" })).toBeInTheDocument();
    });

    it("calculates the configured percentage-row total", () => {
        render(<AllocationStrategyEditor sionId={7} value={{
            strategy: "SPLIT_BY_PERCENT",
            percentage_rows: [
                { import_item: 0, percentage: "33.33", unit_price: "2.00" },
                { import_item: 0, percentage: "33.33", unit_price: "3.00" },
                { import_item: 0, percentage: "33.34", unit_price: "4.00" },
            ],
        }} onChange={vi.fn()} />);
        expect(screen.getByText("Total: 100.00%")).toBeInTheDocument();
    });

    it("adds a percentage row using the current API row shape", async () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor sionId={7} value={{ strategy: "SPLIT_BY_PERCENT", percentage_rows: [] }} onChange={onChange} />);
        await userEvent.click(screen.getByRole("button", { name: "+ Add Item" }));
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
            percentage_rows: [{ import_item: 0, percentage: "0", unit_price: "0" }],
        }));
    });

    it("removes only the selected percentage row", async () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor sionId={7} value={{
            strategy: "SPLIT_BY_PERCENT",
            percentage_rows: [
                { import_item: 0, percentage: "40.00", unit_price: "2.00" },
                { import_item: 0, percentage: "60.00", unit_price: "3.00" },
            ],
        }} onChange={onChange} />);
        await userEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]);
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
            percentage_rows: [{ import_item: 0, percentage: "60.00", unit_price: "3.00" }],
        }));
    });

    it("updates percentage decimal text in the configured row", () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor sionId={7} value={{
            strategy: "SPLIT_BY_PERCENT",
            percentage_rows: [{ import_item: 0, percentage: "50.00", unit_price: "2.00" }],
        }} onChange={onChange} />);
        fireEvent.change(screen.getByDisplayValue("50.00"), { target: { value: "75.50" } });
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
            percentage_rows: [expect.objectContaining({ percentage: "75.50" })],
        }));
    });
});

describe("SplitAllocationPreview", () => {
    it("renders exact backend allocation and residual strings", () => {
        render(<SplitAllocationPreview allocation={{
            strategy: "SPLIT_BY_UNIT_VALUE", status: "ALLOCATED", total_quantity: "1000.000",
            balance_cif: "3500.00", effective_unit_price: "3.5000", quantity_remaining: "0.000",
            cif_remaining: "0.00", lines: [
                { bucket: "SWP", quantity: "600.000", unit_price: "1.50", cif: "900.00" },
                { bucket: "DWP", quantity: "400.000", unit_price: "6.50", cif: "2600.00" },
            ],
        }} />);
        expect(screen.getByText("600.000")).toBeInTheDocument();
        expect(screen.getByText("2600.00")).toBeInTheDocument();
        expect(screen.getByText("0.000")).toBeInTheDocument();
        expect(screen.getByText("0.00")).toBeInTheDocument();
    });
});
