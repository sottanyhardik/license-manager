import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("react-select", () => ({
    default: ({ placeholder, options = [], onChange }: any) => (
        <div data-testid={placeholder}>
            {options.map((option: any) => (
                <button key={option.value} type="button" onClick={() => onChange(option)}>{option.label}</button>
            ))}
            <button type="button" onClick={() => onChange(null)}>Clear</button>
        </div>
    ),
}));
vi.mock("../components/HybridSelect", () => ({ default: () => null }));
vi.mock("../components/DateRangeFilter", () => ({ default: () => null }));

import AllotmentFilters from "./AllotmentFilters";

const initialFilters = {
    description: "", exporter: "", exclude_exporter: "", license_number: "",
    available_quantity_gte: "", available_quantity_lte: "", available_value_gte: "", available_value_lte: "",
    notification_number: "", norm_class: "", hs_code: "", is_expired: "all", is_restricted: "all",
    purchase_status: "", license_status: "active", item_id: "", expiry_date_from: "", expiry_date_to: "",
    debit_based_on: "PLAN",
};

function Harness() {
    const [filters, setFilters] = useState(initialFilters);
    return <>
        <AllotmentFilters
            filters={filters}
            setFilters={setFilters}
            availableItemNames={[{ value: 1, label: "ALUMINIUM FOIL" }, { value: 2, label: "COPPER FOIL" }]}
            notificationOptions={[]}
            purchaseStatusOptions={[]}
        />
        <output data-testid="description">{filters.description}</output>
        <output data-testid="target">{filters.item_id}</output>
    </>;
}

describe("AllotmentFilters planning target description sync", () => {
    it("copies the displayed target name and replaces it for a changed target", () => {
        render(<Harness />);
        fireEvent.click(screen.getByRole("button", { name: "ALUMINIUM FOIL" }));
        expect(screen.getByTestId("description")).toHaveTextContent("ALUMINIUM FOIL");
        fireEvent.click(screen.getByRole("button", { name: "COPPER FOIL" }));
        expect(screen.getByTestId("description")).toHaveTextContent("COPPER FOIL");
        expect(screen.getByTestId("target")).toHaveTextContent("2");
    });

    it("allows a manual description edit and preserves it when the target is cleared", () => {
        render(<Harness />);
        fireEvent.click(screen.getByRole("button", { name: "ALUMINIUM FOIL" }));
        fireEvent.change(screen.getByPlaceholderText("Filter by item description..."), { target: { value: "MANUAL" } });
        fireEvent.click(within(screen.getByTestId("Select a planning item")).getByRole("button", { name: "Clear" }));
        expect(screen.getByTestId("description")).toHaveTextContent("MANUAL");
    });

    it("clears an unchanged copied description when the target is cleared", () => {
        render(<Harness />);
        fireEvent.click(screen.getByRole("button", { name: "ALUMINIUM FOIL" }));
        fireEvent.click(within(screen.getByTestId("Select a planning item")).getByRole("button", { name: "Clear" }));
        expect(screen.getByTestId("description")).toHaveTextContent("");
    });
});
