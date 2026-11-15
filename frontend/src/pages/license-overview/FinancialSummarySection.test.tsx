import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { FinancialLedgerSummary } from "@/pages/license-balance/types";
import { fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";
import FinancialSummarySection from "./FinancialSummarySection";

const base = {
    opening_balance: 50000,
    total_boe_debit: 10000,
    total_allotment_debit: 0,
    total_purchase_credit: 50000,
    total_trade_debit: 0,
    computed_balance: 40000,
    engine_balance: 40000,
    difference: 0,
    mismatched: false,
    tolerance: 0.01,
    has_trading_activity: true,
} as unknown as FinancialLedgerSummary;

const valueFor = (label: string) => screen.getByText(label).closest("tr")?.querySelectorAll("td")[1]?.textContent;

describe("FinancialSummarySection (OD-10)", () => {
    it("shows the engine-backed figure as Current Available Balance and the trade total under its own label", () => {
        render(<FinancialSummarySection summary={{ ...base, trade_running_balance: 50000 }} />);

        expect(valueFor("Current Available Balance")).toBe(fmtNum(40000));
        expect(valueFor("Trade Running Balance (purchases − sales)")).toBe(fmtNum(50000));
    });

    it("omits the trade total when absent or when the licence has no trading activity", () => {
        const { rerender } = render(<FinancialSummarySection summary={{ ...base, trade_running_balance: null }} />);
        expect(screen.queryByText(/Trade Running Balance/)).toBeNull();

        rerender(<FinancialSummarySection summary={{ ...base, has_trading_activity: false, trade_running_balance: 50000 }} />);
        expect(screen.queryByText(/Trade Running Balance/)).toBeNull();
    });
});
