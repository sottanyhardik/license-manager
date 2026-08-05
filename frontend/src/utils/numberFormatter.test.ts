import { describe, expect, it } from "vitest";

import { formatIndianCompact } from "./numberFormatter";

describe("formatIndianCompact", () => {
    it("abbreviates a lakh-range value to '<n> L'", () => {
        expect(formatIndianCompact(4795006)).toBe("47.95 L");
    });

    it("abbreviates a crore-range value to '<n> Cr'", () => {
        expect(formatIndianCompact(126904430)).toBe("12.69 Cr");
    });

    it("falls back to formatIndianNumber for a value under 1 lakh (no abbreviation)", () => {
        expect(formatIndianCompact(32)).toBe("32.00");
        expect(formatIndianCompact(99999)).toBe("99,999.00");
    });

    it("preserves the negative sign for a negative value (e.g. a Profit/Loss)", () => {
        expect(formatIndianCompact(-4321.55)).toBe("-4,321.55");
        expect(formatIndianCompact(-126904430)).toBe("-12.69 Cr");
    });

    it("re-expresses as Cr instead of rounding up to '100.00 L' near the 1-crore boundary", () => {
        // 99.99994... lakhs rounds to "100.00" at 2 decimals — must switch
        // to the Cr branch instead of displaying the nonsensical "100.00 L".
        expect(formatIndianCompact(9999994)).toBe("1.00 Cr");
        expect(formatIndianCompact(9999999.995)).toBe("1.00 Cr");
        // Just below the rounding threshold: genuinely stays in L.
        expect(formatIndianCompact(9994000)).toBe("99.94 L");
    });
});
