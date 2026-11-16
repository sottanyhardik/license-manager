import { describe, expect, it } from "vitest";
import { clampPageSize, normalizeList, parseListParams, toQuery, writeListParams, type ListParams } from "./listContract";
import { qk } from "./queryKeys";

const p: ListParams = { page: 2, pageSize: 50, search: "abc", ordering: "-date", filters: { status: ["a", "b"], date_from: "2024-01-01", empty: "" } };

describe("listContract", () => {
    it("clamps page size to 200", () => {
        expect(clampPageSize(500)).toBe(200);
        expect(clampPageSize(0)).toBe(25);
        expect(clampPageSize(500, 100)).toBe(100);
        expect(toQuery({ ...p, pageSize: 500 }).get("page_size")).toBe("200");
    });

    it("toQuery maps _from to __gte, comma-joins arrays (backend contract), drops empties", () => {
        const q = toQuery(p);
        expect(q.getAll("status")).toEqual(["a,b"]);
        expect(q.get("date__gte")).toBe("2024-01-01");
        expect(q.has("empty")).toBe(false);
    });

    it("array filters round-trip through the URL as a single comma-joined key", () => {
        const opts = { filterKeys: ["status"], multiKeys: ["status"] };
        const written = writeListParams(new URLSearchParams(), { ...p, filters: { status: ["1", "2"] } }, opts);
        expect(written.getAll("status")).toEqual(["1,2"]);
        expect(parseListParams(written, opts).filters.status).toEqual(["1", "2"]);
        // legacy repeated-key URLs still parse
        expect(parseListParams(new URLSearchParams("status=1&status=2"), opts).filters.status).toEqual(["1", "2"]);
    });

    it("keeps comma text in non-multi keys raw", () => {
        const opts = { filterKeys: ["company", "status"], multiKeys: ["status"] };
        const sp = new URLSearchParams({ company: "ACME, Ltd", status: "a,,b" });
        expect(parseListParams(sp, opts).filters).toEqual({ company: "ACME, Ltd", status: ["a", "b"] });
        expect(parseListParams(new URLSearchParams({ search: "ACME, Ltd" }), opts).search).toBe("ACME, Ltd");
    });

    it("normalizes the envelope variants identically", () => {
        const sent = { ...p, page: 1, pageSize: 25 };
        const std = normalizeList({ count: 60, next: "x", previous: null, page_size: 25, total_pages: 3, current_page: 1, results: [1] }, sent);
        const drf = normalizeList({ count: 60, next: "x", previous: null, results: [1] }, sent);
        const master = normalizeList({ count: 60, has_next: true, has_previous: false, results: [1] }, sent);
        for (const r of [std, drf, master]) {
            expect([r.count, r.totalPages, r.hasNext, r.hasPrevious]).toEqual([60, 3, true, false]);
        }
        expect(normalizeList([1, 2], sent).count).toBe(2);
    });

    it("URL round-trips, omits defaults, preserves unrelated params, isolates prefixes", () => {
        const opts = { filterKeys: ["status"], defaults: { ordering: "-id" } };
        const parsed = parseListParams(new URLSearchParams("page=3&page_size=999&status=x&tab=boes"), opts);
        expect(parsed).toMatchObject({ page: 3, pageSize: 200, ordering: "-id", filters: { status: "x" } });
        const written = writeListParams(new URLSearchParams("tab=boes"), { page: 1, pageSize: 25, ordering: "-id", filters: {} }, opts);
        expect(written.toString()).toBe("tab=boes");
        const a = writeListParams(new URLSearchParams(), { ...p, filters: {} }, { filterKeys: [], urlPrefix: "a_" });
        const both = writeListParams(a, { ...p, page: 4, filters: {} }, { filterKeys: [], urlPrefix: "b_" });
        expect(both.get("a_page")).toBe("2");
        expect(both.get("b_page")).toBe("4");
    });
});

describe("qk", () => {
    it("produces stable, structurally equal keys", () => {
        expect(qk.licenses.list(p)).toEqual(qk.licenses.list({ ...p }));
        expect(qk.licenses.detail(5)).toEqual(["licenses", "detail", 5]);
        expect(qk.licenses.overview(5, "boes")).toEqual(["licenses", "detail", 5, "overview", "boes"]);
        expect(qk.boes.all).toEqual(["boes"]);
        expect(qk.masters("item").list(p)[0]).toBe("masters:item");
        // list/detail share the resource prefix so invalidate(all) hits both
        expect(qk.trades.list(p).slice(0, 1)).toEqual(qk.trades.detail(1).slice(0, 1));
    });
});
