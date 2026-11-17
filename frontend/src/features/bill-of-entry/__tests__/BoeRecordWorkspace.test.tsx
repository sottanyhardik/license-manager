import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/api/axios", () => ({
    default: {
        get: vi.fn((url: string) => {
            if (url === "bill-of-entries/") return Promise.resolve({ data: LIST() });
            const boe = url.match(/^bill-of-entries\/(\d+)\/$/);
            if (boe) return Promise.resolve({ data: { id: Number(boe[1]), cha: `CHA of ${boe[1]}`, exchange_rate: "82.30" } });
            const allot = url.match(/^allotments\/(\d+)\/$/);
            if (allot) return Promise.resolve({ data: { id: Number(allot[1]), invoice: `ALLOT-INV-${allot[1]}`, cif_fc: "1500.00" } });
            return new Promise(() => {});
        }),
        post: vi.fn(() => new Promise(() => {})),
        patch: vi.fn(() => new Promise(() => {})),
        put: vi.fn(() => new Promise(() => {})),
        delete: vi.fn(() => new Promise(() => {})),
    },
}));

import api from "@/api/axios";
import { BOE_FIXTURE, LIST_RESPONSE, boeCards, renderBoeList } from "./fixtures";

function LIST() {
    return LIST_RESPONSE;
}

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const tabRequests = () => get.mock.calls.map((c) => c[0] as string).filter((u) => u !== "bill-of-entries/");
const cardFor = (id: number) => boeCards()[BOE_FIXTURE.findIndex((b) => b.id === id)];

async function ready() {
    await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));
}

