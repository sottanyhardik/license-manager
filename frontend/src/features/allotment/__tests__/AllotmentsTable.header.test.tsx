import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";

vi.mock("@/api/axios", () => ({
    default: { get: vi.fn(() => new Promise(() => {})), post: vi.fn(() => Promise.resolve({ data: { id: 999 } })) },
}));
vi.mock("../../../api/axios", () => ({
    default: { get: vi.fn(() => new Promise(() => {})), post: vi.fn(() => Promise.resolve({ data: { id: 999 } })) },
}));

import AllotmentsTable from "@/pages/masters/tables/AllotmentsTable";
import { ALLOTMENT_FIXTURES } from "./fixtures";

/**
 * Header-parity proof. The snapshot in __snapshots__ was generated against the
 * ORIGINAL AllotmentsTable (git HEAD, before the DetailTabs change) and must
 * stay byte-identical: every card's markup outside `.entity-card-detail`
 * (title, chips, badges, body, summary, actions, View/Hide button), for both
 * roles and both expanded states, plus the navigate target of every
 * navigating action.
 */
function wrap(ui: ReactElement) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function headerMarkup(container: HTMLElement): string[] {
    return Array.from(container.querySelectorAll("article")).map((article) => {
        const clone = article.cloneNode(true) as HTMLElement;
        clone.querySelectorAll(".entity-card-detail").forEach((n) => n.remove());
        return clone.outerHTML;
    });
}

function renderTable(canWrite: boolean, expanded: Set<number>, navigate = vi.fn()) {
    return wrap(
        <AllotmentsTable
            loading={false}
            data={ALLOTMENT_FIXTURES}
            canWrite={canWrite}
            entityName="allotments"
            filterParams={{ is_boe: "all" }}
            currentPage={2}
            pageSize={25}
            navigate={navigate}
            onDelete={vi.fn()}
            expandedAllotments={expanded}
            toggleAllotment={vi.fn()}
        />,
    );
}

describe("AllotmentsTable card header parity", () => {
    beforeEach(() => {
        cleanup();
        sessionStorage.clear();
    });

    for (const canWrite of [true, false]) {
        it(`collapsed headers are unchanged (canWrite=${canWrite})`, () => {
            const { container } = renderTable(canWrite, new Set());
            expect(headerMarkup(container)).toMatchSnapshot();
        });

        it(`expanded-card headers are unchanged (canWrite=${canWrite})`, () => {
            const { container } = renderTable(canWrite, new Set([ALLOTMENT_FIXTURES[1].id]));
            expect(headerMarkup(container)).toMatchSnapshot();
        });

        it(`actions per role and navigate targets are unchanged (canWrite=${canWrite})`, () => {
            const navigate = vi.fn();
            const { container } = renderTable(canWrite, new Set(), navigate);
            const perCard = Array.from(container.querySelectorAll("article")).map((article) => {
                const titles = Array.from(article.querySelectorAll(".entity-card-actions button")).map(
                    (b) => b.getAttribute("title"),
                );
                const targets: unknown[] = [];
                for (const t of ["Edit", "Allocate"]) {
                    const btn = article.querySelector<HTMLButtonElement>(`.entity-card-actions button[title="${t}"]`);
                    if (!btn) continue;
                    navigate.mockClear();
                    fireEvent.click(btn);
                    targets.push([t, navigate.mock.calls]);
                }
                return { titles, targets };
            });
            const persisted = JSON.parse(sessionStorage.getItem("filterState_allotments") ?? "null");
            expect({ perCard, persisted: persisted && { filters: persisted.filters, pagination: persisted.pagination, search: persisted.search } }).toMatchSnapshot();
        });
    }
});
