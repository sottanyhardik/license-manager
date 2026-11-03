import { afterEach, describe, expect, it, vi } from "vitest";

import { v3Fixture } from "./fixtures";
import { CONTRACT_ERROR_MESSAGE, parseDashboardPayload, reportContractViolations } from "./payloadContract";

/** A deep copy the tests can mutate without touching the shared fixture. */
function clone(): Record<string, any> {
    return JSON.parse(JSON.stringify(v3Fixture));
}

describe("parseDashboardPayload", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("accepts a valid payload with no violations", () => {
        const result = parseDashboardPayload(clone());

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.violations).toEqual([]);
        expect(result.payload.boe_activity).toEqual(v3Fixture.boe_activity);
    });

    it("accepts empty arrays as valid empty results", () => {
        const raw = clone();
        raw.boe_activity.recent = [];
        raw.boe_activity.pending_mapping = [];
        raw.boe_activity.recently_modified = [];

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.violations).toEqual([]);
        expect(result.payload.boe_activity).toMatchObject({ recent: [], pending_mapping: [] });
    });

    it("leaves a section absent when the role does not grant it, without a violation", () => {
        const raw = clone();
        delete raw.boe_activity;

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.violations).toEqual([]);
        expect("boe_activity" in result.payload).toBe(false);
    });

    it("passes a section error through unchanged", () => {
        const raw = clone();
        raw.boe_activity = { error: "Dashboard section 'boe_activity' could not be loaded" };

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.violations).toEqual([]);
        expect(result.payload.boe_activity).toEqual({ error: "Dashboard section 'boe_activity' could not be loaded" });
    });

    it("replaces a section whose array is missing with a section error, and reports it", () => {
        const raw = clone();
        delete raw.boe_activity.pending_mapping;

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.payload.boe_activity).toEqual({ error: CONTRACT_ERROR_MESSAGE });
        expect(result.violations).toEqual([
            { section: "boe_activity", problem: "boe_activity.pending_mapping should be an array" },
        ]);
    });

    it("rejects a null section, because absent is the only valid way to omit one", () => {
        const raw = clone();
        raw.boe_activity = null;

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.payload.boe_activity).toEqual({ error: CONTRACT_ERROR_MESSAGE });
        expect(result.violations[0]?.section).toBe("boe_activity");
    });

    it("rejects a malformed array that is an object rather than a list", () => {
        const raw = clone();
        raw.boe_activity.recent = { results: raw.boe_activity.recent };

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.payload.boe_activity).toEqual({ error: CONTRACT_ERROR_MESSAGE });
        expect(result.violations).toEqual([{ section: "boe_activity", problem: "boe_activity.recent should be an array" }]);
    });

    it("rejects a row with the wrong field type, naming the exact path", () => {
        const raw = clone();
        raw.boe_activity.pending_mapping[0].id = "8001234";

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.violations).toEqual([
            { section: "boe_activity", problem: "boe_activity.pending_mapping[0].id should be a finite number" },
        ]);
    });

    it("rejects a money field that is a float rather than a 2-dp string", () => {
        const raw = clone();
        raw.financial.available_cif = 48000;

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.payload.financial).toEqual({ error: CONTRACT_ERROR_MESSAGE });
        expect(result.violations.map((v) => v.problem)).toContain(
            "financial.available_cif should be a 2-decimal money string",
        );
    });

    it("accepts the C969 section with its optional error next to count and rows", () => {
        const raw = clone();
        raw.c969_link_review = { count: 0, rows: [], error: "C969 link review could not run" };

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.violations).toEqual([]);
        expect(result.payload.c969_link_review).toEqual({ count: 0, rows: [], error: "C969 link review could not run" });
    });

    it("rejects the whole payload when meta is missing, because no section can be trusted without it", () => {
        const raw = clone();
        delete raw.meta;

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(false);
        expect(result.violations).toEqual([{ section: "meta", problem: "meta should be an object" }]);
    });

    it("rejects the whole payload when attention is not a list, rather than showing no exceptions", () => {
        const raw = clone();
        raw.attention = null;

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(false);
        expect(result.violations).toEqual([{ section: "attention", problem: "attention should be an array" }]);
    });

    it("rejects a response that is null, a string or a list", () => {
        for (const raw of [null, "dashboard", [v3Fixture]]) {
            const result = parseDashboardPayload(raw);
            expect(result.ok).toBe(false);
            expect(result.violations[0]?.section).toBe("root");
        }
    });

    it("ignores unknown extra keys so the backend can add fields", () => {
        const raw = clone();
        raw.future_section = { anything: true };

        const result = parseDashboardPayload(raw);

        expect(result.ok).toBe(true);
        if (!result.ok) return;
        expect(result.violations).toEqual([]);
    });
});

describe("reportContractViolations", () => {
    it("logs one structured error per response that has violations", () => {
        const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
        reportContractViolations([{ section: "boe_activity", problem: "boe_activity.pending_mapping should be an array" }]);

        expect(spy).toHaveBeenCalledTimes(1);
        expect(spy.mock.calls[0]?.[0]).toContain("contract v3");
    });

    it("stays silent when there are no violations", () => {
        const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
        reportContractViolations([]);

        expect(spy).not.toHaveBeenCalled();
    });
});
