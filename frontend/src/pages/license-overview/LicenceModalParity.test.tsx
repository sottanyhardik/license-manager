import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { qk } from "@/lib/queryKeys";
import CustomsLedgerSection from "./CustomsLedgerSection";
import LicenceModalSections from "./LicenceModalSections";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), patch: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() } }));
// The modal's react-select search is replaced by the shared AsyncSelectField; stub it to "pick" id 42.
vi.mock("@/components/AsyncSelectField", () => ({
    default: ({ onChange, ariaLabel }: { onChange: (v: unknown) => void; ariaLabel: string }) => (
        <button type="button" onClick={() => onChange(42)}>{ariaLabel}</button>
    ),
}));
// Radix Select needs pointer APIs jsdom lacks; a native select keeps the value/onValueChange contract.
vi.mock("@/components/ui/select", () => ({
    Select: ({ value, onValueChange, children }: { value: string; onValueChange: (v: string) => void; children: ReactNode }) => (
        <select aria-label="License marking" value={value} onChange={(e) => onValueChange(e.target.value)}>{children}</select>
    ),
    SelectTrigger: () => null,
    SelectValue: () => null,
    SelectContent: ({ children }: { children: ReactNode }) => <>{children}</>,
    SelectItem: ({ value, children }: { value: string; children: ReactNode }) => <option value={value}>{children}</option>,
}));

const mockedGet = vi.mocked(api.get);
const mockedPatch = vi.mocked(api.patch);

const detail = {
    condition_sheet: "Existing sheet",
    balance_report_notes: "",
    balance_cif: 1250.5,
    is_over_utilised: false,
    get_norm_class: "E5",
    export_license: [{ id: 1, description: "Biscuits", cif_fc: 5000 }],
    import_license: [{
        id: 5, serial_number: 1, description: "Wheat flour", hs_code_label: "1101", unit: "kg",
        quantity: 100, condition_type: "AU",
        items_detail: [{ id: 1, name: "Flour", sion_norm_class: null }, { id: 2, name: "Maida", sion_norm_class: null }],
    }],
};
const usage = {
    boes: [{ id: 11, bill_of_entry_number: "BOE-77", date: "2026-01-02", port: "INNSA1", company: "Acme", quantity: 10, cif_fc: 100, cif_inr: 8300 }],
    allotments: [{ id: 21, company: "Beta", quantity: 5, cif_fc: 50, cif_inr: 4150 }],
};

function installApi() {
    mockedGet.mockImplementation((url: string) => {
        if (url === "licenses/9/") return Promise.resolve({ data: detail });
        if (url === "licenses/9/item-usage/") return Promise.resolve({ data: usage });
        return Promise.resolve({ data: {} });
    });
    mockedPatch.mockResolvedValue({ data: {} });
}

function renderWith(ui: ReactNode, writer: boolean) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(qc, "invalidateQueries");
    render(
        <QueryClientProvider client={qc}>
            <AuthContext.Provider value={{ hasRole: (r: string) => writer && r === "LICENSE_MANAGER" } as never}>{ui}</AuthContext.Provider>
        </QueryClientProvider>,
    );
    return { invalidate };
}
const invalidatedLicence = (spy: ReturnType<typeof vi.fn>) =>
    spy.mock.calls.some(([arg]) => JSON.stringify((arg as { queryKey: unknown }).queryKey) === JSON.stringify(qk.licenses.detail("9")));

beforeEach(() => { vi.clearAllMocks(); installApi(); });

describe("licence-level sections (ported from LicenseBalanceModal)", () => {
    it("condition sheet edit sends the modal's PATCH licenses/:id/ payload and invalidates the licence", async () => {
        const { invalidate } = renderWith(<LicenceModalSections licenseId="9" />, true);
        await userEvent.click(await screen.findByRole("button", { name: "Edit condition sheet" }));
        const box = screen.getByRole("textbox", { name: "Condition Sheet" });
        await userEvent.clear(box);
        await userEvent.type(box, "New sheet");
        await userEvent.click(screen.getByRole("button", { name: /save/i }));
        await waitFor(() => expect(mockedPatch).toHaveBeenCalledWith("licenses/9/", { condition_sheet: "New sheet" }));
        await waitFor(() => expect(invalidatedLicence(invalidate as never)).toBe(true));
    });

    it("notes edit sends { balance_report_notes }", async () => {
        renderWith(<LicenceModalSections licenseId="9" />, true);
        await userEvent.click(await screen.findByRole("button", { name: "Edit notes" }));
        await userEvent.type(screen.getByRole("textbox", { name: "Notes" }), "Hello");
        await userEvent.click(screen.getByRole("button", { name: /save/i }));
        await waitFor(() => expect(mockedPatch).toHaveBeenCalledWith("licenses/9/", { balance_report_notes: "Hello" }));
    });

    it("viewers see condition sheet text but no edit controls", async () => {
        renderWith(<LicenceModalSections licenseId="9" />, false);
        expect(await screen.findByText("Existing sheet")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /^edit/i })).not.toBeInTheDocument();
    });

    it("export items table shows the modal's columns and drills usage with type=export", async () => {
        renderWith(<LicenceModalSections licenseId="9" />, false);
        const table = (await screen.findByText("Biscuits")).closest("table")!;
        expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Usage", "Item", "Total CIF", "Balance CIF"]);
        await userEvent.click(screen.getByRole("button", { name: "Show usage for Biscuits" }));
        await waitFor(() => expect(mockedGet).toHaveBeenCalledWith("licenses/9/item-usage/", { params: { item_id: 1, type: "export" } }));
        expect(await screen.findByText("BOE-77")).toBeInTheDocument();
    });
});

