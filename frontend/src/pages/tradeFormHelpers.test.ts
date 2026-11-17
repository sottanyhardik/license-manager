import { describe, expect, it } from "vitest";

import {
    buildTradeJsonPayload,
    cleanIncentiveLine,
    cleanTradeLine,
    cleanTradePayment,
    formatTradeDateForApi,
    getEntityId,
    roundPaise,
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
                    boes: [{ id: 301 }, 302, null],
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
                boes: [301, 302],
                invoice_number: "TRD-1",
                invoice_date: "2026-07-16",
                lines: [{ sr_number: 501, amount_inr: "1200", hsn_code: "49070000" }],
                incentive_lines: [],
                payments: [],
                auto_create_paired: false,
            }),
        );
    });

    it("does not submit hidden DFIA rows with an Incentive trade", () => {
        expect(
            buildTradeJsonPayload(
                {
                    direction: "SALE",
                    license_type: "INCENTIVE",
                    boes: [],
                    invoice_date: "01-09-2026",
                    lines: [{ sr_number: null, amount_inr: 0 }],
                    incentive_lines: [{ incentive_license: { id: 8 }, license_value: 909129 }],
                    payments: [],
                },
                false,
            ),
        ).toEqual(expect.objectContaining({
            lines: [],
            incentive_lines: [{ incentive_license: 8, license_value: 909129 }],
        }));
    });
});

describe("roundPaise (T3: paise, half-up)", () => {
    it("rounds to 2 dp half-up, including binary-float halves", () => {
        expect(roundPaise(7900.079)).toBe(7900.08);
        expect(roundPaise(1.005)).toBe(1.01);
        expect(roundPaise(218072.91175)).toBe(218072.91);
        expect(roundPaise(1234567.005)).toBe(1234567.01);
        expect(roundPaise(100000.125)).toBe(100000.13);
        expect(roundPaise(-1.005)).toBe(-1.01);
        expect(roundPaise(Number.NaN)).toBe(0);
    });
});
