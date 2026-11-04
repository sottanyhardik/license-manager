import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PlanningDashboardStrip } from "./PlanningDashboardStrip";
import { summaryTiles } from "./planningOperationsModel";
import * as rulesApi from "@/services/api/planningRuleApi";

vi.mock("@/services/api/planningRuleApi", () => ({ fetchPlanningDashboard: vi.fn() }));

const dashboard = {
    totals: { norms: 4, norms_with_active_rules: 3, active_rules: 9, inactive_rules: 2, draft_rules: null, validation_errors: 1, warnings: 0 },
    last_rule_change: { modified_on: "2026-11-02T09:00:00Z", modified_by: "asha", rule_id: 3 },
    jobs: { pending: 2, failed: 1, last_successful_execution: null, last_requested: null },
    norms: [],
};

const renderStrip = () => render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <PlanningDashboardStrip />
    </QueryClientProvider>,
);

describe("PlanningDashboardStrip", () => {
    beforeEach(() => vi.clearAllMocks());

    it("shows the canonical KPIs and marks drafts as not modelled", async () => {
        vi.mocked(rulesApi.fetchPlanningDashboard).mockResolvedValue(dashboard);
        renderStrip();

        expect(await screen.findByText("Active rules")).toBeInTheDocument();
        expect(screen.getByText("9")).toBeInTheDocument();
        expect(screen.getByText("Not modelled")).toBeInTheDocument();
        expect(screen.getByText("Failed jobs").parentElement).toHaveTextContent("1");
        expect(screen.getByText(/by asha/)).toBeInTheDocument();
        expect(screen.getByText(/Last successful planning run: Never/)).toBeInTheDocument();
    });

    it("shows a loading state before data arrives", () => {
        vi.mocked(rulesApi.fetchPlanningDashboard).mockReturnValue(new Promise(() => {}));
        renderStrip();

        expect(screen.getByRole("status")).toHaveTextContent("Loading planning overview");
    });

    it("shows an error with a retry action and recovers", async () => {
        vi.mocked(rulesApi.fetchPlanningDashboard)
            .mockRejectedValueOnce(new Error("boom"))
            .mockResolvedValueOnce(dashboard);
        renderStrip();

        expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
        await userEvent.click(screen.getByRole("button", { name: "Retry" }));
        expect(await screen.findByText("Active rules")).toBeInTheDocument();
    });

    it("shows an empty state when no norms exist", async () => {
        vi.mocked(rulesApi.fetchPlanningDashboard).mockResolvedValue({ ...dashboard, totals: { ...dashboard.totals, norms: 0 } });
        renderStrip();

        expect(await screen.findByText("No active SION norms are configured yet.")).toBeInTheDocument();
    });

    it("flags validation errors and failed jobs as danger tones", () => {
        const tiles = summaryTiles(dashboard);
        expect(tiles.find((tile) => tile.label === "Validation errors")?.tone).toBe("danger");
        expect(tiles.find((tile) => tile.label === "Warnings")?.tone).toBe("ok");
    });
});
