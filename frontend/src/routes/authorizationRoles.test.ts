import { describe, expect, it } from "vitest";

import { REPORT_ROLES } from "./authorizationRoles";

describe("REPORT_ROLES", () => {
    it("matches the backend ReportPermission read policy", () => {
        expect(REPORT_ROLES).toEqual([
            "REPORT_VIEWER",
            "LICENSE_MANAGER",
            "TRADE_MANAGER",
            "ALLOTMENT_MANAGER",
            "BOE_MANAGER",
            "INCENTIVE_LICENSE_MANAGER",
        ]);
    });
});
