import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import QuantityUtilization from "./QuantityUtilization";

describe("QuantityUtilization", () => {
    it("renders canonical values without deriving a combined utilization total", () => {
        render(
            <QuantityUtilization
                unit="KG"
                values={{
                    totalQuantity: 1000,
                    boeDebitedQuantity: 125,
                    allottedQuantity: 75,
                    plannedQuantity: 300,
                    actualAvailableQuantity: 800,
                    planRemainingQuantity: 225,
                }}
            />,
        );

        expect(screen.getByText("Total Qty")).toBeInTheDocument();
        expect(screen.getByText("BOE Debited")).toBeInTheDocument();
        expect(screen.getByText("Allotted")).toBeInTheDocument();
        expect(screen.getByText("Planned")).toBeInTheDocument();
        expect(screen.getByText("Actual Available")).toBeInTheDocument();
        expect(screen.getByText("Plan Remaining")).toBeInTheDocument();
        expect(screen.getByText("1,000.000")).toBeInTheDocument();
        expect(screen.getByText("125.000")).toBeInTheDocument();
        expect(screen.getByText("75.000")).toBeInTheDocument();
        expect(screen.getByText("300.000")).toBeInTheDocument();
        expect(screen.getByText("800.000")).toBeInTheDocument();
        expect(screen.getByText("225.000")).toBeInTheDocument();
        expect(screen.queryByText(/utilized total/i)).not.toBeInTheDocument();
    });

    it("keeps missing values distinct from explicit zero and labels exhausted availability", () => {
        render(
            <QuantityUtilization
                values={{
                    totalQuantity: 0,
                    actualAvailableQuantity: 0,
                    planRemainingQuantity: null,
                }}
            />,
        );

        expect(screen.getAllByText("0.000")).toHaveLength(2);
        expect(screen.getAllByText("—")).toHaveLength(4);
        expect(screen.getByText("Exhausted")).toBeInTheDocument();
    });
});
