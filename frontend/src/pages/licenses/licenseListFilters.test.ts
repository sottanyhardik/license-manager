import { describe, expect, it } from "vitest";
import {
  activeFilterChips,
  baselineFilters,
  countNonBaselineFilters,
  createBaselineState,
  normaliseDecimal,
  normaliseIsoDate,
  parseLicenseListSearch,
  serializeLicenseListSearch,
  toApiParams,
  toFilterApiParams,
  validateLicenseListFilters,
  withFilters,
  type LicenseListState,
} from "./licenseListFilters";

const labelFor = (field: string, value: string) => `${field}:${value}`;

function stateFrom(search: string): LicenseListState {
  return parseLicenseListSearch(search).state;
}

describe("parseLicenseListSearch", () => {
  it("defaults an empty URL to the baseline view with no warnings", () => {
    const result = parseLicenseListSearch("");
    expect(result.warnings).toEqual([]);
    expect(result.state).toEqual(createBaselineState());
    expect(result.state.filters.is_expired).toBe("False");
    expect(result.state.filters.flags__is_null).toBe("False");
    expect(result.state.filters.is_planned).toBe("all");
  });

  it("falls back to page 1 for malformed page values and reports them", () => {
    for (const raw of ["abc", "0", "-3", "2.5", "99999999"]) {
      const result = parseLicenseListSearch(`page=${raw}`);
      expect(result.state.page).toBe(1);
      expect(result.warnings.length).toBeGreaterThan(0);
    }
    expect(stateFrom("page=7").page).toBe(7);
  });

  it("allows only 10/25/50/100/200 for page_size and defaults the rest to 25", () => {
    expect(stateFrom("page_size=50").pageSize).toBe(50);
    const bad = parseLicenseListSearch("page_size=17");
    expect(bad.state.pageSize).toBe(25);
    expect(bad.warnings).toHaveLength(1);
    expect(parseLicenseListSearch("page_size=huge").state.pageSize).toBe(25);
  });

  it("maps unknown tri-state values to the default and accepts case variants", () => {
    const bad = parseLicenseListSearch("is_expired=maybe&flags__is_null=sometimes&is_planned=2");
    expect(bad.state.filters.is_expired).toBe("False");
    expect(bad.state.filters.flags__is_null).toBe("False");
    expect(bad.state.filters.is_planned).toBe("all");
    expect(bad.warnings).toHaveLength(3);

    const cased = stateFrom("is_expired=true&flags__is_null=ALL&is_planned=false");
    expect(cased.filters.is_expired).toBe("True");
    expect(cased.filters.flags__is_null).toBe("all");
    expect(cased.filters.is_planned).toBe("False");
  });

  it("turns id CSVs into sorted unique positive ints and drops the rest with a warning", () => {
    const result = parseLicenseListSearch("exporter=3,1,3,abc,-2,0&exporter=2");
    expect(result.state.filters.exporter).toEqual([1, 2, 3]);
    expect(result.warnings).toHaveLength(3);
  });

  it("sorts and de-duplicates code CSVs for scheme and notification filters", () => {
    const result = stateFrom("scheme_code=DFIA,AB,DFIA&notification_number=99/2024,10/2023");
    expect(result.filters.scheme_code).toEqual(["AB", "DFIA"]);
    expect(result.filters.notification_number).toEqual(["10/2023", "99/2024"]);
  });

  it("rejects impossible calendar dates and keeps valid YYYY-MM-DD values", () => {
    const bad = parseLicenseListSearch("license_date__gte=2026-02-30&license_expiry_date__lte=2026-04-01");
    expect(bad.state.filters.license_date__gte).toBe("");
    expect(bad.state.filters.license_expiry_date__lte).toBe("2026-04-01");
    expect(bad.warnings).toHaveLength(1);
    expect(normaliseIsoDate("2024-02-29")).toBe("2024-02-29");
    expect(normaliseIsoDate("2023-02-29")).toBeNull();
    expect(normaliseIsoDate("01-04-2026")).toBeNull();
  });

  it("validates decimals to at most 2 dp and normalises them", () => {
    expect(stateFrom("balance__balance_cif_min=500.00&balance__balance_cif_max=1000.50").filters).toMatchObject({
      balance__balance_cif_min: "500",
      balance__balance_cif_max: "1000.5",
    });
    const bad = parseLicenseListSearch("balance__balance_cif_min=1.234&balance__balance_cif_max=abc");
    expect(bad.state.filters.balance__balance_cif_min).toBe("");
    expect(bad.state.filters.balance__balance_cif_max).toBe("");
    expect(bad.warnings).toHaveLength(2);
    expect(normaliseDecimal("-0")).toBe("0");
    expect(normaliseDecimal("007.10")).toBe("7.1");
    expect(normaliseDecimal("1e5")).toBeNull();
  });

  it("truncates an overlong search to 200 characters with a warning-free trim", () => {
    const long = "x".repeat(250);
    expect(stateFrom(`search=${long}`).filters.search).toHaveLength(200);
    expect(stateFrom("search=%20%200310835340%20").filters.search).toBe("0310835340");
  });

  it("reads legacy _from/_to date keys and prefers the canonical key when both exist", () => {
    const legacy = stateFrom(
      "license_date_from=2026-01-01&license_date_to=2026-02-01&license_expiry_date_from=2027-01-01&license_expiry_date_to=2027-02-01",
    );
    expect(legacy.filters.license_date__gte).toBe("2026-01-01");
    expect(legacy.filters.license_date__lte).toBe("2026-02-01");
    expect(legacy.filters.license_expiry_date__gte).toBe("2027-01-01");
    expect(legacy.filters.license_expiry_date__lte).toBe("2027-02-01");

    const both = stateFrom("license_date__gte=2026-03-01&license_date_from=2026-01-01");
    expect(both.filters.license_date__gte).toBe("2026-03-01");
  });

  it("never throws on hostile input", () => {
    expect(() => parseLicenseListSearch("%E0%A4%A&page=%ZZ&exporter=%00")).not.toThrow();
  });
});

