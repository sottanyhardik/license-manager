import { describe, expect, it } from "vitest";
import {
  compareDecimal,
  csvCell,
  matchesSearch,
  paginate,
  sortRows,
  toCsv,
  withinDateRange,
  type DrawerColumn,
} from "./drilldownModel";

interface Row {
  boe: string;
  date: string | null;
  cif: string | null;
}

const columns: DrawerColumn<Row>[] = [
  { key: "boe", label: "BOE no.", type: "text", value: (r) => r.boe },
  { key: "date", label: "Date", type: "date", value: (r) => r.date },
  { key: "cif", label: "CIF", type: "decimal", align: "right", value: (r) => r.cif },
];

const rows: Row[] = [
  { boe: "B10", date: "2026-03-10", cif: "300.00" },
  { boe: "B2", date: null, cif: "-40.50" },
  { boe: "B9", date: "2026-01-01", cif: "1234.5" },
];

describe("compareDecimal", () => {
  it("compares by digits, not by float value", () => {
    expect(compareDecimal("1234.5", "300.00")).toBeGreaterThan(0);
    expect(compareDecimal("300.00", "300")).toBe(0);
    expect(compareDecimal("0.10", "0.1")).toBe(0);
    expect(compareDecimal("0.005", "0.01")).toBeLessThan(0);
  });

  it("orders negatives below positives and treats -0.00 as zero", () => {
    expect(compareDecimal("-40.50", "0.00")).toBeLessThan(0);
    expect(compareDecimal("-40.50", "-40.49")).toBeLessThan(0);
    expect(compareDecimal("-0.00", "0.00")).toBe(0);
  });

  it("sorts null after every value, whichever side it is on", () => {
    expect(compareDecimal(null, "1.00")).toBeGreaterThan(0);
    expect(compareDecimal("1.00", null)).toBeLessThan(0);
    expect(compareDecimal(null, null)).toBe(0);
  });
});

describe("matchesSearch", () => {
  it("needs every term, case-insensitively, anywhere in the row", () => {
    expect(matchesSearch(["4001", "Mundra", "PARTIALLY COVERED"], "mundra partial")).toBe(true);
    expect(matchesSearch(["4001", "Mundra"], "mundra nhava")).toBe(false);
  });

  it("matches everything for an empty query and ignores null terms", () => {
    expect(matchesSearch([null, "x"], "   ")).toBe(true);
    expect(matchesSearch([null, "x"], "x")).toBe(true);
  });
});

describe("withinDateRange", () => {
  it("includes both bounds", () => {
    expect(withinDateRange("2026-03-10", { from: "2026-03-10", to: "2026-03-10" })).toBe(true);
    expect(withinDateRange("2026-03-09", { from: "2026-03-10", to: "" })).toBe(false);
    expect(withinDateRange("2026-03-11", { from: "", to: "2026-03-10" })).toBe(false);
  });

  it("keeps undated rows only when no bound is set", () => {
    expect(withinDateRange(null, { from: "", to: "" })).toBe(true);
    expect(withinDateRange(null, { from: "2026-01-01", to: "" })).toBe(false);
  });
});

describe("sortRows", () => {
  it("sorts decimal columns by exact value, with negatives and nulls in the right place", () => {
    const asc = sortRows(rows, columns, { key: "cif", direction: "asc" }).map((r) => r.boe);
    expect(asc).toEqual(["B2", "B10", "B9"]);
    const desc = sortRows(rows, columns, { key: "cif", direction: "desc" }).map((r) => r.boe);
    expect(desc).toEqual(["B9", "B10", "B2"]);
  });

  it("sorts null dates last in either direction", () => {
    const asc = sortRows(rows, columns, { key: "date", direction: "asc" }).map((r) => r.boe);
    expect(asc).toEqual(["B9", "B10", "B2"]);
    const desc = sortRows(rows, columns, { key: "date", direction: "desc" }).map((r) => r.boe);
    expect(desc).toEqual(["B10", "B9", "B2"]);
  });

  it("returns the input order when there is no sort", () => {
    expect(sortRows(rows, columns, null)).toBe(rows);
  });

  it("does not mutate the input", () => {
    const copy = [...rows];
    sortRows(rows, columns, { key: "boe", direction: "asc" });
    expect(rows).toEqual(copy);
  });
});

describe("paginate", () => {
  const many = Array.from({ length: 7 }, (_, index) => index);

  it("returns the requested page", () => {
    expect(paginate(many, 2, 3)).toEqual({ rows: [3, 4, 5], page: 2, pageCount: 3 });
  });

  it("clamps a page beyond the end, so a filter that shrinks the list still shows rows", () => {
    expect(paginate(many, 9, 3)).toEqual({ rows: [6], page: 3, pageCount: 3 });
  });

  it("has one empty page when there are no rows", () => {
    expect(paginate([], 4, 25)).toEqual({ rows: [], page: 1, pageCount: 1 });
  });
});

describe("csvCell and toCsv", () => {
  it("quotes cells with commas, quotes or line breaks", () => {
    expect(csvCell('Customer "A", Ltd')).toBe('"Customer ""A"", Ltd"');
    expect(csvCell("line\nbreak")).toBe('"line\nbreak"');
  });

  it("guards text that a spreadsheet would read as a formula, but not negative numbers", () => {
    expect(csvCell("=SUM(A1)")).toBe("'=SUM(A1)");
    expect(csvCell("+1")).toBe("'+1");
    expect(csvCell("-40.50")).toBe("-40.50");
    expect(csvCell("-note")).toBe("'-note");
  });

  it("writes an empty cell for null and a header row first", () => {
    expect(csvCell(null)).toBe("");
    expect(toCsv(columns, rows)).toBe(
      ["BOE no.,Date,CIF", "B10,2026-03-10,300.00", "B2,,-40.50", "B9,2026-01-01,1234.5"].join("\r\n"),
    );
  });
});
