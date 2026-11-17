import { describe, expect, it } from "vitest";

import * as R from "./authorizationRoles";
import { REPORT_ROLES, ROLES } from "./authorizationRoles";

describe("ROLES", () => {
    it("has the expected role codes (key === value)", () => {
        expect(Object.values(ROLES).sort()).toEqual([
            "ACCOUNTS_APPROVER", "ACCOUNTS_MANAGER", "ACCOUNTS_VIEWER", "ACCOUNT_ACCESS", "ALLOTMENT_MANAGER", "ALLOTMENT_VIEWER", "BOE_MANAGER", "BOE_VIEWER",
            "INCENTIVE_LICENSE_MANAGER", "INCENTIVE_LICENSE_VIEWER", "LEDGER_MANAGER", "LICENSE_MANAGER",
            "LICENSE_VIEWER", "REPORT_VIEWER", "TL_GENERATE", "TRADE_MANAGER", "TRADE_VIEWER", "USER_MANAGER",
        ]);
        for (const [k, v] of Object.entries(ROLES)) expect(v).toBe(k);
    });
});

describe("REPORT_ROLES", () => {
    it("matches the backend ReportPermission read policy", () => {
        expect(REPORT_ROLES).toEqual([
            "REPORT_VIEWER", "LICENSE_MANAGER", "TRADE_MANAGER", "ALLOTMENT_MANAGER", "BOE_MANAGER",
            "INCENTIVE_LICENSE_MANAGER",
        ]);
    });
});

describe("named role sets", () => {
    it("are unchanged", () => {
        const { ROLES: _r, ...sets } = R;
        expect(sets).toMatchInlineSnapshot(`
          {
            "ACCOUNTING_ROLES": [
              "ACCOUNTS_VIEWER",
              "ACCOUNTS_MANAGER",
              "ACCOUNTS_APPROVER",
            ],
            "ALLOTMENT_ROLES": [
              "ALLOTMENT_MANAGER",
              "ALLOTMENT_VIEWER",
            ],
            "BOE_LIST_ROLES": [
              "BOE_MANAGER",
              "BOE_VIEWER",
              "TL_GENERATE",
              "ACCOUNT_ACCESS",
            ],
            "BOE_TRANSFER_LETTER_ROLES": [
              "BOE_MANAGER",
              "TL_GENERATE",
            ],
            "INCENTIVE_LICENSE_ROLES": [
              "INCENTIVE_LICENSE_MANAGER",
              "INCENTIVE_LICENSE_VIEWER",
            ],
            "LEDGER_PACKAGE_READINESS_ROLES": [
              "LICENSE_MANAGER",
              "TRADE_MANAGER",
              "LEDGER_MANAGER",
            ],
            "LEDGER_READ_ROLES": [
              "LICENSE_MANAGER",
              "TRADE_MANAGER",
              "TRADE_VIEWER",
              "LEDGER_MANAGER",
            ],
            "LEDGER_UPLOAD_ROLES": [
              "LICENSE_MANAGER",
              "LEDGER_MANAGER",
            ],
            "LICENSE_OVERVIEW_ROLES": [
              "LICENSE_MANAGER",
              "LICENSE_VIEWER",
              "BOE_MANAGER",
              "BOE_VIEWER",
              "TRADE_MANAGER",
              "TRADE_VIEWER",
            ],
            "LICENSE_ROLES": [
              "LICENSE_MANAGER",
              "LICENSE_VIEWER",
            ],
            "RECONCILIATION_ISSUES_ROLES": [
              "TRADE_MANAGER",
              "TRADE_VIEWER",
              "BOE_MANAGER",
              "BOE_VIEWER",
              "ACCOUNT_ACCESS",
              "TL_GENERATE",
            ],
            "RECONCILIATION_ROLES": [
              "BOE_MANAGER",
              "TRADE_MANAGER",
              "ACCOUNT_ACCESS",
            ],
            "REPORT_ROLES": [
              "REPORT_VIEWER",
              "LICENSE_MANAGER",
              "TRADE_MANAGER",
              "ALLOTMENT_MANAGER",
              "BOE_MANAGER",
              "INCENTIVE_LICENSE_MANAGER",
            ],
            "TRADE_ROLES": [
              "TRADE_MANAGER",
              "TRADE_VIEWER",
            ],
            "USER_ADMIN_ROLES": [
              "USER_MANAGER",
            ],
          }
        `);
    });
});
