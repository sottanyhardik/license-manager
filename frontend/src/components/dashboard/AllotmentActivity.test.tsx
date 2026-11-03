import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { AllotmentActivity as AllotmentActivityData, AllotmentActivityRow } from "@/pages/dashboardContract";
import AllotmentActivity from "./AllotmentActivity";
import { v3Fixture } from "./fixtures";

const section = v3Fixture.allotment_activity as AllotmentActivityData;

function renderAllotments(
    value: AllotmentActivityData | { error: string } | undefined,
    props: { search?: string; onRetry?: () => void; retrying?: boolean } = {},
) {
    return render(
        <MemoryRouter>
            <AllotmentActivity
                section={value}
                search={props.search ?? ""}
                allotmentsHref="/allotments"
                onRetry={props.onRetry}
                retrying={props.retrying}
            />
        </MemoryRouter>,
    );
}

function row(overrides: Partial<AllotmentActivityRow>): AllotmentActivityRow {
    return { ...section.recent[0]!, ...overrides };
}

describe("AllotmentActivity", () => {
    it("shows every requested column header", () => {
        renderAllotments(section);

        const table = screen.getByRole("table", { name: /Recent allotments/ });
        for (const label of [
            "Reference", "Date", "Customer", "Licence", "Item", "Original qty",
            "Allocated CIF (FC)", "Utilised CIF (FC)", "Remaining reservation", "Status",
        ]) {
            const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
            expect(within(table).getByRole("columnheader", { name: new RegExp(escaped) })).toBeInTheDocument();
        }
    });

    it("links the reference to the allotment and the licence to its workspace", () => {
        renderAllotments(section);

        const first = section.recent[0]!;
        expect(screen.getByRole("link", { name: first.reference })).toHaveAttribute("href", `/allotments/${first.id}/allocate`);
        expect(screen.getByRole("link", { name: first.licences[0]!.license_number })).toHaveAttribute(
            "href",
            `/licenses?licence=${first.licences[0]!.id}`,
        );
    });

    it("shows the original quantity and the quantity on items as separate figures", () => {
        renderAllotments({
            ...section,
            recent: [row({ original_quantity: "100.00", allocated_quantity: "60.00", unplaced_quantity: "40.00", remaining_quantity: "60.00" })],
        });

        const table = screen.getByRole("table", { name: /Recent allotments/ });
        expect(within(table).getByText("100.00")).toBeInTheDocument();
        expect(within(table).getByText("unplaced 40.00")).toBeInTheDocument();
        expect(within(table).getByText("qty 60.00")).toBeInTheDocument();
    });

    it("names the not-reserved CIF when it is non-zero, in the row and in the footer", () => {
        renderAllotments(section);

        const table = screen.getByRole("table", { name: /Recent allotments/ });
        const tfoot = table.querySelector("tfoot") as HTMLElement;
        expect(within(table).getAllByText(/Not reserved \$/).length).toBe(2);
        expect(within(tfoot).getByText(/Not reserved \$15,100\.00/)).toBeInTheDocument();
        expect(screen.getByText(/Allocated CIF = Utilised \+ Remaining reservation \+ Not reserved/)).toBeInTheDocument();
    });

    it("does not show the not-reserved line when it is zero", () => {
        renderAllotments({
            ...section,
            recent: [row({ not_reserved_cif: "0.00", status: "open", reserved_cif: "47300.00", consumed_cif: "0.00", boe_count: 0 })],
            totals: { allotted_cif: "47300.00", consumed_cif: "0.00", reserved_cif: "47300.00", not_reserved_cif: "0.00" },
        });

        const table = screen.getByRole("table", { name: /Recent allotments/ });
        expect(within(table).queryByText(/Not reserved/)).not.toBeInTheDocument();
    });

    it("shows the scope totals in the footer", () => {
        renderAllotments(section);

        const table = screen.getByRole("table", { name: /Recent allotments/ });
        const tfoot = table.querySelector("tfoot") as HTMLElement;
        expect(within(tfoot).getByText("Total, all allotments in scope")).toBeInTheDocument();
        expect(within(tfoot).getByText("$24,100.00")).toBeInTheDocument();
        expect(within(tfoot).getByText("$9,000.00")).toBeInTheDocument();
    });

    it("labels statuses by what the engine reports, including a BOE link without an allocation", () => {
        renderAllotments({
            ...section,
            recent: [
                row({ id: 1, status: "open" }),
                row({ id: 2, status: "partly_consumed" }),
                row({ id: 3, status: "consumed" }),
                row({ id: 4, status: "boe_linked", boe_count: 2 }),
            ],
        });

        const table = screen.getByRole("table", { name: /Recent allotments/ });
        expect(within(table).getAllByText("Open").length).toBeGreaterThan(0);
        expect(within(table).getByText("Partly utilised")).toBeInTheDocument();
        expect(within(table).getByText("Fully utilised")).toBeInTheDocument();
        expect(within(table).getByText("BOE linked, no allocation")).toBeInTheDocument();
        expect(within(table).getByText("2 BOEs")).toBeInTheDocument();
    });

    it("searches across the licence number, keeping matching rows", () => {
        renderAllotments({
            ...section,
            recent: [row({ id: 1, licences: [{ id: 11, license_number: "LIC-ALPHA" }] }), row({ id: 2, licences: [{ id: 22, license_number: "LIC-BETA" }] })],
        }, { search: "beta" });

        const table = screen.getByRole("table", { name: /Recent allotments/ });
        expect(within(table).getByRole("link", { name: "LIC-BETA" })).toBeInTheDocument();
        expect(within(table).queryByRole("link", { name: "LIC-ALPHA" })).not.toBeInTheDocument();
    });

    it("says when no row matches the search", () => {
        renderAllotments(section, { search: "no-such-allotment-xyz" });

        expect(screen.getByText("No allotments match the search.")).toBeInTheDocument();
    });

    it("renders the empty state for a valid empty list, not an error", () => {
        renderAllotments({ ...section, total: 0, recent: [], counts: { open: 0, partly_consumed: 0, consumed: 0, boe_linked: 0 } });

        expect(screen.getByText("No recent allotments")).toBeInTheDocument();
        expect(screen.queryByText(/could not be loaded/)).not.toBeInTheDocument();
    });

    it("shows the section error with a Retry action that calls onRetry", () => {
        const onRetry = vi.fn();
        renderAllotments({ error: "Dashboard section 'allotment_activity' could not be loaded" }, { onRetry });

        expect(screen.getByText(/could not be loaded/)).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Retry Allotment activity" }));
        expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it("shows the loading skeleton while a retry is in flight, not the old error", () => {
        renderAllotments({ error: "Could not load" }, { onRetry: vi.fn(), retrying: true });

        expect(screen.getByTestId("section-skeleton")).toBeInTheDocument();
        expect(screen.queryByText(/Could not load/)).not.toBeInTheDocument();
    });

    it("renders nothing when the section is absent because the role does not grant it", () => {
        const { container } = renderAllotments(undefined);

        expect(container).toBeEmptyDOMElement();
    });

    it("exposes the table scroller as a keyboard-reachable region", () => {
        renderAllotments(section);

        const region = screen.getByRole("region", { name: /scroll horizontally/ });
        expect(region).toHaveAttribute("tabindex", "0");
    });
});
