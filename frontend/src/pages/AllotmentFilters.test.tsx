import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AllotmentFilters from "./AllotmentFilters";

vi.mock("react-select", () => ({ default: () => <div data-testid="react-select" /> }));
vi.mock("../components/HybridSelect", () => ({ default: () => <div data-testid="hybrid-select" /> }));
vi.mock("../components/DateRangeFilter", () => ({ default: ({ label }: { label: string }) => <div>{label}</div> }));

const filters = {
    description: "RBD Palmolein Oil", exporter: "", exclude_exporter: "", license_number: "", available_quantity_gte: "50", available_quantity_lte: "", available_value_gte: "100", available_value_lte: "", notification_number: "", norm_class: "", hs_code: "", is_expired: "all", is_restricted: "all", purchase_status: "PURCHASED", license_status: "active", item_id: "", expiry_date_from: "", expiry_date_to: "", debit_based_on: "ACTUAL",
};

describe("AllotmentFilters expanded allocation layout", () => {
    it("keeps every allocation criterion visible in the responsive grid", () => {
        render(<AllotmentFilters filters={filters} setFilters={vi.fn()} availableItemNames={[]} notificationOptions={[]} purchaseStatusOptions={[{ value: "PURCHASED", label: "Purchased" }]} />);

        expect(screen.getByLabelText("Item Description")).toHaveValue("RBD Palmolein Oil");
        expect(screen.getByLabelText("Min Available Qty")).toHaveValue(50);
        expect(screen.getByLabelText("Min Available Value")).toHaveValue(100);

        expect(screen.getByLabelText("HS Code")).toBeVisible();
        expect(screen.getByText("Purchase Status")).toBeVisible();
        expect(screen.getByText("Expiry Date")).toBeVisible();
        expect(screen.queryByRole("button", { name: /more filters/i })).not.toBeInTheDocument();
    });
});
