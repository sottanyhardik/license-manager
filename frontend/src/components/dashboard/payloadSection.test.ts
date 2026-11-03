import { describe, expect, it } from "vitest";

import { v3Fixture } from "./fixtures";
import { CONTRACT_ERROR_MESSAGE, parseDashboardSection } from "./payloadContract";

/** A single-section response: meta plus the one section, as the backend returns for `?section=`. */
function singleSection(name: "boe_activity" | "invoice_activity" | "allotment_activity"): Record<string, unknown> {
    return { meta: JSON.parse(JSON.stringify(v3Fixture.meta)), [name]: JSON.parse(JSON.stringify(v3Fixture[name])) };
}

describe("parseDashboardSection", () => {
    it("returns a valid BOE section with no violations", () => {
        const result = parseDashboardSection("boe_activity", singleSection("boe_activity"));

        expect(result.violations).toEqual([]);
        expect(result.section).toEqual(v3Fixture.boe_activity);
    });

    it("returns a valid invoice section with no violations", () => {
        const result = parseDashboardSection("invoice_activity", singleSection("invoice_activity"));

        expect(result.violations).toEqual([]);
        expect(result.section).toEqual(v3Fixture.invoice_activity);
    });

    it("accepts an empty list as a valid empty section", () => {
        const raw = singleSection("boe_activity");
        (raw.boe_activity as Record<string, unknown>).recent = [];

        const result = parseDashboardSection("boe_activity", raw);

        expect(result.violations).toEqual([]);
        expect(result.section).toMatchObject({ recent: [] });
    });

    it("passes a section error through unchanged", () => {
        const raw = { meta: v3Fixture.meta, boe_activity: { error: "Could not load" } };

        const result = parseDashboardSection("boe_activity", raw);

        expect(result.violations).toEqual([]);
        expect(result.section).toEqual({ error: "Could not load" });
    });

    it("treats a response without the requested section as a violation, not an empty section", () => {
        const raw = { meta: v3Fixture.meta };

        const result = parseDashboardSection("invoice_activity", raw);

        expect(result.section).toEqual({ error: CONTRACT_ERROR_MESSAGE });
        expect(result.violations).toEqual([{ section: "invoice_activity", problem: "invoice_activity is missing from the response" }]);
    });

    it("replaces a malformed section with a contract error and names the exact path", () => {
        const raw = singleSection("invoice_activity");
        (raw.invoice_activity as Record<string, unknown>).recent = "not a list";

        const result = parseDashboardSection("invoice_activity", raw);

        expect(result.section).toEqual({ error: CONTRACT_ERROR_MESSAGE });
        expect(result.violations).toEqual([{ section: "invoice_activity", problem: "invoice_activity.recent should be an array" }]);
    });

    it("rejects a response that is not an object", () => {
        const result = parseDashboardSection("boe_activity", "<html>");

        expect(result.section).toEqual({ error: CONTRACT_ERROR_MESSAGE });
        expect(result.violations[0]?.section).toBe("root");
    });

    it("reports a malformed meta alongside the section", () => {
        const raw = singleSection("boe_activity");
        delete (raw as { meta?: unknown }).meta;

        const result = parseDashboardSection("boe_activity", raw);

        expect(result.violations).toContainEqual({ section: "meta", problem: "meta should be an object" });
    });
});
