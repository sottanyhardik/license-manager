import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../../api/axios";
import { openAuthedFile } from "../../utils/documentDownload";
import ItemPivotReport from "./ItemPivotReport";

vi.mock("react-router-dom", async (importOriginal) => ({
    ...(await importOriginal<typeof import("react-router-dom")>()),
    useNavigate: () => vi.fn(),
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
}));
vi.mock("../../api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("../../utils/documentDownload", () => ({ openAuthedFile: vi.fn(() => Promise.resolve()) }));
vi.mock("sonner", () => ({
    toast: { dismiss: vi.fn(), error: vi.fn(), info: vi.fn(), success: vi.fn() },
}));

const get = vi.mocked(api.get);
const count = (prefix: string) => get.mock.calls.filter(([u]) => String(u).startsWith(prefix)).length;

describe("ItemPivotReport request counts", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        get.mockImplementation((url: string) => {
            if (url.startsWith("item-pivot/available-norms/")) {
                return Promise.resolve({ data: [{ norm_class: "E1", description: "Confectionery" }] });
            }
            if (url.startsWith("reports/item-pivot/")) {
                return Promise.resolve({ data: { items: [], licenses_by_norm_notification: {}, norm_notes_conditions: {} } });
            }
            return Promise.resolve({ data: { results: [] } });
        });
    });

    it("loads available-norms once and debounces min-balance changes into one report GET", async () => {
        render(<ItemPivotReport />);
        fireEvent.click((await screen.findAllByRole("button", { name: /E1/ }))[0]);
        await waitFor(() => expect(count("reports/item-pivot/")).toBe(1));

        const select = screen.getByLabelText(/Minimum Balance/);
        fireEvent.change(select, { target: { value: "1000" } });
        fireEvent.change(select, { target: { value: "5000" } });
        fireEvent.change(select, { target: { value: "10000" } });

        await waitFor(() => expect(count("reports/item-pivot/")).toBe(2), { timeout: 2000 });
        await new Promise((r) => setTimeout(r, 600));
        expect(count("reports/item-pivot/")).toBe(2);
        expect(count("item-pivot/available-norms/")).toBe(1);
    });

    it("export and filter chips use the same min balance as the displayed data while the debounce is pending", async () => {
        render(<ItemPivotReport />);
        fireEvent.click((await screen.findAllByRole("button", { name: /E1/ }))[0]);
        await waitFor(() => expect(count("reports/item-pivot/")).toBe(1));
        fireEvent.change(screen.getByLabelText(/Minimum Balance/), { target: { value: "5000" } });
        fireEvent.click(screen.getByRole("button", { name: /excel/i }));
        await waitFor(() => expect(vi.mocked(openAuthedFile)).toHaveBeenCalledTimes(1));
        const exportedPath = String(vi.mocked(openAuthedFile).mock.calls[0][0]);
        // Export is filtered by the value the table currently shows (initial 200), not the pending 5000.
        expect(exportedPath).not.toContain("5000");
        expect(exportedPath).toContain("200");
    });
});