describe("serializeLicenseListSearch", () => {
  it("always writes is_expired and flags__is_null, and writes page and page_size", () => {
    const query = serializeLicenseListSearch(createBaselineState());
    expect(query).toContain("is_expired=False");
    expect(query).toContain("flags__is_null=False");
    expect(query).toContain("page=1");
    expect(query).toContain("page_size=25");
    expect(query).not.toContain("is_planned");
  });

  it("writes is_planned only when it is not 'all'", () => {
    const planned = withFilters(createBaselineState(), { is_planned: "True" });
    expect(serializeLicenseListSearch(planned)).toContain("is_planned=True");
  });

  it("is deterministic: the same values in a different insertion order give the same string", () => {
    const base = createBaselineState();
    const a = withFilters(base, { exporter: [3, 1, 2], scheme_code: ["ZZ", "AA"] });
    const b = withFilters(base, { exporter: [2, 3, 1], scheme_code: ["AA", "ZZ"] });
    expect(serializeLicenseListSearch(a)).toBe(serializeLicenseListSearch(b));
    expect(serializeLicenseListSearch(a)).toContain("exporter=1,2,3");
  });

  it("uses a fixed key order regardless of how the URL was written", () => {
    const fromUrl = serializeLicenseListSearch(stateFrom("page=2&port=5&search=abc&exporter=1"));
    expect(fromUrl.indexOf("search=")).toBeLessThan(fromUrl.indexOf("exporter="));
    expect(fromUrl.indexOf("exporter=")).toBeLessThan(fromUrl.indexOf("port="));
    expect(fromUrl.indexOf("port=")).toBeLessThan(fromUrl.indexOf("is_expired="));
    expect(fromUrl.endsWith("page=2&page_size=25")).toBe(true);
  });

  it("round-trips: parse(serialize(state)) serialises to the same string", () => {
    const state = stateFrom(
      "search=Acme%20Ltd&exporter=9,2&exclude_port=4&purchase_status=11,10,1&scheme_code=DFIA&is_expired=all&flags__is_null=True&is_planned=False&license_date__gte=2026-04-01&license_expiry_date__lte=2030-12-31&balance__balance_cif_min=500&balance__balance_cif_max=999.99&page=3&page_size=100",
    );
    const once = serializeLicenseListSearch(state);
    expect(serializeLicenseListSearch(parseLicenseListSearch(once).state)).toBe(once);
    expect(parseLicenseListSearch(once).warnings).toEqual([]);
  });

  it("keeps commas literal so CSV values stay readable", () => {
    expect(serializeLicenseListSearch(stateFrom("purchase_status=11,10"))).toContain("purchase_status=10,11");
  });
});

