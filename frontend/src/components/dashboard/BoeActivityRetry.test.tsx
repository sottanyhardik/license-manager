import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import BoeActivity from "./BoeActivity";
import { v3Fixture } from "./fixtures";

function renderBoe(section: Parameters<typeof BoeActivity>[0]["section"], props: { onRetry?: () => void; retrying?: boolean } = {}) {
    return render(
        <MemoryRouter>
            <BoeActivity section={section} search="" onRetry={props.onRetry} retrying={props.retrying} />
        </MemoryRouter>,
    );
}

describe("BoeActivity retry", () => {
    it("shows the section error with a Retry action that calls onRetry", () => {
        const onRetry = vi.fn();
        renderBoe({ error: "This section could not be loaded. Check the connection, then retry" }, { onRetry });

        fireEvent.click(screen.getByRole("button", { name: "Retry BOE activity" }));
        expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it("shows the loading skeleton while a retry is in flight", () => {
        renderBoe({ error: "Could not load" }, { onRetry: vi.fn(), retrying: true });

        expect(screen.getByTestId("section-skeleton")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Retry BOE activity" })).not.toBeInTheDocument();
    });

    it("renders the BOE rows after a successful retry supplies the section", () => {
        const { rerender } = renderBoe({ error: "Could not load" }, { onRetry: vi.fn() });
        rerender(
            <MemoryRouter>
                <BoeActivity section={v3Fixture.boe_activity} search="" onRetry={vi.fn()} retrying={false} />
            </MemoryRouter>,
        );

        expect(screen.getByRole("table", { name: "Bills of entry" })).toBeInTheDocument();
        expect(screen.queryByText(/could not be loaded/)).not.toBeInTheDocument();
    });
});
