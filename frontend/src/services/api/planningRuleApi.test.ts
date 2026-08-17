import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/axios";
import { fetchSionPlanningRules, planSavedSionRules, previewSavedSionRules } from "./planningRuleApi";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

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
});
