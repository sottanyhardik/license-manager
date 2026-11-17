import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import CustomsLedgerSection from "./CustomsLedgerSection";
import ledgerSrc from "./CustomsLedgerSection.tsx?raw";
import modalSrc from "@/components/LicenseBalanceModal.tsx?raw";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), patch: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() } }));

// Wire shapes from 11_QUANTITY_DISCREPANCY_REPORT.md §6 (L8, L9, L10).
const L8 = { id: 8, serial_number: 8, unit: "kg", quantity: 12335.89, boe_debited_quantity: 0, allotted_quantity: 0, billed_no_boe_qty: 0, available_quantity: 0, available_quantity_canonical: "12335.890", over_utilised_quantity: "0.000", is_quantity_over_utilised: false };
const L9 = { id: 9, serial_number: 9, unit: "kg", quantity: 321000, boe_debited_quantity: 434670, allotted_quantity: 0, billed_no_boe_qty: 0, available_quantity: 0, available_quantity_canonical: "0.000", over_utilised_quantity: "113670.000", is_quantity_over_utilised: true };
const L10 = { id: 10, serial_number: 10, unit: "mts", quantity: 163077.02, boe_debited_quantity: 0, allotted_quantity: 0, billed_no_boe_qty: 163077.02, available_quantity: 163077, available_quantity_canonical: "163077.020", over_utilised_quantity: "0.000", is_quantity_over_utilised: false };
const EXHAUSTED = { id: 11, serial_number: 11, unit: "kg", quantity: 50, available_quantity_canonical: "0.000", over_utilised_quantity: "0.000", is_quantity_over_utilised: false };
const OLD_API = { id: 12, serial_number: 12, unit: "kg", quantity: 100, boe_debited_quantity: 1, allotted_quantity: 1, billed_no_boe_qty: 1, available_quantity: 77 };

function renderLedger(items: unknown[]) {
    vi.mocked(api.get).mockResolvedValue({ data: { import_license: items } });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
        <QueryClientProvider client={qc}>
            <AuthContext.Provider value={{ hasRole: () => false } as never}><CustomsLedgerSection licenseId="1" /></AuthContext.Provider>
        </QueryClientProvider>,
    );
}
const row = async (sr: number) => (await screen.findAllByText(String(sr), { selector: "span" })).map((s) => s.closest("tr")!)[0];
const availableCell = (tr: HTMLElement) => within(tr).getAllByRole("cell")[4 + 5]; // 4 identity + Total..Planned, then Actual Available

beforeEach(() => vi.clearAllMocks());

describe("CustomsLedgerSection server-authoritative available quantity", () => {
    it("renders the canonical value as received at 3dp (L8 hidden BOE, L10 odd unit)", async () => {
        renderLedger([L8, L10]);
        expect(availableCell(await row(8))).toHaveTextContent("12,335.890");
        expect(availableCell(await row(10))).toHaveTextContent("1,63,077.020");
    });

    it("shows the over-use indicator only when flagged (L9) and derives status from server fields", async () => {
        renderLedger([L8, L9, EXHAUSTED]);
        const r9 = await row(9);
        expect(availableCell(r9)).toHaveTextContent("0.000");
        expect(within(r9).getAllByText("Over-used by 113670.000").length).toBeGreaterThan(0);
        expect(within(r9).getByText("Over-used")).toBeInTheDocument();
        expect(within(r9).queryByText("Exhausted")).toBeNull();
        expect(within(await row(8)).queryByText(/Over-used/)).toBeNull();
        expect(within(await row(11)).getByText("Exhausted")).toBeInTheDocument();
        expect(screen.getAllByText(/Over-used by/).every((el) => el.textContent === "Over-used by 113670.000")).toBe(true);
    });

    it("falls back to the existing server field (not computation) when the canonical field is absent", async () => {
        renderLedger([OLD_API]);
        // Old formula would give 100-1-1-1 = 97; the server value 77 must be shown.
        expect(availableCell(await row(12))).toHaveTextContent("77.000");
        expect(availableCell(await row(12))).not.toHaveTextContent("97");
    });

    it("output does not depend on the inputs that used to feed the removed formula", async () => {
        renderLedger([{ ...L8, quantity: 1, boe_debited_quantity: 999, allotted_quantity: 999, billed_no_boe_qty: 999 }]);
        expect(availableCell(await row(8))).toHaveTextContent("12,335.890");
    });

    it("source no longer contains the client subtraction", () => {
        for (const src of [ledgerSrc, modalSrc]) {
            expect(src).not.toMatch(/actualAvailableQuantity\s*=/);
            expect(src).not.toMatch(/quantity\s*(\|\||\?\?)\s*0\)\s*-\s*Number/);
            expect(src).not.toMatch(/Number\(item\.quantity[^)]*\)\s*-/);
        }
    });
});
