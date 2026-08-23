import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import SionE5 from "./SionE5";

vi.mock("./SionNormReport", () => ({
    default: ({ sionNorm, title }: { sionNorm: string; title: string }) => (
        <div data-testid="sion-report" data-sion-norm={sionNorm}>
            {title}
        </div>
    ),
}));

describe("SionE5", () => {
    it("renders the shared SION report with the E5 contract", () => {
        render(<SionE5 />);

        expect(screen.getByTestId("sion-report")).toHaveAttribute("data-sion-norm", "E5");
        expect(screen.getByText("SION Norm E5 - Parle Report")).toBeInTheDocument();
    });
});
