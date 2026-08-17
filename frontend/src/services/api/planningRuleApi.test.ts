import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/axios";
import { planSavedSionRules, previewSavedSionRules } from "./planningRuleApi";

vi.mock("@/api/axios", () => ({ default: { post: vi.fn() } }));

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
});
