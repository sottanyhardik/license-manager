import { describe, expect, it } from "vitest";

import { v3Fixture } from "./fixtures";
import { CONTRACT_ERROR_MESSAGE, parseDashboardPayload, parseDashboardSection } from "./payloadContract";

/** The raw shape a test can corrupt. Typed loosely on purpose: the validator is what checks it. */
type LooseResponse = {
    meta: unknown;
    allotment_activity: { recent: Record<string, unknown>[]; totals?: unknown };
};

function clone(value: unknown): LooseResponse {
    return JSON.parse(JSON.stringify(value)) as LooseResponse;
}

describe("allotment activity contract", () => {
    it("accepts the documented row and totals shape", () => {
        const result = parseDashboardPayload(clone(v3Fixture));

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.violations).toEqual([]);
        expect(result.payload.allotment_activity).toEqual(v3Fixture.allotment_activity);
    });

    it("rejects a row missing the not-reserved figure, naming the exact path", () => {
        const raw = clone(v3Fixture);
        delete raw.allotment_activity.recent[0].not_reserved_cif;

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.payload.allotment_activity).toEqual({ error: CONTRACT_ERROR_MESSAGE });
        expect(result.violations).toEqual([
            {
                section: "allotment_activity",
                problem: "allotment_activity.recent[0].not_reserved_cif should be a 2-decimal money string",
            },
        ]);
    });

    it("rejects licences that are not a list, rather than showing no licence", () => {
        const raw = clone(v3Fixture);
        raw.allotment_activity.recent[0].licences = "0311009039";

        const result = parseDashboardSection("allotment_activity", { meta: raw.meta, allotment_activity: raw.allotment_activity });

        expect(result.section).toEqual({ error: CONTRACT_ERROR_MESSAGE });
        expect(result.violations).toEqual([
            { section: "allotment_activity", problem: "allotment_activity.recent[0].licences should be an array" },
        ]);
    });

    it("rejects a missing totals block, so the footer cannot invent zeros", () => {
        const raw = clone(v3Fixture);
        delete raw.allotment_activity.totals;

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.payload.allotment_activity).toEqual({ error: CONTRACT_ERROR_MESSAGE });
        expect(result.violations[0]?.problem).toBe("allotment_activity.totals should be an object");
    });

    it("rejects a float quantity, because quantities cross the API as 2-decimal strings", () => {
        const raw = clone(v3Fixture);
        raw.allotment_activity.recent[0].original_quantity = 20000;

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.violations.map((v) => v.problem)).toContain(
            "allotment_activity.recent[0].original_quantity should be a 2-decimal money string",
        );
    });

    it("rejects an unknown status rather than labelling it", () => {
        const raw = clone(v3Fixture);
        raw.allotment_activity.recent[0].status = "cancelled";

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.payload.allotment_activity).toEqual({ error: CONTRACT_ERROR_MESSAGE });
    });
});
