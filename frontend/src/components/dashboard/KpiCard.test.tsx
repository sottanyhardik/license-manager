import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import KpiCard from "./KpiCard";

function renderCard(props: Partial<Parameters<typeof KpiCard>[0]> = {}) {
    return render(
        <MemoryRouter>
            <KpiCard label="Available CIF" value="$48,000.00" unit="USD (FC)" context="5 over-utilised" tooltip="How it is calculated" {...props} />
        </MemoryRouter>,
    );
}

describe("KpiCard", () => {
    it("shows label, unit, value and context, and a click-through link when given a target", () => {
        renderCard({ href: "/licenses?is_expired=false" });
        const link = screen.getByRole("link", { name: "Available CIF: $48,000.00. Open list" });
        expect(link).toHaveAttribute("href", "/licenses?is_expired=false");
        expect(screen.getByText("(USD (FC))")).toBeInTheDocument();
        expect(screen.getByText("5 over-utilised")).toBeInTheDocument();
    });

    it("renders no link when there is no list to open", () => {
        renderCard({ href: undefined });
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
        expect(screen.getByText("$48,000.00")).toBeInTheDocument();
    });

    it("hides the value and context while loading", () => {
        renderCard({ loading: true });
        expect(screen.queryByText("$48,000.00")).not.toBeInTheDocument();
        expect(screen.queryByText("5 over-utilised")).not.toBeInTheDocument();
    });

    it("gives the calculation tooltip an accessible trigger", () => {
        renderCard();
        expect(screen.getByRole("button", { name: "How Available CIF is calculated" })).toBeInTheDocument();
    });
});