describe("import-item controls (ported from LicenseBalanceModal)", () => {
    it("removing a tag sends PATCH license-items/:id/ { items } with the remaining ids", async () => {
        const { invalidate } = renderWith(<CustomsLedgerSection licenseId="9" />, true);
        const [desktopRemove] = await screen.findAllByRole("button", { name: "Remove Flour" });
        await userEvent.click(desktopRemove);
        await waitFor(() => expect(mockedPatch).toHaveBeenCalledWith("license-items/5/", { items: [2] }));
        await waitFor(() => expect(invalidatedLicence(invalidate as never)).toBe(true));
    });

    it("adding a tag appends the picked id to { items }", async () => {
        renderWith(<CustomsLedgerSection licenseId="9" />, true);
        const [addButton] = await screen.findAllByRole("button", { name: "Add" });
        await userEvent.click(addButton);
        await userEvent.click(screen.getByRole("button", { name: "Add item tag" }));
        await waitFor(() => expect(mockedPatch).toHaveBeenCalledWith("license-items/5/", { items: [1, 2, 42] }));
    });

    it("licence marking sends { condition_type }, and None clears it with an empty string", async () => {
        renderWith(<CustomsLedgerSection licenseId="9" />, true);
        const [select] = await screen.findAllByRole("combobox", { name: "License marking" });
        await userEvent.selectOptions(select, "10%");
        await waitFor(() => expect(mockedPatch).toHaveBeenCalledWith("license-items/5/", { condition_type: "10%" }));
        await userEvent.selectOptions(select, "__none__");
        await waitFor(() => expect(mockedPatch).toHaveBeenCalledWith("license-items/5/", { condition_type: "" }));
    });

    it("viewers get no tag or marking edit controls", async () => {
        renderWith(<CustomsLedgerSection licenseId="9" />, false);
        await screen.findAllByText("Wheat flour");
        expect(screen.queryByRole("button", { name: /^remove/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument();
        expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
        expect(screen.getAllByText("AU").length).toBeGreaterThan(0);
    });

    it("usage drill requests item-usage/ with type=import and shows the modal's columns, no balance line", async () => {
        renderWith(<CustomsLedgerSection licenseId="9" />, false);
        const [toggle] = await screen.findAllByRole("button", { name: "Show usage for SR 1" });
        await userEvent.click(toggle);
        await waitFor(() => expect(mockedGet).toHaveBeenCalledWith("licenses/9/item-usage/", { params: { item_id: 5, type: "import" } }));
        const boeTable = within(screen.getAllByRole("region", { name: "BOE usage" })[0]).getByRole("table");
        expect(within(boeTable).getAllByRole("columnheader").map((h) => h.textContent))
            .toEqual(["BOE Number", "Date", "Port", "Company", "Qty", "CIF $", "CIF INR"]);
        const allotTable = within(screen.getAllByRole("region", { name: "Allotment usage" })[0]).getByRole("table");
        expect(within(allotTable).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Company", "Qty", "CIF $", "CIF INR"]);
        expect(screen.queryByText(/balance calculation/i)).not.toBeInTheDocument();
    });

    it("D7: Quantity and CIF (FC) group headers span their 7 columns", async () => {
        renderWith(<CustomsLedgerSection licenseId="9" />, false);
        const quantity = await screen.findByRole("columnheader", { name: "Quantity" });
        expect(quantity).toHaveAttribute("colspan", "7");
        expect(screen.getByRole("columnheader", { name: "CIF (FC)" })).toHaveAttribute("colspan", "7");
    });
});
