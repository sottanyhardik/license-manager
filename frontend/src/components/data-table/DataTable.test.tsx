import { useEffect, useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ColumnDef, SortingState, RowSelectionState } from "@tanstack/react-table";
import { DataTable } from "./DataTable";
import { ExpandableDataTable } from "./ExpandableDataTable";
import { nextSorting, sortingToOrdering, orderingToSorting } from "./helpers";
import { useExpandedParam } from "./useExpandedParam";

interface Row { id: number; name: string; amount: string }
const rows: Row[] = [{ id: 1, name: "Alpha", amount: "1,00,000.00" }, { id: 2, name: "Beta", amount: "2,50.00" }];
const columns: ColumnDef<Row, unknown>[] = [
    { id: "name", accessorKey: "name", header: "Name" },
    // caller-supplied renderer: DataTable must show the string verbatim
    { id: "amount", accessorKey: "amount", header: "Amount", meta: { numeric: true }, cell: (c) => c.row.original.amount },
];
const base = { columns, data: rows, getRowId: (r: Row) => String(r.id), caption: "Test table" };

describe("DataTable", () => {
    it("renders caller-formatted values untouched", () => {
        render(<DataTable {...base} state={{ status: "success" }} />);
        expect(screen.getByText("1,00,000.00")).toBeInTheDocument();
        expect(screen.getByText("1,00,000.00")).toHaveClass("tabular-nums");
    });

    it("cycles sort asc -> desc -> none, emits it and updates aria-sort", async () => {
        const user = userEvent.setup();
        const seen: SortingState[] = [];
        function Harness() {
            const [value, setValue] = useState<SortingState>([]);
            return <DataTable {...base} state={{ status: "success" }} sorting={{ value, onChange: (s) => { seen.push(s); setValue(s); } }} />;
        }
        render(<Harness />);
        const th = screen.getByRole("columnheader", { name: /Name/ });
        expect(th).toHaveAttribute("aria-sort", "none");
        await user.click(within(th).getByRole("button"));
        expect(th).toHaveAttribute("aria-sort", "ascending");
        await user.click(within(th).getByRole("button"));
        expect(th).toHaveAttribute("aria-sort", "descending");
        await user.click(within(th).getByRole("button"));
        expect(th).toHaveAttribute("aria-sort", "none");
        expect(seen.map(sortingToOrdering)).toEqual(["name", "-name", undefined]);
    });

    it("has no sort controls without a sorting prop", () => {
        render(<DataTable {...base} state={{ status: "success" }} />);
        expect(screen.getByRole("columnheader", { name: "Name" })).not.toHaveAttribute("aria-sort");
    });

    it("ordering helpers round-trip", () => {
        expect(orderingToSorting("-name")).toEqual([{ id: "name", desc: true }]);
        expect(nextSorting([], "x")).toEqual([{ id: "x", desc: false }]);
    });

    it("loading state shows skeleton rows and aria-busy", () => {
        render(<DataTable {...base} data={[]} state={{ status: "loading" }} />);
        expect(screen.getAllByTestId("dt-skeleton-row").length).toBeGreaterThan(0);
        expect(screen.getByRole("table")).toHaveAttribute("aria-busy", "true");
    });

    it("error state announces and retries", async () => {
        const onRetry = vi.fn();
        render(<DataTable {...base} data={[]} state={{ status: "error", error: new Error("boom") }} onRetry={onRetry} />);
        expect(screen.getByRole("alert")).toHaveTextContent("boom");
        await userEvent.click(screen.getByRole("button", { name: "Retry" }));
        expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it("empty state shows title, description and action", () => {
        render(<DataTable {...base} data={[]} state={{ status: "success" }} empty={{ title: "Nothing here", description: "Try again", action: <button>Add</button> }} />);
        expect(screen.getByTestId("dt-empty")).toHaveTextContent("Nothing here");
        expect(screen.getByText("Try again")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
    });

    it("selects all on page and passes ids to bulk actions", async () => {
        const user = userEvent.setup();
        function Harness() {
            const [value, setValue] = useState<RowSelectionState>({});
            return <DataTable {...base} state={{ status: "success" }} selection={{ value, onChange: setValue, bulkActions: (ids) => <span data-testid="bulk">{ids.join(",")}</span> }} />;
        }
        render(<Harness />);
        await user.click(screen.getByRole("checkbox", { name: "Select all on page" }));
        expect(screen.getByTestId("bulk")).toHaveTextContent("1,2");
        await user.click(screen.getByRole("checkbox", { name: "Select row 1" }));
        expect(screen.getByTestId("bulk")).toHaveTextContent("2");
    });
});

describe("ExpandableDataTable", () => {
    const Panel = ({ r, onUnmount }: { r: Row; onUnmount: (id: number) => void }) => {
        useEffect(() => () => onUnmount(r.id), [r.id, onUnmount]);
        return <div>Content of {r.name}</div>;
    };

    it("shows only the newly expanded row content and unmounts the previous one", async () => {
        const user = userEvent.setup();
                const unmounts: number[] = [];
        const onUnmount = (i: number) => { unmounts.push(i); };
        render(
            <ExpandableDataTable<Row>
                {...base}
                state={{ status: "success" }}
                renderExpanded={(r) => <Panel r={r} onUnmount={onUnmount} />}
            />,
        );
        expect(screen.queryByText(/Content of/)).not.toBeInTheDocument(); // lazy
        await user.click(screen.getByRole("button", { name: "Expand Row 1" }));
        expect(screen.getByText("Content of Alpha")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Expand Row 2" }));
        expect(screen.queryByText("Content of Alpha")).not.toBeInTheDocument();
        expect(screen.getByText("Content of Beta")).toBeInTheDocument();
        expect(unmounts).toContain(1);
        await user.click(screen.getByRole("button", { name: "Collapse Row 2" }));
        expect(screen.queryByText(/Content of/)).not.toBeInTheDocument();
        expect(unmounts).toContain(2);
    });

    it("expand toggle is keyboard operable with correct aria wiring", async () => {
        const user = userEvent.setup();
        render(<ExpandableDataTable<Row> {...base} state={{ status: "success" }} renderExpanded={(r) => <div>Content of {r.name}</div>} />);
        await user.tab();
        const btn = screen.getByRole("button", { name: "Expand Row 1" });
        expect(btn).toHaveFocus();
        expect(btn).toHaveAttribute("aria-expanded", "false");
        await user.keyboard("{Enter}");
        const open = screen.getByRole("button", { name: "Collapse Row 1" });
        expect(open).toHaveAttribute("aria-expanded", "true");
        const region = screen.getByRole("region", { name: "Details for Row 1" });
        expect(open.getAttribute("aria-controls")).toBe(region.id);
        await user.keyboard(" ");
        expect(screen.queryByRole("region")).not.toBeInTheDocument();
    });

    it("supports controlled expandedId and URL sync via useExpandedParam", async () => {
        const user = userEvent.setup();
        function Harness() {
            const [id, setId] = useExpandedParam();
            return (
                <>
                    <span data-testid="id">{String(id)}</span>
                    <ExpandableDataTable<Row> {...base} state={{ status: "success" }} expandedId={id} onExpandedChange={setId} renderExpanded={(r) => <div>Content of {r.name}</div>} />
                </>
            );
        }
        render(<MemoryRouter initialEntries={["/x?expanded=2&tab=a"]}><Harness /></MemoryRouter>);
        expect(screen.getByText("Content of Beta")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Expand Row 1" }));
        expect(screen.getByTestId("id")).toHaveTextContent("1");
        expect(screen.queryByText("Content of Beta")).not.toBeInTheDocument();
    });
});