describe("toApiParams", () => {
  it("sends explicit baseline values and paging for the default view", () => {
    expect(toApiParams(createBaselineState())).toEqual({
      is_expired: "False",
      flags__is_null: "False",
      page: 1,
      page_size: 25,
    });
  });

  it("omits is_planned when it is 'all' and sends it otherwise", () => {
    expect(toApiParams(createBaselineState())).not.toHaveProperty("is_planned");
    expect(toApiParams(withFilters(createBaselineState(), { is_planned: "False" }))).toMatchObject({
      is_planned: "False",
    });
  });

  it("sends a 10-digit search as license_number and drops search", () => {
    const params = toApiParams(withFilters(createBaselineState(), { search: "0310835340" }));
    expect(params.license_number).toBe("0310835340");
    expect(params).not.toHaveProperty("search");
    expect(toApiParams(withFilters(createBaselineState(), { search: "acme" }))).toMatchObject({ search: "acme" });
  });

  it("sends codes for scheme and notification filters and ids for the rest", () => {
    const params = toApiParams(
      withFilters(createBaselineState(), {
        scheme_code: ["DFIA", "AB"],
        notification_number: ["10/2023"],
        exporter: [2, 1],
        exclude_port: [7],
      }),
    );
    expect(params).toMatchObject({
      scheme_code: "AB,DFIA",
      notification_number: "10/2023",
      exporter: "1,2",
      exclude_port: "7",
    });
  });

  it("uses API names for every date and decimal bound", () => {
    const params = toApiParams(
      withFilters(createBaselineState(), {
        license_date__gte: "2026-04-01",
        license_expiry_date__lte: "2030-01-31",
        balance__balance_cif_min: "200",
        balance__balance_cif_max: "1000.5",
      }),
    );
    expect(params).toMatchObject({
      license_date__gte: "2026-04-01",
      license_expiry_date__lte: "2030-01-31",
      balance__balance_cif_min: "200",
      balance__balance_cif_max: "1000.5",
    });
  });

  it("toFilterApiParams omits paging (used by exports)", () => {
    const params = toFilterApiParams(createBaselineState());
    expect(params).not.toHaveProperty("page");
    expect(params).not.toHaveProperty("page_size");
    expect(params).toMatchObject({ is_expired: "False", flags__is_null: "False" });
  });
});

