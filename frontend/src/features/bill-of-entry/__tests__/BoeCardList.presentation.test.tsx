/**
 * Presentation-equivalence guard for the BOE card register.
 *
 * The snapshot file was recorded against the UNMODIFIED inline MasterList BOE
 * block (before the BoeCardList extraction and the DetailTabs body), so any
 * change to card text, markup, classes, actions, links or role gating fails here.
 * The item table that used to be the whole expanded body must survive unchanged
 * (after the swap it lives in the "Import Items" tab).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";

vi.mock("@/api/axios", () => ({
    default: {
        get: vi.fn((url: string) => {
            if (url === "bill-of-entries/") return Promise.resolve({ data: LIST() });
            // Any tab body stays loading; its content is not snapshotted.
            return new Promise(() => {});
        }),
        post: vi.fn(() => new Promise(() => {})),
        patch: vi.fn(() => new Promise(() => {})),
        put: vi.fn(() => new Promise(() => {})),
        delete: vi.fn(() => new Promise(() => {})),
    },
}));

import BoeCardList, { type BoeCardListProps } from "../BoeCardList";
import { BOE_FIXTURE, LIST_RESPONSE, boeCards, normaliseIds, renderBoeList, type Role } from "./fixtures";

function LIST() {
    return LIST_RESPONSE;
}

const ROLES: Role[] = ["BOE_MANAGER", "BOE_VIEWER", "ACCOUNT_ACCESS"];

/** Card markup without the expanded body (the only part allowed to change). */
function cardChrome(card: HTMLElement) {
    const clone = card.cloneNode(true) as HTMLElement;
    clone.querySelector(".entity-card-detail")?.remove();
    return normaliseIds(clone.outerHTML);
}

async function itemsTableHtml(user: ReturnType<typeof userEvent.setup>, card: HTMLElement) {
    const detail = card.querySelector(".entity-card-detail") as HTMLElement;
    expect(detail).not.toBeNull();
    const tab = within(detail).queryByRole("tab", { name: "Import Items" });
    if (tab) await user.click(tab);
    const table = detail.querySelector(".detail-table-scroller, .surface-panel") as HTMLElement;
    expect(table).not.toBeNull();
    return normaliseIds(table.outerHTML);
}

describe("BOE card register presentation (recorded before extraction)", () => {
    beforeEach(() => vi.clearAllMocks());
    afterEach(() => cleanup());

    for (const role of ROLES) {
        it(`cards, actions, links and expanded item table are identical (${role})`, async () => {
            const user = userEvent.setup();
            renderBoeList(role);
            await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));

            const result: Record<string, unknown> = {};
            for (const [i, item] of BOE_FIXTURE.entries()) {
                const card = boeCards()[i];
                const entry: Record<string, unknown> = {
                    collapsed: cardChrome(card),
                    text: card.textContent,
                    actionTitles: within(card).getAllByRole("button").map((b) => b.getAttribute("title") ?? b.textContent?.trim()),
                    hrefs: within(card).queryAllByRole("link").map((a) => a.getAttribute("href")),
                };

                // Inline invoice edit (gated by canEditInvoice).
                const invoiceBtn = within(card).queryByTitle("Click to edit invoice number");
                entry.canEditInvoice = !!invoiceBtn;
                if (invoiceBtn) {
                    await user.click(invoiceBtn);
                    const input = within(card).getByPlaceholderText("Invoice number") as HTMLInputElement;
                    expect(input.value).toBe(item.invoice_no || "");
                    entry.editingChip = normaliseIds((input.parentElement as HTMLElement).outerHTML);
                    await user.click(within(card).getByRole("button", { name: "Cancel invoice edit" }));
                    expect(within(card).queryByPlaceholderText("Invoice number")).toBeNull();
                }

                // Expand: chrome identical, item table preserved.
                await user.click(within(card).getByTitle("View details"));
                entry.expandedChrome = cardChrome(card);
                entry.itemsTable = await itemsTableHtml(user, card);
                await user.click(within(card).getByTitle("Hide details"));
                expect(card.querySelector(".entity-card-detail")).toBeNull();

                result[String(item.id)] = entry;
            }
            expect(result).toMatchSnapshot();
        });
    }

    /** Expand the card and open its consolidated ActionMenu; returns the menu item labels. */
    async function menuLabels(user: ReturnType<typeof userEvent.setup>, card: HTMLElement) {
        await user.click(within(card).getByTitle("View details"));
        await user.click(within(card).getByRole("button", { name: /^Actions for BOE/ }));
        return screen.queryAllByRole("menuitem").map((m) => m.textContent?.trim());
    }

    it("collapsed cards carry no action icons; actions live in the workspace ActionMenu (D11)", async () => {
        renderBoeList("BOE_MANAGER");
        await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));
        for (const card of boeCards()) {
            for (const t of ["Edit", "Delete", "Transfer Letter", "Merge BOE"]) expect(within(card).queryByTitle(t)).toBeNull();
        }
    });

    it("Edit menu item navigates to the edit page (BOE_MANAGER)", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_MANAGER");
        await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));
        await menuLabels(user, boeCards()[0]);
        await user.click(screen.getByRole("menuitem", { name: "Edit" }));
        expect(await screen.findByTestId("edit-page")).toHaveTextContent("edit 201");
    });

    it("viewers (D2) get the invoice chip but no menu actions at all (no Transfer Letter, no write actions)", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_VIEWER");
        await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));
        for (const card of boeCards()) {
            expect(within(card).getByTitle("Click to edit invoice number")).toBeInTheDocument();
            await user.click(within(card).getByTitle("View details"));
            expect(within(card).queryByRole("button", { name: /^Actions for BOE/ })).toBeNull();
            expect(within(card).queryByRole("button", { name: "Transfer Letter" })).toBeNull();
            await user.click(within(card).getByTitle("Hide details"));
        }
    });

    it("ACCOUNT_ACCESS gets the invoice chip only; TL_GENERATE gets Transfer Letter only", async () => {
        const user = userEvent.setup();
        renderBoeList("ACCOUNT_ACCESS");
        await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));
        const card = boeCards()[0];
        expect(within(card).getByTitle("Click to edit invoice number")).toBeInTheDocument();
        await user.click(within(card).getByTitle("View details"));
        expect(within(card).queryByRole("button", { name: /^Actions for BOE/ })).toBeNull();
        cleanup();

        renderBoeList("TL_GENERATE");
        await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));
        expect(within(boeCards()[0]).queryByTitle("Click to edit invoice number")).toBeNull();
        expect(await menuLabels(user, boeCards()[0])).toEqual(["Transfer Letter"]);
    });

    it("managers get Resolve Dispute, Merge and Update Product Name where applicable, Delete last", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_MANAGER");
        await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));
        const [c201, c202] = boeCards();
        expect(await menuLabels(user, c201)).toEqual(["Edit", "Transfer Letter", "Merge BOE", "Delete"]);
        await user.keyboard("{Escape}");
        expect(await menuLabels(user, c202)).toEqual(["Edit", "Transfer Letter", "Merge BOE", "Resolve Dispute", "Update Product Name", "Delete"]);
    });
});
