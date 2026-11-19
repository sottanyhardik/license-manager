import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../../api/axios", () => ({ default: { get: vi.fn(() => Promise.resolve({ data: {} })), post: vi.fn() } }));
import LicensesTable, { type LicenseListItem } from "./LicensesTable";

const item = (id: number, n: string) => ({ id, license_number: n, exporter: { id: 1, name: "ACME" }, license_date: "2024-01-01", license_expiry_date: "2027-01-01", balance_cif: "1", is_active: true }) as unknown as LicenseListItem;
const props = { loading: false, data: [item(1, "0310000001"), item(2, "0310000002")], canWrite: false, entityName: "licenses", filterParams: {}, currentPage: 1, pageSize: 25,
    navigate: vi.fn(), onDelete: vi.fn(), fetchingOwnershipIds: new Set<number>(), onFetchOwnership: vi.fn(), invalidateList: vi.fn() };
const wrap = (ui: React.ReactNode) => <QueryClientProvider client={new QueryClient()}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>;

describe("LicensesTable open requests", () => {
    it("opens the requested licence; requesting an already-open licence keeps exactly one workspace", () => {
        const { rerender } = render(wrap(<LicensesTable {...props} openRequest={{ id: 2, n: 1 }} />));
        expect(screen.getByRole("button", { name: "Collapse license 0310000002" })).toBeInTheDocument();
        rerender(wrap(<LicensesTable {...props} openRequest={{ id: 2, n: 2 }} />));
        expect(screen.getByRole("button", { name: "Collapse license 0310000002" })).toBeInTheDocument(); // not toggled closed
        expect(screen.getAllByRole("region", { name: /details$/ })).toHaveLength(1);
        rerender(wrap(<LicensesTable {...props} openRequest={{ id: 1, n: 3 }} />));
        expect(screen.getByRole("button", { name: "Collapse license 0310000001" })).toBeInTheDocument(); // second licence opens …
        expect(screen.getByRole("button", { name: "Expand license 0310000002" })).toBeInTheDocument(); // … in place of the first
    });
});
