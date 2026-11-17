import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StatusBadge } from "./StatusBadge";
import { TONES, TONE_MAP } from "./tone";
import { EmptyState } from "./EmptyState";
import { LoadingState } from "./LoadingState";
import { InlineError } from "./InlineError";
import { ConfirmProvider, useConfirm, ConfirmDialog } from "./ConfirmDialog";
import { SearchInput } from "./SearchInput";
import { DateRangePicker } from "./DateRangePicker";
import { ActivityTimeline } from "./ActivityTimeline";
import { QueryBoundary } from "./QueryBoundary";

describe("StatusBadge", () => {
    it.each(TONES)("applies token classes for %s without raw palette or hex", (tone) => {
        render(<StatusBadge tone={tone} label={`L-${tone}`} />);
        const el = screen.getByText(`L-${tone}`);
        expect(el).toHaveAttribute("data-tone", tone);
        for (const cls of TONE_MAP[tone].soft.split(" ")) expect(el).toHaveClass(cls);
        for (const t of TONES) {
            const all = Object.values(TONE_MAP[t]).join(" ");
            expect(all).not.toMatch(/#[0-9a-f]{3,6}|(red|green|blue|amber|slate|gray|yellow)-\d{2,3}/i);
        }
    });
    it("supports solid appearance", () => {
        render(<StatusBadge tone="danger" label="Bad" appearance="solid" />);
        expect(screen.getByText("Bad")).toHaveClass("bg-destructive");
    });
});

describe("EmptyState / LoadingState / InlineError", () => {
    it("renders EmptyState as status with action", () => {
        render(<EmptyState title="No licences" description="Try again" action={<button>Add</button>} />);
        expect(screen.getByRole("status")).toHaveTextContent("No licences");
        expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
    });
    it("renders LoadingState variants with status role and reduced-motion spinner", () => {
        const { rerender, container } = render(<LoadingState variant="skeleton-rows" rows={3} label="Loading rows" />);
        expect(screen.getByRole("status", { name: "Loading rows" })).toBeInTheDocument();
        expect(container.querySelectorAll("[data-slot='skeleton']").length).toBe(3);
        rerender(<LoadingState variant="spinner" />);
        expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
        expect(container.querySelector(".motion-reduce\\:animate-none")).not.toBeNull();
    });
    it("InlineError shows DRF message and retry", async () => {
        const onRetry = vi.fn();
        render(<InlineError error={{ response: { data: { detail: "Denied" } } }} onRetry={onRetry} />);
        expect(screen.getByRole("alert")).toHaveTextContent("Denied");
        await userEvent.click(screen.getByRole("button", { name: "Retry" }));
        expect(onRetry).toHaveBeenCalled();
    });
});

function Harness({ danger = false, requireText }: { danger?: boolean; requireText?: string }) {
    const confirm = useConfirm();
    return (
        <>
            <button onClick={async () => {
                const ok = await confirm({ title: "Sure?", tone: danger ? "danger" : "default", requireText });
                document.title = String(ok);
            }}>Open</button>
        </>
    );
}

describe("ConfirmDialog", () => {
    it("resolves true on confirm and focuses Confirm for default tone", async () => {
        render(<ConfirmProvider><Harness /></ConfirmProvider>);
        await userEvent.click(screen.getByRole("button", { name: "Open" }));
        const dialog = await screen.findByRole("alertdialog");
        expect(dialog).toBeInTheDocument();
        await waitFor(() => expect(screen.getByRole("button", { name: "Confirm" })).toHaveFocus());
        await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
        await waitFor(() => expect(document.title).toBe("true"));
    });
    it("Esc resolves false, danger focuses Cancel, and focus is trapped", async () => {
        const user = userEvent.setup();
        render(<ConfirmProvider><Harness danger /></ConfirmProvider>);
        await user.click(screen.getByRole("button", { name: "Open" }));
        await screen.findByRole("alertdialog");
        await waitFor(() => expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus());
        for (let i = 0; i < 4; i++) {
            await user.tab();
            expect(screen.getByRole("alertdialog").contains(document.activeElement)).toBe(true);
        }
        await user.keyboard("{Escape}");
        await waitFor(() => expect(document.title).toBe("false"));
        await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    });
    it("requireText gates Confirm", async () => {
        const user = userEvent.setup();
        render(<ConfirmProvider><Harness danger requireText="DELETE" /></ConfirmProvider>);
        await user.click(screen.getByRole("button", { name: "Open" }));
        const confirmBtn = await screen.findByRole("button", { name: "Confirm" });
        expect(confirmBtn).toBeDisabled();
        await user.type(screen.getByLabelText(/to confirm/), "DELETE");
        expect(confirmBtn).toBeEnabled();
    });
    it("async onConfirm disables both buttons until settled (controlled form)", async () => {
        let release!: () => void;
        const onConfirm = vi.fn(() => new Promise<void>((r) => { release = r; }));
        const onOpenChange = vi.fn();
        render(<ConfirmDialog open onOpenChange={onOpenChange} onConfirm={onConfirm} title="Go?" />);
        await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
        expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Confirm" })).toHaveAttribute("aria-busy", "true");
        expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
        release();
        await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    });
});

describe("SearchInput / DateRangePicker / ActivityTimeline", () => {
    it("SearchInput debounces, clears immediately, and syncs external value", async () => {
        vi.useFakeTimers();
        const onChange = vi.fn();
        const { rerender } = render(<SearchInput value="" onChange={onChange} label="Search" delay={300} />);
        const input = screen.getByRole("searchbox", { name: "Search" });
        const { fireEvent, act } = await import("@testing-library/react");
        fireEvent.change(input, { target: { value: "abc" } });
        expect(onChange).not.toHaveBeenCalled();
        act(() => { vi.advanceTimersByTime(300); });
        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange).toHaveBeenLastCalledWith("abc");
        fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
        expect(onChange).toHaveBeenLastCalledWith("");
        rerender(<SearchInput value="ext" onChange={onChange} label="Search" />);
        expect(input).toHaveValue("ext");
        vi.useRealTimers();
    });

    it("DateRangePicker emits ISO ranges, presets, and blocks inverted ranges", async () => {
        const { fireEvent } = await import("@testing-library/react");
        const onChange = vi.fn();
        const presets = [{ id: "y", label: "Year", range: () => ({ from: "2026-01-01", to: "2026-12-31" }) }];
        const { rerender } = render(<DateRangePicker label="Expiry" value={{ to: "2026-06-01" }} onChange={onChange} presets={presets} />);
        fireEvent.change(screen.getByLabelText("Expiry from"), { target: { value: "2026-05-01" } });
        expect(onChange).toHaveBeenLastCalledWith({ from: "2026-05-01", to: "2026-06-01" });
        onChange.mockClear();
        fireEvent.change(screen.getByLabelText("Expiry from"), { target: { value: "2026-07-01" } });
        expect(onChange).not.toHaveBeenCalled();
        fireEvent.change(screen.getByLabelText("Expiry to"), { target: { value: "" } });
        expect(onChange).toHaveBeenLastCalledWith({});
        await userEvent.click(screen.getByRole("button", { name: "Year" }));
        expect(onChange).toHaveBeenLastCalledWith({ from: "2026-01-01", to: "2026-12-31" });
        rerender(<DateRangePicker label="Expiry" value={{ from: "2026-01-01", to: "2026-12-31" }} onChange={onChange} presets={presets} />);
        expect(screen.getByRole("button", { name: "Year" })).toHaveAttribute("aria-pressed", "true");
    });

    it("ActivityTimeline keeps order and handles loading/empty/error", async () => {
        const items = [
            { id: 1, at: "2026-03-02T10:00:00Z", action: "Second" },
            { id: 2, at: "2026-03-01T10:00:00Z", action: "First", actor: "sam" },
        ];
        const { rerender } = render(<ActivityTimeline items={items} state={{ status: "success" }} />);
        const li = screen.getAllByRole("listitem");
        expect(li[0]).toHaveTextContent("Second");
        expect(li[1]).toHaveTextContent("First");
        rerender(<ActivityTimeline items={[]} state={{ status: "success" }} emptyLabel="Nothing" />);
        expect(screen.getByRole("status")).toHaveTextContent("Nothing");
        rerender(<ActivityTimeline items={[]} state={{ status: "loading" }} />);
        expect(screen.getByRole("status", { name: "Loading activity" })).toBeInTheDocument();
        const onRetry = vi.fn();
        rerender(<ActivityTimeline items={[]} state={{ status: "error", error: new Error("boom") }} onRetry={onRetry} />);
        await userEvent.click(screen.getByRole("button", { name: "Retry" }));
        expect(onRetry).toHaveBeenCalled();
    });
});

