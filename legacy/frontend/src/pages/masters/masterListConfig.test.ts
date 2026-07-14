import { describe, it, expect } from "vitest";
import { getDefaultFilters } from "./masterListConfig";

describe("getDefaultFilters", () => {
  it("allotments default to AT / non-BOE / all", () => {
    expect(getDefaultFilters("allotments")).toEqual({
      type: "AT",
      is_boe: "False",
      is_allotted: "all",
    });
  });

  it("bill-of-entries default to un-invoiced", () => {
    expect(getDefaultFilters("bill-of-entries")).toEqual({ is_invoice: "False" });
  });

  it("incentive-licenses default to all sold statuses", () => {
    expect(getDefaultFilters("incentive-licenses")).toEqual({ sold_status: "" });
  });

  it("unknown entities get no default filters", () => {
    expect(getDefaultFilters("companies")).toEqual({});
    expect(getDefaultFilters("licenses")).toEqual({});
    expect(getDefaultFilters("")).toEqual({});
  });
});
