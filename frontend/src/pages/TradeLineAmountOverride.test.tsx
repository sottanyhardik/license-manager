import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import TradeLineAmountOverride from "./TradeLineAmountOverride";

describe("TradeLineAmountOverride (T1 toggle, T4 warnings)", () => {
    it("toggles manual amount and asks for a reason only when on", () => {
        const onOverrideChange = vi.fn();
        const { rerender } = render(
            <TradeLineAmountOverride index={0} override={false} reason="" onOverrideChange={onOverrideChange} onReasonChange={vi.fn()} />,
        );
        expect(screen.queryByLabelText(/Reason for manual amount/)).not.toBeInTheDocument();
        fireEvent.click(screen.getByLabelText("Manual amount"));
        expect(onOverrideChange).toHaveBeenCalledWith(true);

        const onReasonChange = vi.fn();
        rerender(
            <TradeLineAmountOverride index={0} override reason="" onOverrideChange={onOverrideChange} onReasonChange={onReasonChange} />,
        );
        const reason = screen.getByLabelText("Reason for manual amount, line 1");
        expect(reason).toBeRequired();
        fireEvent.change(reason, { target: { value: "Lump sum" } });
        expect(onReasonChange).toHaveBeenCalledWith("Lump sum");
    });

    it("lists server CIF INR warnings without blocking", () => {
        render(
            <TradeLineAmountOverride index={2} override={false} reason="" warnings={["cif_inr 4536070.00 differs"]}
                onOverrideChange={vi.fn()} onReasonChange={vi.fn()} />,
        );
        expect(screen.getByRole("list", { name: "Warnings, line 3" })).toHaveTextContent("cif_inr 4536070.00 differs");
    });
});
