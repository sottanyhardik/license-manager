import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { BoeActivity as BoeActivityData } from "@/pages/dashboardContract";
import BoeActivity from "./BoeActivity";
import { v3Fixture } from "./fixtures";

const boeSection = v3Fixture.boe_activity as BoeActivityData;

function renderBoe(section: BoeActivityData | { error: string } | undefined, search = "") {
    return render(
        <MemoryRouter>
            <BoeActivity section={section} search={search} />
        </MemoryRouter>,
    );
}

describe("BoeActivity", () => {
    it("renders the recent rows from a valid section", () => {
        renderBoe(boeSection);

        const table = screen.getByRole("table", { name: "Bills of entry" });
        expect(within(table).getAllByRole("row")).toHaveLength(boeSection.recent.length + 1);
        expect(within(table).getByRole("link", { name: boeSection.recent[0]!.bill_of_entry_number })).toBeInTheDocument();
    });

    it("shows the count tiles from the section", () => {
        renderBoe(boeSection);

        expect(screen.getByTitle(/no licence item rows/)).toHaveTextContent(String(boeSection.pending_licence_mapping));
        expect(screen.getByText("Without invoice no.")).toBeInTheDocument();
    });

    it("filters the visible rows by the page search across the importer and BOE number", () => {
        renderBoe(boeSection, "importer two");

        const table = screen.getByRole("table", { name: "Bills of entry" });
        const dataRows = within(table).getAllByRole("row").slice(1);
        expect(dataRows.length).toBeGreaterThan(0);
        for (const row of dataRows) {
            expect(row.textContent?.toLowerCase()).toContain("importer two");
        }
    });

    it("shows the search empty message when no visible row matches", () => {
        renderBoe(boeSection, "no-such-importer-xyz");

        expect(screen.getByText("No BOEs match the search.")).toBeInTheDocument();
    });

    it("shows the pending-mapping rows on the pending tab", () => {
        renderBoe(boeSection);

        fireEvent.mouseDown(screen.getByRole("tab", { name: "Pending licence mapping" }));
        fireEvent.click(screen.getByRole("tab", { name: "Pending licence mapping" }));

        expect(screen.getByText(/Showing up to \d+ of/)).toBeInTheDocument();
    });

    it("shows the empty state when a list is empty, not a crash", () => {
        renderBoe({ ...boeSection, recent: [] });

        expect(screen.getByText("No recent BOE records.")).toBeInTheDocument();
    });

    it("shows the section error message when the section failed", () => {
        renderBoe({ error: "Dashboard section 'boe_activity' could not be loaded" });

        expect(screen.getByText(/Dashboard section 'boe_activity' could not be loaded/)).toBeInTheDocument();
    });

    it("renders nothing when the section is absent because the role does not grant it", () => {
        const { container } = renderBoe(undefined);

        expect(container).toBeEmptyDOMElement();
    });
});
