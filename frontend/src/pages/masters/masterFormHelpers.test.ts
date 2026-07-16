import { describe, expect, it } from "vitest";

import { getMasterFormApiBase } from "./masterFormHelpers";

describe("getMasterFormApiBase", () => {
    it.each([
        ["licenses", "licenses/"],
        ["allotments", "allotments/"],
        ["bill-of-entries", "bill-of-entries/"],
        ["trades", "trades/"],
        ["incentive-licenses", "incentive-licenses/"],
        ["companies", "masters/companies/"],
        [null, ""],
        [undefined, ""],
    ])("resolves %s to %s", (entityName, expected) => {
        expect(getMasterFormApiBase(entityName)).toBe(expected);
    });
});
