import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import OverUtilisedBadge from "./OverUtilisedBadge";
import { formatFiniteDecimal, isLicenceOverUtilised } from "./licenseBalanceHelpers";

describe("isLicenceOverUtilised", () => {
    it("derives from negative balance when flag absent", () => {
        expect(isLicenceOverUtilised("-12.5")).toBe(true);
        expect(isLicenceOverUtilised(0)).toBe(false);
        expect(isLicenceOverUtilised(10)).toBe(false);
        expect(isLicenceOverUtilised(null)).toBe(false);
    });
    it("prefers the explicit flag", () => {
        expect(isLicenceOverUtilised(5, true)).toBe(true);
        expect(isLicenceOverUtilised(-5, false)).toBe(false);
    });
});

describe("negative balance formatting", () => {
    it("keeps the minus sign", () => {
        expect(formatFiniteDecimal("-1234.5")).toBe("-1234.50");
    });
});

describe("OverUtilisedBadge", () => {
    it("renders accessible badge for negative balance", () => {
        render(<OverUtilisedBadge balance={-3} />);
        expect(screen.getByLabelText(/over-utilised/i)).toBeTruthy();
        expect(screen.getByText("Over-utilised")).toBeTruthy();
    });
    it("renders nothing for positive balance", () => {
        const { container } = render(<OverUtilisedBadge balance={3} />);
        expect(container.firstChild).toBeNull();
    });
});
