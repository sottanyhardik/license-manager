import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AllocationStrategyEditor } from "./AllocationStrategyEditor";
import { SplitAllocationPreview } from "./SplitAllocationPreview";

describe("AllocationStrategyEditor", () => {
    it("offers standard and generic split strategies", async () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor value={{ strategy: "STANDARD" }} onChange={onChange} />);
        await userEvent.selectOptions(screen.getByLabelText("Allocation strategy"), "SPLIT_BY_UNIT_VALUE");
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
            strategy: "SPLIT_BY_UNIT_VALUE",
            config: expect.objectContaining({
                algorithm: "SPLIT_BY_UNIT_VALUE",
                basis: "BALANCE_CIF_PER_QUANTITY",
                buckets: [
                    { code: "SWP", min_price: "0.00", max_price: "1.50", reference_price: "1.50" },
                    { code: "DWP", min_price: "1.50", max_price: "6.50", reference_price: "6.50" },
                ],
            }),
        }));
    });

    it("passes decimal boundary text through without calculating in React", async () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor value={{ strategy: "SPLIT_BY_UNIT_VALUE", config: {
            algorithm: "SPLIT_BY_UNIT_VALUE", basis: "BALANCE_CIF_PER_QUANTITY",
            buckets: [{ code: "SWP", min_price: "0.00", max_price: "1.50", reference_price: "1.50" }],
        } }} onChange={onChange} />);
        const input = screen.getByLabelText("SWP max price");
        fireEvent.change(input, { target: { value: "1.75" } });
        expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ config: expect.objectContaining({ buckets: [expect.objectContaining({ max_price: "1.75" })] }) }));
    });

    it("handles percentage allocation with empty rows without crashing", () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor value={{
            strategy: "SPLIT_BY_PERCENTAGE",
            config: { algorithm: "SPLIT_BY_PERCENTAGE", rows: [] },
        }} onChange={onChange} />);
        expect(screen.getByText(/No percentage configuration has been created yet/)).toBeInTheDocument();
        expect(screen.getByText("0.00%")).toBeInTheDocument();
    });

    it("handles percentage allocation with legacy API payload (percentage_rules)", () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor value={{
            strategy: "SPLIT_BY_PERCENTAGE",
            config: {
                sion_id: 123,
                percentage_rules: [
                    { rule_id: 1, output_code: "OUTPUT1", percentage: "50.00" },
                    { rule_id: 2, output_code: "OUTPUT2", percentage: "50.00" },
                ],
            } as any,
        }} onChange={onChange} />);
        expect(screen.getByDisplayValue("OUTPUT1")).toBeInTheDocument();
        expect(screen.getByDisplayValue("OUTPUT2")).toBeInTheDocument();
        expect(screen.getByText("100.00%")).toBeInTheDocument();
    });

    it("calculates percentage total correctly", () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor value={{
            strategy: "SPLIT_BY_PERCENTAGE",
            config: {
                algorithm: "SPLIT_BY_PERCENTAGE",
                rows: [
                    { id: "1", input_item_id: 1, output_code: "OUT1", percentage: "33.33", unit_price: "2.00" },
                    { id: "2", input_item_id: 2, output_code: "OUT2", percentage: "33.33", unit_price: "3.00" },
                    { id: "3", input_item_id: 3, output_code: "OUT3", percentage: "33.34", unit_price: "4.00" },
                ],
            },
        }} onChange={onChange} />);
        expect(screen.getByText("100.00%")).toBeInTheDocument();
    });

    it("adds percentage row with correct initial values", async () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor value={{
            strategy: "SPLIT_BY_PERCENTAGE",
            config: { algorithm: "SPLIT_BY_PERCENTAGE", rows: [] },
        }} onChange={onChange} />);
        const addButtons = screen.getAllByText(/\+ Add Percentage Row/);
        await userEvent.click(addButtons[1]);
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
            strategy: "SPLIT_BY_PERCENTAGE",
            config: expect.objectContaining({
                rows: expect.arrayContaining([
                    expect.objectContaining({
                        input_item_id: null,
                        percentage: "0.00",
                        unit_price: "0.00",
                    }),
                ]),
            }),
        }));
    });

    it("removes percentage row", async () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor value={{
            strategy: "SPLIT_BY_PERCENTAGE",
            config: {
                algorithm: "SPLIT_BY_PERCENTAGE",
                rows: [
                    { id: "1", input_item_id: 1, output_code: "OUT1", percentage: "50.00", unit_price: "2.00" },
                    { id: "2", input_item_id: 2, output_code: "OUT2", percentage: "50.00", unit_price: "3.00" },
                ],
            },
        }} onChange={onChange} />);
        const removeButtons = screen.getAllByLabelText(/Remove row/);
        await userEvent.click(removeButtons[0]);
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
            config: expect.objectContaining({
                rows: expect.arrayContaining([
                    expect.objectContaining({ output_code: "OUT2" }),
                ]),
            }),
        }));
    });

    it("updates percentage value", async () => {
        const onChange = vi.fn();
        render(<AllocationStrategyEditor value={{
            strategy: "SPLIT_BY_PERCENTAGE",
            config: {
                algorithm: "SPLIT_BY_PERCENTAGE",
                rows: [
                    { id: "1", input_item_id: 1, output_code: "OUT1", percentage: "50.00", unit_price: "2.00" },
                ],
            },
        }} onChange={onChange} />);
        const percentageInputs = screen.getAllByDisplayValue("50.00");
        fireEvent.change(percentageInputs[0], { target: { value: "75.50" } });
        expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
            config: expect.objectContaining({
                rows: expect.arrayContaining([
                    expect.objectContaining({
                        output_code: "OUT1",
                        percentage: "75.50",
                    }),
                ]),
            }),
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