describe("validateLicenseListFilters", () => {
  it("is clean for the baseline", () => {
    expect(validateLicenseListFilters(baselineFilters())).toEqual({});
  });

  it("flags a licence date range where from is after to", () => {
    const errors = validateLicenseListFilters({
      ...baselineFilters(),
      license_date__gte: "2026-05-01",
      license_date__lte: "2026-04-01",
    });
    expect(errors.license_date).toBeDefined();
  });

  it("flags an expiry date range where from is after to", () => {
    const errors = validateLicenseListFilters({
      ...baselineFilters(),
      license_expiry_date__gte: "2031-01-01",
      license_expiry_date__lte: "2030-01-01",
    });
    expect(errors.license_expiry_date).toBeDefined();
  });

  it("accepts equal from and to dates (inclusive bounds)", () => {
    const errors = validateLicenseListFilters({
      ...baselineFilters(),
      license_date__gte: "2026-04-01",
      license_date__lte: "2026-04-01",
    });
    expect(errors).toEqual({});
  });

  it("flags balance min greater than max", () => {
    const errors = validateLicenseListFilters({
      ...baselineFilters(),
      balance__balance_cif_min: "500",
      balance__balance_cif_max: "100.5",
    });
    expect(errors.balance__balance_cif).toBeDefined();
  });

  it("flags malformed decimals and dates that reached the state", () => {
    const errors = validateLicenseListFilters({
      ...baselineFilters(),
      balance__balance_cif_min: "1.999",
      license_date__gte: "2026-13-01",
    });
    expect(errors.balance__balance_cif_min).toBeDefined();
    expect(errors.license_date__gte).toBeDefined();
  });

  it("flags the same id in an include and an exclude filter", () => {
    const errors = validateLicenseListFilters({
      ...baselineFilters(),
      exporter: [4, 5],
      exclude_exporter: [5],
      port: [1],
      exclude_port: [1],
    });
    expect(errors.exporter).toBeDefined();
    expect(errors.port).toBeDefined();
  });
});

describe("activeFilterChips", () => {
  it("produces no chips for the baseline and a count of zero", () => {
    const state = createBaselineState();
    expect(activeFilterChips(state, labelFor)).toEqual([]);
    expect(countNonBaselineFilters(state)).toBe(0);
  });

  it("produces one chip per multi-select value, each with its own label", () => {
    const state = stateFrom("purchase_status=11,10,1");
    const chips = activeFilterChips(state, labelFor);
    expect(chips.map((chip) => chip.label)).toEqual([
      "Purchase status: purchase_status:1",
      "Purchase status: purchase_status:10",
      "Purchase status: purchase_status:11",
    ]);
    expect(countNonBaselineFilters(state)).toBe(3);
  });

  it("removes exactly one value and resets page to 1", () => {
    const state = stateFrom("purchase_status=11,10,1&page=4");
    const chips = activeFilterChips(state, labelFor);
    const next = chips[1].remove(state);
    expect(next.filters.purchase_status).toEqual([1, 11]);
    expect(next.page).toBe(1);
    expect(activeFilterChips(next, labelFor)).toHaveLength(2);
  });

  it("uses one chip per date bound with distinct wording", () => {
    const state = stateFrom("license_date__gte=2026-04-01&license_date__lte=2026-06-30");
    const labels = activeFilterChips(state, labelFor).map((chip) => chip.label);
    expect(labels).toEqual(["Licence date from 01-04-2026", "Licence date to 30-06-2026"]);
  });

  it("describes numeric bounds with the rupee symbol and comparison", () => {
    const labels = activeFilterChips(stateFrom("balance__balance_cif_min=500&balance__balance_cif_max=1000"), labelFor).map(
      (chip) => chip.label,
    );
    expect(labels).toEqual(["Balance ≥ ₹500", "Balance ≤ ₹1000"]);
  });

  it("shows non-baseline segmented values and removes them back to the baseline", () => {
    const state = stateFrom("is_expired=all&flags__is_null=True&is_planned=True");
    const chips = activeFilterChips(state, labelFor);
    expect(chips.map((chip) => chip.label)).toEqual([
      "Licence status: All",
      "Flags is null: Yes",
      "Is planned: Yes",
    ]);
    const cleared = chips.reduce((current, chip) => chip.remove(current), state);
    expect(cleared.filters.is_expired).toBe("False");
    expect(cleared.filters.flags__is_null).toBe("False");
    expect(cleared.filters.is_planned).toBe("all");
    expect(activeFilterChips(cleared, labelFor)).toEqual([]);
  });

  it("counts search as one non-baseline filter", () => {
    expect(countNonBaselineFilters(stateFrom("search=acme"))).toBe(1);
  });
});
