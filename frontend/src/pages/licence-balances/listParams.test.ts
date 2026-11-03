import { describe, expect, it } from "vitest";
import { DEFAULT_PAGE_SIZE, parseListParams, serializeListParams, toApiParams } from "./listParams";

describe("parseListParams", () => {
  it("applies defaults for an empty URL", () => {
    expect(parseListParams(new URLSearchParams(""))).toEqual({
      search: "",
      expiry: "all",
      page: 1,
      pageSize: DEFAULT_PAGE_SIZE,
    });
  });

  it("normalises invalid values to safe defaults", () => {
    const parsed = parseListParams(new URLSearchParams("page=abc&page_size=7&expiry=bogus"));
    expect(parsed).toEqual({ search: "", expiry: "all", page: 1, pageSize: DEFAULT_PAGE_SIZE });
    expect(parseListParams(new URLSearchParams("page=-3")).page).toBe(1);
    expect(parseListParams(new URLSearchParams("page=2.5")).page).toBe(1);
  });

  it("accepts the supported page sizes and expiry filters", () => {
    expect(parseListParams(new URLSearchParams("page_size=100&expiry=expired"))).toMatchObject({
      pageSize: 100,
      expiry: "expired",
    });
  });

  it("trims the search text", () => {
    expect(parseListParams(new URLSearchParams("search=%20acme%20")).search).toBe("acme");
  });
});

describe("serializeListParams", () => {
  it("omits default values so the canonical URL stays short", () => {
    expect(serializeListParams({ search: "", expiry: "all", page: 1, pageSize: 25 }).toString()).toBe("");
  });

  it("round-trips non-default state", () => {
    const state = { search: "acme", expiry: "active" as const, page: 3, pageSize: 50 as const };
    const query = serializeListParams(state).toString();
    expect(parseListParams(new URLSearchParams(query))).toEqual(state);
  });
});

describe("toApiParams", () => {
  it("sends explicit paging and expiry, and omits an empty search", () => {
    expect(toApiParams({ search: "", expiry: "all", page: 2, pageSize: 25 })).toEqual({
      page: 2,
      page_size: 25,
      expiry: "all",
    });
    expect(toApiParams({ search: "acme", expiry: "all", page: 1, pageSize: 100 })).toMatchObject({ search: "acme" });
  });
});
