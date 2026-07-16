import { describe, expect, it } from "vitest";

import {
    buildTradeJsonPayload,
    cleanIncentiveLine,
    cleanTradeLine,
    cleanTradePayment,
    formatTradeDateForApi,
    getEntityId,
} from "./tradeFormHelpers";

describe("tradeFormHelpers", () => {
    it("formats Date values for API without changing existing API strings", () => {
        expect(formatTradeDateForApi(new Date("2026-07-16T00:00:00Z"))).toBe("2026-07-16");
        expect(formatTradeDateForApi("01-07-2026")).toBe("01-07-2026");
        expect(formatTradeDateForApi(null)).toBeNull();
    });

    it("extracts entity IDs from primitive and object FK values", () => {
        expect(getEntityId(10)).toBe(10);
        expect(getEntityId({ id: 22, name: "Acme" })).toBe(22);
        expect(getEntityId(null)).toBeUndefined();
    });

    it("cleans trade lines for API writes", () => {
        expect(
            cleanTradeLine({
                id: "",
                sr_number: { id: 501 },
                hsn_code: "ignored",
                amount_inr: "1200",
            }),
        ).toEqual({
            sr_number: 501,
            hsn_code: "49070000",
            amount_inr: "1200",
        });
    });

    it("cleans incentive lines and payments for API writes", () => {
        expect(cleanIncentiveLine({ id: null, incentive_license: { id: 8 }, amount_inr: 500 })).toEqual({
            incentive_license: 8,
            amount_inr: 500,
        });
        expect(cleanTradePayment({ id: undefined, date: new Date("2026-07-16T00:00:00Z"), amount: 100 })).toEqual({
            date: "2026-07-16",
            amount: 100,
        });
    });

    it("builds the non-file TradeForm payload", () => {
        expect(
            buildTradeJsonPayload(
                {
                    direction: "PURCHASE",
                    license_type: "DFIA",
                    from_company: { id: 101 },
                    to_company: 202,
                    boe: undefined,
                    invoice_number: " TRD-1 ",
                    invoice_date: new Date("2026-07-16T00:00:00Z"),
                    lines: [{ sr_number: { id: 501 }, amount_inr: "1200" }],
                    incentive_lines: [],
                    payments: [],
                },
                false,
            ),
        ).toEqual(
            expect.objectContaining({
                direction: "PURCHASE",
                license_type: "DFIA",
                from_company: 101,
                to_company: 202,
                boe: null,
                invoice_number: "TRD-1",
                invoice_date: "2026-07-16",
                lines: [{ sr_number: 501, amount_inr: "1200", hsn_code: "49070000" }],
                incentive_lines: [],
                payments: [],
                auto_create_paired: false,
            }),
        );
    });
});
