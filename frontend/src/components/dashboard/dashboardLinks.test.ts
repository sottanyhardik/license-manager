import { describe, expect, it } from "vitest";

import {
    addDays,
    activeLicencesTarget,
    attentionTarget,
    bandTarget,
    LICENCE_LIST_FILTERS,
    licenceEditPath,
    licenceList,
    LIST_PATHS,
    QUICK_ACTION_PATHS,
    withinTarget,
} from "./dashboardLinks";

const ASOF = "2026-11-02";

function paramsOf(href: string): URLSearchParams {
    const query = href.split("?")[1] ?? "";
    return new URLSearchParams(query);
}

function licenceLinks(): string[] {
    const links = [
        licenceList({ is_expired: "all" }),
        licenceList({ is_expired: false }, 7),
        licenceList({ is_expired: true }),
        licenceList({ is_null: true, is_expired: "all" }, 3),
        withinTarget(7, ASOF),
        withinTarget(60, ASOF, 9),
    ];
    for (const key of ["expired", "d0_7", "d8_15", "d16_30", "d31_60", "over_60", "inactive"]) {
        const target = bandTarget(key, ASOF, 5);
        if (target) links.push(target);
    }
    for (const key of ["missing_dgft"]) {
        const target = attentionTarget(key, null);
        if (target) links.push(target);
    }
    return links.filter((link) => link.startsWith("/licenses"));
}

describe("dashboard links", () => {
    it("uses only licence-list filter names verified against the backend", () => {
        expect([...LICENCE_LIST_FILTERS].sort()).toEqual(
            ["exporter", "is_active", "is_expired", "is_null", "license_expiry_date_from", "license_expiry_date_to", "search"].sort(),
        );
    });

    it("never emits a parameter the licence list does not accept", () => {
        const accepted = new Set<string>(LICENCE_LIST_FILTERS);
        for (const link of licenceLinks()) {
            for (const key of paramsOf(link).keys()) {
                expect(accepted.has(key), `${link} uses ${key}`).toBe(true);
            }
        }
        for (const link of licenceLinks()) {
            expect(link).not.toMatch(/company_id|status=/);
        }
    });

    it("always sets is_expired explicitly, because the licence list defaults it to false", () => {
        for (const link of licenceLinks()) {
            if (link.includes("?") && !link.includes("is_expired=")) {
                throw new Error(`${link} omits is_expired`);
            }
        }
    });

    it("builds the Active link from is_active and is_expired, the same predicate as the count", () => {
        const active = paramsOf(activeLicencesTarget(4));
        expect(active.get("is_active")).toBe("true");
        expect(active.get("is_expired")).toBe("false");
        expect(active.get("exporter")).toBe("4");
    });

    it("scopes licence links to a company through the exporter filter", () => {
        expect(paramsOf(licenceList({ is_expired: true }, 7)).get("exporter")).toBe("7");
        expect(paramsOf(licenceList({ is_expired: true })).has("exporter")).toBe(false);
    });

    it("builds the expiry windows from the as-of date, not the browser clock", () => {
        const window7 = paramsOf(withinTarget(7, ASOF));
        expect(window7.get("license_expiry_date_from")).toBe("2026-11-02");
        expect(window7.get("license_expiry_date_to")).toBe("2026-11-09");
        expect(window7.get("is_expired")).toBe("false");

        const over60 = paramsOf(bandTarget("over_60", ASOF) ?? "");
        expect(over60.get("license_expiry_date_from")).toBe("2027-01-02");
        expect(over60.has("license_expiry_date_to")).toBe(false);
    });

    it("returns no link for bands that cannot be expressed with declared filters", () => {
        expect(bandTarget("no_expiry", ASOF)).toBeNull();
        expect(bandTarget("inactive", ASOF)).toBeNull();
    });

    it("returns null for unknown attention keys instead of a guessed URL", () => {
        expect(attentionTarget("some_future_key", null)).toBeNull();
    });

    it("keeps detail links on record ids", () => {
        expect(licenceEditPath(812)).toBe("/licenses/812/edit");
    });

    it("exposes only routes that exist in the app router", () => {
        expect(QUICK_ACTION_PATHS).toEqual({
            newLicence: "/licenses/create",
            newAllotment: "/allotments/create",
            newBoe: "/bill-of-entries/create",
            newInvoice: "/trades/create",
            reconciliation: "/reconciliation",
            reports: "/reports/item-report",
        });
        expect(LIST_PATHS.boes).toBe("/bill-of-entries");
    });

    it("adds days by calendar arithmetic across month boundaries", () => {
        expect(addDays("2026-10-30", 5)).toBe("2026-11-04");
        expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    });
});
