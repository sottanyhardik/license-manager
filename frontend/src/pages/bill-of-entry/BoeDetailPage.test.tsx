import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/axios", () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(() => new Promise(() => {})),
        patch: vi.fn(() => new Promise(() => {})),
        put: vi.fn(() => new Promise(() => {})),
        delete: vi.fn(() => new Promise(() => {})),
    },
}));

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { BOE_FIXTURE, authFor, type Role } from "@/features/bill-of-entry/__tests__/fixtures";
import BoeDetailPage from "./BoeDetailPage";

const get = api.get as unknown as ReturnType<typeof vi.fn>;

function Where() {
    const l = useLocation();
    return <div data-testid="where">{l.pathname}{l.search}</div>;
}

function renderAt(path: string, role: Role = "BOE_MANAGER") {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={queryClient}>
            <AuthContext.Provider value={authFor(role) as never}>
                <MemoryRouter initialEntries={[path]}>
                    <Routes>
                        <Route path="/bill-of-entries" element={<div data-testid="register">register</div>} />
                        <Route path="/bill-of-entries/:id" element={<BoeDetailPage />} />
                        <Route path="/bill-of-entries/:id/generate-transfer-letter" element={<div data-testid="tl">tl</div>} />
                        <Route path="/bill-of-entries/:id/edit" element={<div data-testid="edit">edit</div>} />
                    </Routes>
                    <Where />
                </MemoryRouter>
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
}

describe("BoeDetailPage (/bill-of-entries/:id)", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        sessionStorage.clear();
        get.mockImplementation((url: string) => {
            const m = url.match(/^bill-of-entries\/(\d+)\/$/);
            if (m) {
                const rec = BOE_FIXTURE.find((b) => b.id === Number(m[1]));
                return rec ? Promise.resolve({ data: rec }) : Promise.reject({ response: { status: 404 } });
            }
            return new Promise(() => {});
        });
    });
    afterEach(() => cleanup());

    it("renders header, opens on Overview and fetches via the typed detail endpoint", async () => {
        renderAt("/bill-of-entries/201");
        expect(await screen.findByRole("heading", { name: "BOE 7012345" })).toBeInTheDocument();
        expect(screen.getByText(/05-01-2025 · INNSA1/)).toBeInTheDocument();
        expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
        expect(get).toHaveBeenCalledWith("bill-of-entries/201/");
    });

    it("honours ?tab= deep links, falls back for unknown tabs, and tab clicks update the URL", async () => {
        const user = userEvent.setup();
        renderAt("/bill-of-entries/201?tab=import-items");
        expect(await screen.findByRole("tab", { name: "Import Items" })).toHaveAttribute("aria-selected", "true");
        expect(screen.getByRole("tabpanel")).toHaveTextContent("Palm oil");
        await user.click(screen.getByRole("tab", { name: "Overview" }));
        expect(screen.getByTestId("where")).toHaveTextContent("/bill-of-entries/201?tab=overview");
        cleanup();
        renderAt("/bill-of-entries/201?tab=nope");
        expect(await screen.findByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    });

    it("Back returns to the register and flags saved-filter restore", async () => {
        const user = userEvent.setup();
        renderAt("/bill-of-entries/201");
        await user.click(await screen.findByRole("button", { name: /back/i }));
        expect(screen.getByTestId("register")).toBeInTheDocument();
        expect(JSON.parse(sessionStorage.getItem("allotmentListFilters") as string).returnTo).toBe("list");
    });

    it("shows not-found for an unknown or malformed id (no fetch for malformed)", async () => {
        renderAt("/bill-of-entries/999");
        expect(await screen.findByText("Bill of entry not found")).toBeInTheDocument();
        cleanup();
        get.mockClear();
        renderAt("/bill-of-entries/abc");
        expect(await screen.findByText("Bill of entry not found")).toBeInTheDocument();
        expect(get).not.toHaveBeenCalled();
    });

    it("shows a retryable error for non-404 failures", async () => {
        get.mockImplementation(() => Promise.reject({ response: { status: 500 } }));
        renderAt("/bill-of-entries/201");
        expect(await screen.findByText("Could not load bill of entry", {}, { timeout: 4000 })).toBeInTheDocument();
    });

    it("action menu is role-gated like the card (manager vs viewer vs TL)", async () => {
        const user = userEvent.setup();
        renderAt("/bill-of-entries/201", "BOE_MANAGER");
        await user.click(await screen.findByRole("button", { name: /more actions for BOE 7012345/i }));
        const labels = (await screen.findAllByRole("menuitem")).map((e) => e.textContent);
        expect(labels).toEqual(expect.arrayContaining(["Edit", "Transfer Letter", "Merge BOE", "Delete"]));
        cleanup();

        renderAt("/bill-of-entries/201", "BOE_VIEWER");
        await screen.findByRole("heading", { name: "BOE 7012345" });
        expect(screen.queryByRole("button", { name: /more actions/i })).toBeNull();
        cleanup();

        renderAt("/bill-of-entries/201", "TL_GENERATE");
        await user.click(await screen.findByRole("button", { name: /more actions for BOE 7012345/i }));
        const tl = (await screen.findAllByRole("menuitem")).map((e) => e.textContent);
        expect(tl).toEqual(["Transfer Letter"]);
        await user.click(screen.getByRole("menuitem", { name: "Transfer Letter" }));
        await waitFor(() => expect(screen.getByTestId("tl")).toBeInTheDocument());
    });

    it("Edit action opens the edit route and does not clobber saved register filters", async () => {
        const user = userEvent.setup();
        sessionStorage.setItem("filterState_bill-of-entries", JSON.stringify({
            filters: { port: "INNSA1" }, pagination: { currentPage: 3, pageSize: 25 }, search: "", timestamp: Date.now(),
        }));
        renderAt("/bill-of-entries/201");
        await user.click(await screen.findByRole("button", { name: /more actions for BOE 7012345/i }));
        await user.click(await screen.findByRole("menuitem", { name: "Edit" }));
        expect(await screen.findByTestId("edit")).toBeInTheDocument();
        const saved = JSON.parse(sessionStorage.getItem("filterState_bill-of-entries") as string);
        expect(saved.filters).toEqual({ port: "INNSA1" });
        expect(saved.pagination.currentPage).toBe(3);
        expect(within(document.body).queryByText("Bill of entry not found")).toBeNull();
    });
});
