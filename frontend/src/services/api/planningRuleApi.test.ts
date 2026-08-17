import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/axios";
import { fetchRuleAllocationStrategy, fetchSionPlanningRules, planSavedSionRules, previewSavedSionRules, updateRuleAllocationStrategy } from "./planningRuleApi";

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
