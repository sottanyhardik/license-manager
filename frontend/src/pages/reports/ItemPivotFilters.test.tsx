import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ItemPivotFilters, { normalizeMinBalance } from "./ItemPivotFilters";

vi.mock("react-select", () => ({
    default: ({ inputId, options, value, onChange, placeholder }) => (
        <select
            id={inputId}
            aria-label={placeholder}
            multiple
            value={(value || []).map((option) => option.value)}
            onChange={(event) => {
                const selectedValues = Array.from(event.currentTarget.selectedOptions).map((option) => option.value);
                onChange(options.filter((option) => selectedValues.includes(option.value)));
            }}
        >
            {options.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
            ))}
        </select>
    ),
}));

vi.mock("../../components/AsyncSelectField", () => ({
    default: ({ placeholder }) => <input aria-label={placeholder} readOnly />,
}));

const purchaseStatusOptions = [
    { value: "GE", label: "GE Purchase" },
    { value: "MI", label: "MI Purchase" },
    { value: "IP", label: "IP Purchase" },
];

function renderFilters(overrides = {}) {
    const props = {
        minBalance: 200,
        setMinBalance: vi.fn(),
        licenseStatus: "active",
        setLicenseStatus: vi.fn(),
        purchaseStatus: ["GE", "MI"],
        setPurchaseStatus: vi.fn(),
        purchaseStatusOptions,
        expiryDateFrom: "",
        setExpiryDateFrom: vi.fn(),
        expiryDateTo: "",
        setExpiryDateTo: vi.fn(),
        selectedCompanies: [],
        handleCompanyChange: vi.fn(),
        excludeCompanies: [],
        handleExcludeCompanyChange: vi.fn(),
        hasActiveFilters: false,
        handleClearFilters: vi.fn(),
        isDefaultPurchaseStatus: true,
        ...overrides,
    };

    render(<ItemPivotFilters {...props} />);
    return props;
}

describe("ItemPivotFilters", () => {
    it("normalizes minimum balance values defensively", () => {
        expect(normalizeMinBalance("500")).toBe(500);
        expect(normalizeMinBalance("-999999")).toBe(-999999);
        expect(normalizeMinBalance("bad", 200)).toBe(200);
        expect(normalizeMinBalance(null, 100)).toBe(100);
    });

    it("renders active filter chips and handles clearing when a truthy date string is supplied", () => {
        const props = renderFilters({
            hasActiveFilters: "2026-01-01",
            isDefaultPurchaseStatus: false,
            purchaseStatus: [],
            minBalance: 500,
            licenseStatus: "expired",
            expiryDateFrom: "2026-01-01",
            selectedCompanies: [{ value: 1, label: "Company A" }],
            excludeCompanies: [{ value: 2, label: "Company B" }],
        });

        expect(screen.getByText("Active Filters:")).toBeInTheDocument();
        expect(screen.getByText("Purchase: none")).toBeInTheDocument();
        expect(screen.getByText("Min Balance: Rs.500")).toBeInTheDocument();
        expect(screen.getByText("Status: expired")).toBeInTheDocument();
        expect(screen.getByText("Incl. Companies: 1")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /clear filters/i }));
        expect(props.handleClearFilters).toHaveBeenCalledTimes(1);
    });

    it("wires native filter controls to their callbacks", () => {
        const props = renderFilters();

        fireEvent.change(screen.getByLabelText("Minimum Balance (CIF)"), { target: { value: "500" } });
        fireEvent.change(screen.getByLabelText("License Status"), { target: { value: "expired" } });
        fireEvent.change(screen.getByLabelText("Expiry Date From"), { target: { value: "2026-01-01" } });
        fireEvent.change(screen.getByLabelText("Expiry Date To"), { target: { value: "2026-12-31" } });

        expect(props.setMinBalance).toHaveBeenCalledWith(500);
        expect(props.setLicenseStatus).toHaveBeenCalledWith("expired");
        expect(props.setExpiryDateFrom).toHaveBeenCalledWith("2026-01-01");
        expect(props.setExpiryDateTo).toHaveBeenCalledWith("2026-12-31");
    });

    it("maps selected purchase-status options back to codes", () => {
        const props = renderFilters();
        const select = screen.getByLabelText("Purchase Status") as HTMLSelectElement;

        Array.from(select.options).forEach((option) => {
            option.selected = ["GE", "IP"].includes(option.value);
        });
        fireEvent.change(select);

        expect(props.setPurchaseStatus).toHaveBeenCalledWith(["GE", "IP"]);
    });
});
