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
