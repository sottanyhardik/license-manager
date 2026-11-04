import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import IncentiveLicensesTable from "./IncentiveLicensesTable";

const baseItem = {
    license_expiry_date: "2099-01-01",
    license_date: "2025-01-01",
};

function renderWith(items: any[]) {
    return render(
        <IncentiveLicensesTable
            loading={false}
            data={items}
            canWrite={false}
            entityName="Incentive Licenses"
            filterParams={{}}
            currentPage={1}
            pageSize={25}
            navigate={vi.fn()}
            onDelete={vi.fn()}
        />,
    );
}

describe("IncentiveLicensesTable sold status labels", () => {
    it("shows Available only for an explicit NO", () => {
        renderWith([{ ...baseItem, id: 1, license_number: "A", sold_status: "NO" }]);
        expect(screen.getByText("Available")).toBeInTheDocument();
    });

    it("shows Partial for PARTIAL", () => {
        renderWith([{ ...baseItem, id: 2, license_number: "B", sold_status: "PARTIAL" }]);
        expect(screen.getByText("Partial")).toBeInTheDocument();
    });

    it("shows Sold for YES", () => {
        renderWith([{ ...baseItem, id: 3, license_number: "C", sold_status: "YES" }]);
        expect(screen.getByText("Sold")).toBeInTheDocument();
        expect(screen.queryByText("Available")).not.toBeInTheDocument();
    });

    it("never shows a licence as Available when sold_status is missing", () => {
        renderWith([{ ...baseItem, id: 4, license_number: "D" }]);
        expect(screen.queryByText("Available")).not.toBeInTheDocument();
        expect(screen.getByText("Unknown")).toBeInTheDocument();
    });
});
