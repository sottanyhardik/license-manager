import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock("@/utils/pdfPreview", () => ({ openPdfPreview: vi.fn() }));

import api from "@/api/axios";
import AllotmentsTable from "@/pages/masters/tables/AllotmentsTable";
import { ALLOTMENT_FIXTURES } from "./fixtures";

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const navigate = vi.fn();

/** Mirrors MasterList's Set-based toggle state. */
function Harness({ canWrite = true }: { canWrite?: boolean }) {
    const [expanded, setExpanded] = useState<Set<number>>(new Set());
    const toggle = (id: number) => setExpanded((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id); else next.add(id);
        return next;
    });
    return (
        <AllotmentsTable
            loading={false} data={ALLOTMENT_FIXTURES} canWrite={canWrite} entityName="allotments"
            filterParams={{}} currentPage={1} pageSize={25} navigate={navigate} onDelete={vi.fn()}
            expandedAllotments={expanded} toggleAllotment={toggle}
        />
    );
}

function setup(canWrite = true) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={qc}><Harness canWrite={canWrite} /></QueryClientProvider>);
    return userEvent.setup();
}

const card = (invoice: string) =>
    screen.getByText(invoice, { selector: ".entity-card-title" }).closest("article") as HTMLElement;
const urls = () => get.mock.calls.map((c) => c[0]);

beforeEach(() => {
    vi.clearAllMocks();
    get.mockImplementation((url: string) => {
        const id = Number(url.match(/^allotments\/(\d+)\/$/)?.[1]);
        const row = ALLOTMENT_FIXTURES.find((r) => r.id === id);
        if (row) return Promise.resolve({ data: { ...row, alloted_quantity: `ALLOTTED-${id}`, contact_person: `Contact-${id}` } });
        return Promise.resolve({ data: new Blob() });
    });
});

describe("Allotment record workspace", () => {
    it("several cards stay open together; each shows only its own data, keyed per record; toggle closes only that card", async () => {
        const user = setup();
        await user.click(within(card("INV-101")).getByTitle("View details"));
        // Default tab is Allotment Details (row data): expanding makes zero requests.
        expect(within(card("INV-101")).getByRole("tab", { name: "Allotment Details" })).toHaveAttribute("aria-selected", "true");
        expect(within(card("INV-101")).getByText("Palm Oil RBD")).toBeInTheDocument();
        expect(get).not.toHaveBeenCalled();

        await user.click(within(card("INV-103")).getByTitle("View details"));
        expect(screen.getAllByRole("tablist")).toHaveLength(2);
        expect(within(card("INV-103")).getByText("No items have been allotted yet.")).toBeInTheDocument();
        expect(within(card("INV-103")).queryByText("Palm Oil RBD")).toBeNull();
        expect(within(card("INV-101")).getByText("Palm Oil RBD")).toBeInTheDocument();
        expect(within(card("INV-101")).getByTitle("Hide details")).toHaveAttribute("aria-expanded", "true");
        expect(get).not.toHaveBeenCalled();

        // Toggle semantics: clicking an open card closes only that card.
        await user.click(within(card("INV-101")).getByTitle("Hide details"));
        expect(card("INV-101").querySelector(".entity-card-detail")).toBeNull();
        expect(card("INV-103").querySelector(".entity-card-detail")).not.toBeNull();
        expect(within(card("INV-101")).getByTitle("View details")).toHaveAttribute("aria-expanded", "false");
    });

    it("each tab requests only its own endpoint, only when opened, and unmounts on switch", async () => {
        const user = setup();
        const a = card("INV-101");
        await user.click(within(a).getByTitle("View details"));
        // Default Allotment Details: no request on expand.
        expect(within(a).getByText("Palm Oil RBD")).toBeInTheDocument();
        expect(get).not.toHaveBeenCalled();
        // Overview -> allotments/:id/ once, only when clicked.
        await user.click(within(a).getByRole("tab", { name: "Overview" }));
        await user.click(await within(a).findByRole("button", { name: "Shipment & contact" }));
        expect(within(a).getByText("Contact-101")).toBeInTheDocument();
        expect(urls()).toEqual(["allotments/101/"]);

        // Allotment Details -> list row data, no request; Overview unmounted.
        await user.click(within(a).getByRole("tab", { name: "Allotment Details" }));
        expect(within(a).getByText("Palm Oil RBD")).toBeInTheDocument();
        expect(within(a).queryByText("Contact-101")).toBeNull();
        expect(urls()).toEqual(["allotments/101/"]);

        // Licence Mapping / Utilisation -> same allotments/:id/ (cached), no new request.
        await user.click(within(a).getByRole("tab", { name: "Licence Mapping" }));
        expect(within(a).getAllByText("0310001111").length).toBeGreaterThan(0);
        await user.click(within(a).getByRole("tab", { name: "Utilisation" }));
        expect(within(a).getByText("ALLOTTED-101")).toBeInTheDocument();
        expect(urls()).toEqual(["allotments/101/"]);

        // Documents -> nothing until a button is pressed.
        await user.click(within(a).getByRole("tab", { name: "Documents" }));
        expect(urls()).toEqual(["allotments/101/"]);
        await user.click(within(within(a).getByRole("tabpanel")).getByRole("button", { name: "Open License Copy PDF for 0310002222" }));
        await waitFor(() => expect(urls()).toEqual(["allotments/101/", "licenses/22/merged-documents/"]));
        await user.click(within(within(a).getByRole("region", { name: "Allotment PDF" })).getByRole("button", { name: "Preview PDF" }));
        await waitFor(() => expect(urls()[2]).toBe("allotment-actions/101/generate-pdf/"));
    });

    it("Edit Options exposes only the existing actions, gated by role", async () => {
        let user = setup(true);
        let a = card("INV-101");
        await user.click(within(a).getByTitle("View details"));
        await user.click(within(a).getByRole("tab", { name: "Edit Options" }));
        const panel = within(a).getByRole("tabpanel");
        expect(within(panel).getAllByRole("button").map((b) => b.textContent)).toEqual(
            ["Edit", "Copy", "Allocate", "Preview PDF", "Download", "Delete"],
        );
        await user.click(within(panel).getByRole("button", { name: "Allocate" }));
        expect(navigate).toHaveBeenCalledWith("/allotments/101/allocate");

        document.body.innerHTML = "";
        user = setup(false);
        a = card("INV-101");
        await user.click(within(a).getByTitle("View details"));
        await user.click(within(a).getByRole("tab", { name: "Edit Options" }));
        expect(within(within(a).getByRole("tabpanel")).getAllByRole("button").map((b) => b.textContent)).toEqual(
            ["Preview PDF", "Download"],
        );
    });
});