describe("BOE record workspace (expanded card)", () => {
    beforeEach(() => vi.clearAllMocks());
    afterEach(() => cleanup());

    it("several cards stay open together; each shows only its own data; toggle closes only that card", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_MANAGER");
        await ready();

        await user.click(within(cardFor(201)).getByTitle("View details"));
        const regionA = screen.getByRole("region", { name: "BOE 7012345 details" });
        await user.click(within(regionA).getByRole("tab", { name: "BOE Details" }));
        expect(await screen.findByText("CHA of 201")).toBeInTheDocument();

        await user.click(within(cardFor(202)).getByTitle("View details"));
        expect(screen.getAllByRole("region", { name: /^BOE .* details$/ })).toHaveLength(2);
        const regionB = screen.getByRole("region", { name: "BOE 7012346 details" });
        // B opens on its own default tab, not A's last tab; A keeps its state.
        expect(within(regionB).getByRole("tab", { name: "Import Items" })).toHaveAttribute("aria-selected", "true");
        expect(within(regionA).getByRole("tab", { name: "BOE Details" })).toHaveAttribute("aria-selected", "true");
        expect(screen.getByText("CHA of 201")).toBeInTheDocument();
        await user.click(within(regionB).getByRole("tab", { name: "BOE Details" }));
        expect(await screen.findByText("CHA of 202")).toBeInTheDocument();
        expect(within(regionA).queryByText("CHA of 202")).toBeNull();
        expect(within(regionB).queryByText("CHA of 201")).toBeNull();

        // Toggle semantics: clicking an open card closes only that card.
        await user.click(within(cardFor(201)).getByTitle("Hide details"));
        expect(cardFor(201).querySelector(".entity-card-detail")).toBeNull();
        expect(screen.getAllByRole("region", { name: /^BOE .* details$/ })).toHaveLength(1);
        expect(within(cardFor(201)).getByTitle("View details")).toHaveAttribute("aria-expanded", "false");
    });

    it("each tab requests only its own endpoint, and only when opened", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_MANAGER");
        await ready();
        get.mockClear();

        await user.click(within(cardFor(203)).getByTitle("View details"));
        expect(tabRequests()).toEqual([]);

        const step = async (tab: string, expected: string[]) => {
            get.mockClear();
            await user.click(screen.getByRole("tab", { name: tab }));
            await waitFor(() => expect([...tabRequests()].sort()).toEqual([...expected].sort()));
        };
        await step("Overview", []);
        await step("BOE Details", ["bill-of-entries/203/"]);
        await step("Import Items", []);
        await step("Licence Mapping", []);
        await step("Allotment Mapping", ["allotments/302/", "allotments/303/"]);
        expect(await screen.findByText("ALLOT-INV-302")).toBeInTheDocument();
        expect(screen.getByText("ALLOT-INV-303")).toBeInTheDocument();
        await step("Documents", []);
        await step("Edit Options", []);
    });

    it("renders the requested tabs (Invoices, Reconciliation, Activity omitted) and values as received", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_VIEWER");
        await ready();
        await user.click(within(cardFor(201)).getByTitle("View details"));
        expect(screen.getByRole("tablist", { name: "BOE 7012345 sections" })).toBeInTheDocument();
        expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
            "Overview", "BOE Details", "Import Items", "Licence Mapping", "Allotment Mapping", "Documents", "Edit Options",
        ]);
        await user.click(screen.getByRole("tab", { name: "Overview" }));
        // Amounts are formatted for display only, at the backend's scale (INR to paise).
        const overview = screen.getByRole("tabpanel");
        expect(within(overview).getByText("₹12,34,567.89")).toBeInTheDocument();
        expect(within(overview).getByText("15,000.5")).toBeInTheDocument();
        expect(within(overview).getByText("12.346")).toBeInTheDocument();
        expect(within(overview).getByText("1,215.03")).toBeInTheDocument();
        expect(within(overview).queryByText("1234567.89")).toBeNull();
        await user.click(screen.getByRole("tab", { name: "Licence Mapping" }));
        expect(screen.getByRole("button", { name: "Open License Copy PDF for 0310123456" })).toBeInTheDocument();
        expect(screen.getByText("GE")).toBeInTheDocument();
    });

    it("uses the Licence tab-strip layout (single scrollable row)", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_MANAGER");
        await ready();
        await user.click(within(cardFor(201)).getByTitle("View details"));
        const tabsRoot = screen.getByRole("tablist", { name: "BOE 7012345 sections" }).parentElement;
        expect(tabsRoot).toHaveClass("min-w-0", "[&_[role=tablist]]:flex-nowrap", "[&_[role=tablist]]:overflow-x-auto", "[&_[role=tab]]:shrink-0");
        expect(screen.getByRole("tab", { name: "Import Items" })).toHaveAttribute("aria-selected", "true");
    });

    it("Edit Options keeps the card's gating and handlers", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_VIEWER");
        await ready();
        await user.click(within(cardFor(201)).getByTitle("View details"));
        await user.click(screen.getByRole("tab", { name: "Edit Options" }));
        expect(screen.queryByRole("button", { name: "Edit BOE" })).toBeNull();
        expect(screen.getByRole("button", { name: "Generate Transfer Letter" })).toBeInTheDocument();
        cleanup();

        renderBoeList("BOE_MANAGER");
        await ready();
        await user.click(within(cardFor(201)).getByTitle("View details"));
        await user.click(screen.getByRole("tab", { name: "Edit Options" }));
        await user.click(screen.getByRole("button", { name: "Edit BOE" }));
        expect(await screen.findByTestId("edit-page")).toHaveTextContent("edit 201");
    });

    it("is keyboard operable: arrow keys move between tabs", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_MANAGER");
        await ready();
        await user.click(within(cardFor(201)).getByTitle("View details"));
        const items = screen.getByRole("tab", { name: "Import Items" });
        act(() => items.focus());
        await user.keyboard("{ArrowRight}");
        expect(screen.getByRole("tab", { name: "Licence Mapping" })).toHaveFocus();
        expect(screen.getByRole("tab", { name: "Licence Mapping" })).toHaveAttribute("aria-selected", "true");
    });
});
