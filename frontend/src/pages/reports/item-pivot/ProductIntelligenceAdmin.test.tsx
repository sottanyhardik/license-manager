import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import api from "@/api/axios";
import ProductIntelligenceAdmin from "./ProductIntelligenceAdmin";
import type { IntelAdmin, IntelModel } from "./matchingShared";

const model = (id: number, status: IntelModel["status"], passed: boolean): IntelModel => ({
    id, version: `pm-${id}`, status, algorithm: "logreg", dataset: "ds-1", notes: status === "INSUFFICIENT_LABELS" ? "Needs ≥60 verified labels" : "",
    metrics: status === "INSUFFICIENT_LABELS" ? { labels: 5 } : { labels: 80, holdout: { precision: 0.97, recall: 0.8, false_merge_rate: 0.03, ece: 0.04, n: 20 }, gate: { passed, failures: passed ? [] : ["recall 0.4 < 0.5"] } },
    comparison: {}, trained_on: "2026-11-19T00:00:00Z", promoted_on: null, trained_by: "mgr",
});
const admin = (canManage = true): IntelAdmin => ({
    can_manage: canManage,
    inventory: [{ source: "licence_import_item", records: 26818, unique_normalised: 1612, duplicate_observations: 21851, missing_description: 3355, missing_hsn: 3368, master_links: { none: 7306, one: 15775, several: 3737 }, trust: "Master links are proxy only" }],
    labels: { verified: 5, positive: 5, negative: 0, required: { total: 60, per_class: 20 }, new_since_last_dataset: 0 },
    active_model: null, promotion_gate: { precision: 0.95, false_merge_rate: 0.05, recall: 0.5, ece: 0.1 },
    models: [model(3, "CANDIDATE", true), model(2, "CANDIDATE", false), model(1, "INSUFFICIENT_LABELS", false)],
    datasets: [{ id: 1, version: "ds-1", observations: 58486, unique: 7041, labels: 5, sha256: "606995088ad70b6e", created_on: "2026-11-19T00:00:00Z" }],
    aliases: 0, events: [{ id: 1, action: "train", detail: { status: "INSUFFICIENT_LABELS" }, user: "mgr", on: "2026-11-19T00:00:00Z" }],
});

function setup(canManage = true) {
    vi.mocked(api.get).mockImplementation(async (url: string) => (url.startsWith("item-pivot/matching/aliases") ? { data: { aliases: [] } } : { data: admin(canManage) }));
    vi.mocked(api.post).mockResolvedValue({ data: {} });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProductIntelligenceAdmin /></QueryClientProvider>);
    return userEvent.setup();
}

beforeEach(() => vi.clearAllMocks());

describe("Product intelligence admin", () => {
    it("shows inventory, label progress and that no model is active", async () => {
        setup();
        expect(await screen.findByText("None — deterministic + alias matching")).toBeInTheDocument();
        expect(screen.getByText("5 / 60 (5 match · 0 not)")).toBeInTheDocument();
        expect(within(screen.getByRole("table", { name: "Inventory" })).getByText("26,818")).toBeInTheDocument();
        expect(screen.getByText("Needs ≥60 verified labels")).toBeInTheDocument();
    });

    it("promotes only candidates that passed the gate and queues training in the background", async () => {
        const user = setup();
        const table = await screen.findByRole("table", { name: "Models" });
        const promote = within(table).getAllByRole("button", { name: "Promote" });
        expect(promote[0]).toBeEnabled();
        expect(promote[1]).toBeDisabled();
        await user.click(promote[0]);
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/admin/models/3/promote/"));
        await user.click(screen.getByRole("button", { name: /Generate dataset \+ train candidate/ }));
        await waitFor(() => expect(api.post).toHaveBeenCalledWith("item-pivot/matching/admin/train/", { train: true }));
    });

    it("hides management actions from viewers", async () => {
        setup(false);
        await screen.findByRole("table", { name: "Models" });
        expect(screen.queryByRole("button", { name: "Promote" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /train candidate/ })).not.toBeInTheDocument();
    });
});
