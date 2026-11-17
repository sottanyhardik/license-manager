import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/api/axios";
import LicenseBalanceModal from "./LicenseBalanceModal";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), patch: vi.fn(), post: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/AsyncSelectField", () => ({ default: () => null }));

// Wire shapes from 11_QUANTITY_DISCREPANCY_REPORT.md §6 (L8 hidden BOE, L9 over-utilised).
const L8 = { id: 8, serial_number: 8, quantity: 12335.89, debited_quantity: 12335, allotted_quantity: 0, available_quantity: 0, available_quantity_canonical: "12335.890", over_utilised_quantity: "0.000", is_quantity_over_utilised: false, items_detail: [] };
const L9 = { id: 9, serial_number: 9, quantity: 321000, debited_quantity: 434670, allotted_quantity: 0, available_quantity: 0, available_quantity_canonical: "0.000", over_utilised_quantity: "113670.000", is_quantity_over_utilised: true, items_detail: [] };
const OLD = { id: 12, serial_number: 12, quantity: 100, debited_quantity: 1, allotted_quantity: 1, available_quantity: 77, items_detail: [] };

async function openBalance(item: Record<string, unknown>) {
    vi.mocked(api.get).mockImplementation((url: string) => Promise.resolve({
        data: url.includes("item-usage") ? { boes: [], allotments: [] } : { id: 1, balance_cif: 10, export_license: [], import_license: [item] },
    }));
    render(<LicenseBalanceModal show onHide={() => undefined} licenseId={1} />);
    await userEvent.click(await screen.findByText(String(item.serial_number), { selector: "td" }));
    return screen.findByText(/^Balance:/);
}

beforeEach(() => vi.clearAllMocks());

describe("LicenseBalanceModal server-authoritative balance quantity", () => {
    it("renders available_quantity_canonical as received, without an over-use badge (L8)", async () => {
        const el = await openBalance(L8);
        expect(el).toHaveTextContent("Balance: 12335.89");
        expect(screen.queryByText(/Over-used by/)).toBeNull();
    });

    it("shows the over-use indicator when flagged (L9) instead of a negative client balance", async () => {
        const el = await openBalance(L9);
        expect(el).toHaveTextContent("Balance: 0.00");
        expect(await screen.findByText("Over-used by 113670.000")).toBeInTheDocument();
    });

    it("falls back to the existing server field when canonical is absent (never computes)", async () => {
        const el = await openBalance(OLD);
        await waitFor(() => expect(el).toHaveTextContent("Balance: 77.00"));
    });
});
