import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/axios";
import { autoPlanLicense, fetchRuleAllocationStrategy, fetchSionPlanningRules, planSavedSionRules, previewSavedSionRules, updateRuleAllocationStrategy, waitForReplanBatch } from "./planningRuleApi";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), patch: vi.fn(), post: vi.fn() } }));

describe("SION planning request payloads", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(api.post).mockResolvedValue({ data: {} });
    });

    it("omits license_ids for the normal SION-first plan and preview", async () => {
        await planSavedSionRules(1);
        await previewSavedSionRules(1);

        expect(api.post).toHaveBeenNthCalledWith(1, "sion-planning-rules/plan-sion/", { sion_id: 1, mode: "NEW" });
        expect(api.post).toHaveBeenNthCalledWith(2, "sion-planning-rules/preview-sion/", { sion_id: 1, mode: "NEW" });
    });

    it("includes an explicit non-empty license restriction", async () => {
        await planSavedSionRules(1, "ALL", [10, 20]);

        expect(api.post).toHaveBeenCalledWith("sion-planning-rules/plan-sion/", {
            sion_id: 1,
            mode: "ALL",
            license_ids: [10, 20],
        });
    });

    it("executes a forced synchronous Auto Plan request", async () => {
        await autoPlanLicense(430);

        expect(api.post).toHaveBeenCalledWith("licenses/430/auto-plan/", { force: true });
    });

    it("normalizes missing and historical leaf expressions for safe rendering", async () => {
        vi.mocked(api.get).mockResolvedValue({ data: [
            { id: 1, expression: undefined },
            { id: 2, expression: { field: "HSN", comparator: "CONTAINS", value: "1701" } },
        ] });

        const rules = await fetchSionPlanningRules(7);

        expect(rules[0].expression).toEqual({ operator: "AND", conditions: [] });
        expect(rules[1].expression).toEqual({ operator: "AND", conditions: [{ field: "HSN", comparator: "CONTAINS", value: "1701" }] });
    });

    it("reads and writes allocation strategy through the canonical action endpoint", async () => {
        const strategy = { strategy: "SPLIT_BY_UNIT_VALUE" as const, config: {
            algorithm: "SPLIT_BY_UNIT_VALUE" as const, basis: "BALANCE_CIF_PER_QUANTITY" as const,
            buckets: [
                { code: "SWP", min_price: "0.00", max_price: "1.50", reference_price: "1.50" },
                { code: "DWP", min_price: "1.50", max_price: "6.50", reference_price: "6.50" },
            ],
        } };
        vi.mocked(api.get).mockResolvedValue({ data: strategy });
        vi.mocked(api.patch).mockResolvedValue({ data: strategy });

        expect(await fetchRuleAllocationStrategy(9)).toEqual(strategy);
        await updateRuleAllocationStrategy(9, strategy);

        expect(api.get).toHaveBeenCalledWith("sion-planning-rules/9/allocation-strategy/");
        expect(api.patch).toHaveBeenCalledWith("sion-planning-rules/9/allocation-strategy/", strategy);
    });
});

describe("waitForReplanBatch", () => {
    const status = (state: "RUNNING" | "SUCCEEDED" | "PARTIAL_FAILURE" | "FAILED") => ({
        state, requested: 2, processed: state === "RUNNING" ? 1 : 2, succeeded: state === "SUCCEEDED" ? 2 : 1, failed: state === "SUCCEEDED" ? 0 : 1,
        skipped: 0, active: state === "RUNNING" ? 1 : 0, partial_failures: 0, unknown_request_ids: [], initiated_by: "ops",
        started_at: null, completed_at: null, errors: [], request_ids: [1, 2],
    });

    it("polls until the server leaves RUNNING and reports the final state", async () => {
        const fetchStatus = vi.fn()
            .mockResolvedValueOnce(status("RUNNING"))
            .mockResolvedValueOnce(status("PARTIAL_FAILURE"));
        const sleep = vi.fn().mockResolvedValue(undefined);
        const progress: string[] = [];

        const result = await waitForReplanBatch([1, 2], {
            fetchStatus, sleep, intervalMs: 5, now: () => 0,
            onProgress: (next) => progress.push(next.state),
        });

        expect(result.timedOut).toBe(false);
        expect(result.status.state).toBe("PARTIAL_FAILURE");
        expect(fetchStatus).toHaveBeenCalledTimes(2);
        expect(sleep).toHaveBeenCalledWith(5);
        expect(progress).toEqual(["RUNNING", "PARTIAL_FAILURE"]);
    });

    it("never converts a still-running batch into success on timeout", async () => {
        let clock = 0;
        const fetchStatus = vi.fn().mockResolvedValue(status("RUNNING"));

        const result = await waitForReplanBatch([1, 2], {
            fetchStatus, sleep: async () => { clock += 1000; }, intervalMs: 1000,
            maxWaitMs: 2500, now: () => clock,
        });

        expect(result.timedOut).toBe(true);
        expect(result.status.state).toBe("RUNNING");
    });

    it("returns a failed batch as failed, not as success", async () => {
        const result = await waitForReplanBatch([1, 2], { fetchStatus: async () => status("FAILED"), sleep: async () => {}, now: () => 0 });

        expect(result.status.state).toBe("FAILED");
        expect(result.timedOut).toBe(false);
    });
});
