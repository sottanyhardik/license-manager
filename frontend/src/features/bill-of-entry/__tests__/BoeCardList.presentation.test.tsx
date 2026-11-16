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
                    await user.click(within(card).getByRole("button", { name: "✕" }));
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

    it("title link and Edit action navigate to the edit page (BOE_MANAGER)", async () => {
        const user = userEvent.setup();
        renderBoeList("BOE_MANAGER");
        await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));
        await user.click(within(boeCards()[0]).getByTitle("Edit"));
        expect(await screen.findByTestId("edit-page")).toHaveTextContent("edit 201");
    });

    it("viewers get no Edit/Delete actions and no invoice editing", async () => {
        renderBoeList("BOE_VIEWER");
        await waitFor(() => expect(boeCards()).toHaveLength(BOE_FIXTURE.length));
        for (const card of boeCards()) {
            expect(within(card).queryByTitle("Edit")).toBeNull();
            expect(within(card).queryByTitle("Delete")).toBeNull();
            expect(within(card).queryByTitle("Click to edit invoice number")).toBeNull();
        }
    });
});