describe("QueryBoundary", () => {
    const base = { data: undefined as { name: string } | undefined, isPending: false, isError: false, error: null as unknown, refetch: vi.fn() };

    it("shows a labelled skeleton while pending", () => {
        const { container } = render(
            <QueryBoundary query={{ ...base, isPending: true }} rows={2} loadingLabel="Loading thing" errorTitle="Could not load thing">
                {(d) => <p>{d.name}</p>}
            </QueryBoundary>,
        );
        expect(screen.getByRole("status", { name: "Loading thing" })).toBeInTheDocument();
        expect(container.querySelectorAll("[data-slot='skeleton']").length).toBe(2);
    });

    it("shows the error title and retries via refetch", async () => {
        const refetch = vi.fn();
        render(
            <QueryBoundary query={{ ...base, isError: true, error: new Error("boom"), refetch }} loadingLabel="Loading thing" errorTitle="Could not load thing">
                {(d) => <p>{d.name}</p>}
            </QueryBoundary>,
        );
        expect(screen.getByText("Could not load thing")).toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: "Retry" }));
        expect(refetch).toHaveBeenCalledTimes(1);
    });

    it("treats settled-without-data as an error", () => {
        render(
            <QueryBoundary query={base} loadingLabel="Loading thing" errorTitle="Could not load thing">
                {(d) => <p>{d.name}</p>}
            </QueryBoundary>,
        );
        expect(screen.getByText("Could not load thing")).toBeInTheDocument();
    });

    it("renders children with the data", () => {
        render(
            <QueryBoundary query={{ ...base, data: { name: "Loaded value" } }} loadingLabel="Loading thing" errorTitle="Could not load thing">
                {(d) => <p>{d.name}</p>}
            </QueryBoundary>,
        );
        expect(screen.getByText("Loaded value")).toBeInTheDocument();
        expect(screen.queryByRole("status")).toBeNull();
    });
});
