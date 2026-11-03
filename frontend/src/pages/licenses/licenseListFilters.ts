/**
 * Licence list — pure filter model.
 *
 * The URL is the single source of truth for filters, page and page size
 * (docs/09-module-implementation/licence-listing.md §12). This module has no
 * React, router or network code: parse, serialise, validate, chips and the
 * API-param mapping live here so they can be unit-tested in isolation.
 *
 * `toApiParams` / `toFilterApiParams` are the ONLY place where backend query
 * names are produced for this page.
 */

export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 200] as const;
export type LicenseListPageSize = (typeof PAGE_SIZE_OPTIONS)[number];
export const DEFAULT_PAGE_SIZE: LicenseListPageSize = 25;
export const SEARCH_MAX_LENGTH = 200;
const CODE_MAX_LENGTH = 50;
const DECIMAL_MAX_INTEGER_DIGITS = 12;
const MAX_DB_ID = 2147483647;

/** A 10-digit search is an identity lookup and is sent as `license_number`. */
const LICENSE_NUMBER_PATTERN = /^\d{10}$/;

export type TriState = "all" | "True" | "False";

export type IdMultiField =
  | "exporter"
  | "exclude_exporter"
  | "port"
  | "exclude_port"
  | "purchase_status"
  | "export_license__norm_class";

export type CodeMultiField = "scheme_code" | "notification_number";

export type MultiField = IdMultiField | CodeMultiField;

export type DateField =
  | "license_date__gte"
  | "license_date__lte"
  | "license_expiry_date__gte"
  | "license_expiry_date__lte";

export type DecimalField = "balance__balance_cif_min" | "balance__balance_cif_max";

export interface LicenseListFilters {
  search: string;
  exporter: number[];
  exclude_exporter: number[];
  port: number[];
  exclude_port: number[];
  purchase_status: number[];
  export_license__norm_class: number[];
  scheme_code: string[];
  notification_number: string[];
  is_expired: TriState;
  flags__is_null: TriState;
  is_planned: TriState;
  license_date__gte: string;
  license_date__lte: string;
  license_expiry_date__gte: string;
  license_expiry_date__lte: string;
  balance__balance_cif_min: string;
  balance__balance_cif_max: string;
}

export interface LicenseListState {
  filters: LicenseListFilters;
  page: number;
  pageSize: LicenseListPageSize;
}

export interface LicenseListParseResult {
  state: LicenseListState;
  /** Human-readable notes about URL values that were dropped or defaulted. */
  warnings: string[];
}

/** Field-level validation messages. Keys are the field a message belongs to. */
export type LicenseFilterErrorKey =
  | "license_date"
  | "license_expiry_date"
  | "balance__balance_cif"
  | "exporter"
  | "port"
  | DateField
  | DecimalField;

export type LicenseFieldErrors = Partial<Record<LicenseFilterErrorKey, string>>;

/** Maps a multi-select value to the text shown for it (labels or "Unknown #id"). */
export type FilterLabelLookup = (field: MultiField, value: string) => string;

export interface LicenseFilterChip {
  key: string;
  label: string;
  /** Returns the next state with this value removed. Always resets page to 1. */
  remove: (state: LicenseListState) => LicenseListState;
}

export type LicenseApiParams = Record<string, string | number>;

/** Baseline (default view): hide expired and null-balance licences. */
export const BASELINE_IS_EXPIRED: TriState = "False";
export const BASELINE_FLAGS_IS_NULL: TriState = "False";

export function baselineFilters(): LicenseListFilters {
  return {
    search: "",
    exporter: [],
    exclude_exporter: [],
    port: [],
    exclude_port: [],
    purchase_status: [],
    export_license__norm_class: [],
    scheme_code: [],
    notification_number: [],
    is_expired: BASELINE_IS_EXPIRED,
    flags__is_null: BASELINE_FLAGS_IS_NULL,
    is_planned: "all",
    license_date__gte: "",
    license_date__lte: "",
    license_expiry_date__gte: "",
    license_expiry_date__lte: "",
    balance__balance_cif_min: "",
    balance__balance_cif_max: "",
  };
}

export function createBaselineState(): LicenseListState {
  return { filters: baselineFilters(), page: 1, pageSize: DEFAULT_PAGE_SIZE };
}

/** True when both baseline-owned fields are at their baseline values. */
export function isBaselineActive(filters: LicenseListFilters): boolean {
  return filters.is_expired === BASELINE_IS_EXPIRED && filters.flags__is_null === BASELINE_FLAGS_IS_NULL;
}

// ---------------------------------------------------------------------------
// Value normalisers
// ---------------------------------------------------------------------------

const ID_PATTERN = /^\d{1,10}$/;
const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const DECIMAL_PATTERN = new RegExp(`^-?\\d{1,${DECIMAL_MAX_INTEGER_DIGITS}}(\\.\\d{1,2})?$`);

function parsePositiveId(raw: string): number | null {
  if (!ID_PATTERN.test(raw)) return null;
  const value = Number(raw);
  return value > 0 && value <= MAX_DB_ID ? value : null;
}

/** Returns the trimmed YYYY-MM-DD string when it is a real calendar date, else null. */
export function normaliseIsoDate(raw: string): string | null {
  const text = raw.trim();
  const match = ISO_DATE_PATTERN.exec(text);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year < 1900 || year > 2999) return null;
  const probe = new Date(Date.UTC(year, month - 1, day));
  const valid =
    probe.getUTCFullYear() === year && probe.getUTCMonth() === month - 1 && probe.getUTCDate() === day;
  return valid ? text : null;
}

/**
 * Canonical decimal string with at most 2 dp and no redundant zeros
 * ("500.00" -> "500", "0.50" -> "0.5", "-0" -> "0"). Null when malformed.
 */
export function normaliseDecimal(raw: string): string | null {
  const text = raw.trim();
  if (!DECIMAL_PATTERN.test(text)) return null;
  const negative = text.startsWith("-");
  const body = negative ? text.slice(1) : text;
  const [integerPart, fractionPart = ""] = body.split(".");
  const integer = integerPart.replace(/^0+(?=\d)/, "");
  const fraction = fractionPart.replace(/0+$/, "");
  const magnitude = fraction ? `${integer}.${fraction}` : integer;
  const isZero = /^0(\.0*)?$/.test(magnitude);
  return negative && !isZero ? `-${magnitude}` : magnitude;
}

function sortedUniqueIds(values: readonly number[]): number[] {
  return [...new Set(values)].sort((a, b) => a - b);
}

function sortedUniqueCodes(values: readonly string[]): string[] {
  return [...new Set(values.map((v) => v.trim()).filter((v) => v !== ""))].sort();
}

/** Trims and caps free text. Shared by the URL serialiser and the search debounce. */
export function normaliseSearch(raw: string): string {
  return raw.trim().slice(0, SEARCH_MAX_LENGTH);
}

function normalisePage(raw: number): number {
  return Number.isInteger(raw) && raw >= 1 ? raw : 1;
}

function normalisePageSize(raw: number): LicenseListPageSize {
  return (PAGE_SIZE_OPTIONS as readonly number[]).includes(raw) ? (raw as LicenseListPageSize) : DEFAULT_PAGE_SIZE;
}

// ---------------------------------------------------------------------------
// Parse (URL -> state)
// ---------------------------------------------------------------------------

function readCsvTokens(params: URLSearchParams, key: string): string[] {
  const tokens: string[] = [];
  for (const raw of params.getAll(key)) {
    for (const part of raw.split(",")) {
      const token = part.trim();
      if (token !== "") tokens.push(token);
    }
  }
  return tokens;
}

function readIdCsv(params: URLSearchParams, key: string, warnings: string[]): number[] {
  const ids: number[] = [];
  for (const token of readCsvTokens(params, key)) {
    const id = parsePositiveId(token);
    if (id === null) warnings.push(`Ignored "${token}" in ${key}: expected a positive id.`);
    else ids.push(id);
  }
  return sortedUniqueIds(ids);
}

function readCodeCsv(params: URLSearchParams, key: string, warnings: string[]): string[] {
  const codes: string[] = [];
  for (const token of readCsvTokens(params, key)) {
    if (token.length > CODE_MAX_LENGTH) warnings.push(`Ignored a code longer than ${CODE_MAX_LENGTH} characters in ${key}.`);
    else codes.push(token);
  }
  return sortedUniqueCodes(codes);
}

/**
 * The first present key wins. Legacy names come after the canonical name so a
 * URL carrying both resolves to the canonical one.
 */
function readDate(params: URLSearchParams, names: readonly string[], warnings: string[]): string {
  for (const name of names) {
    const raw = params.get(name);
    if (raw === null || raw.trim() === "") continue;
    const date = normaliseIsoDate(raw);
    if (date === null) {
      warnings.push(`Ignored "${raw}" in ${name}: expected a date as YYYY-MM-DD.`);
      return "";
    }
    return date;
  }
  return "";
}

function readDecimal(params: URLSearchParams, name: string, warnings: string[]): string {
  const raw = params.get(name);
  if (raw === null || raw.trim() === "") return "";
  const value = normaliseDecimal(raw);
  if (value === null) {
    warnings.push(`Ignored "${raw}" in ${name}: expected a number with at most 2 decimal places.`);
    return "";
  }
  return value;
}

function readTriState(
  params: URLSearchParams,
  name: string,
  fallback: TriState,
  allowed: readonly TriState[],
  warnings: string[],
): TriState {
  const raw = params.get(name);
  if (raw === null || raw.trim() === "") return fallback;
  const text = raw.trim().toLowerCase();
  const match = allowed.find((option) => option.toLowerCase() === text);
  if (match !== undefined) return match;
  warnings.push(`Ignored "${raw}" in ${name}: using the default.`);
  return fallback;
}

function readPage(params: URLSearchParams, warnings: string[]): number {
  const raw = params.get("page");
  if (raw === null || raw.trim() === "") return 1;
  const text = raw.trim();
  if (/^\d{1,7}$/.test(text) && Number(text) >= 1) return Number(text);
  warnings.push(`Ignored page "${raw}": using page 1.`);
  return 1;
}

function readPageSize(params: URLSearchParams, warnings: string[]): LicenseListPageSize {
  const raw = params.get("page_size");
  if (raw === null || raw.trim() === "") return DEFAULT_PAGE_SIZE;
  const text = raw.trim();
  if (/^\d+$/.test(text) && (PAGE_SIZE_OPTIONS as readonly number[]).includes(Number(text))) {
    return Number(text) as LicenseListPageSize;
  }
  warnings.push(`Ignored page_size "${raw}": using ${DEFAULT_PAGE_SIZE}.`);
  return DEFAULT_PAGE_SIZE;
}

/**
 * Reads a URL query string into a typed state. Never throws: malformed values
 * fall back to defaults (or are dropped) and are reported in `warnings`.
 */
export function parseLicenseListSearch(search: string): LicenseListParseResult {
  const params = new URLSearchParams(search);
  const warnings: string[] = [];
  const baseline = baselineFilters();

  const filters: LicenseListFilters = {
    search: normaliseSearch(params.get("search") ?? ""),
    exporter: readIdCsv(params, "exporter", warnings),
    exclude_exporter: readIdCsv(params, "exclude_exporter", warnings),
    port: readIdCsv(params, "port", warnings),
    exclude_port: readIdCsv(params, "exclude_port", warnings),
    purchase_status: readIdCsv(params, "purchase_status", warnings),
    export_license__norm_class: readIdCsv(params, "export_license__norm_class", warnings),
    scheme_code: readCodeCsv(params, "scheme_code", warnings),
    notification_number: readCodeCsv(params, "notification_number", warnings),
    is_expired: readTriState(params, "is_expired", baseline.is_expired, ["all", "True", "False"], warnings),
    flags__is_null: readTriState(params, "flags__is_null", baseline.flags__is_null, ["all", "True", "False"], warnings),
    is_planned: readTriState(params, "is_planned", "all", ["all", "True", "False"], warnings),
    license_date__gte: readDate(params, ["license_date__gte", "license_date_from"], warnings),
    license_date__lte: readDate(params, ["license_date__lte", "license_date_to"], warnings),
    license_expiry_date__gte: readDate(params, ["license_expiry_date__gte", "license_expiry_date_from"], warnings),
    license_expiry_date__lte: readDate(params, ["license_expiry_date__lte", "license_expiry_date_to"], warnings),
    balance__balance_cif_min: readDecimal(params, "balance__balance_cif_min", warnings),
    balance__balance_cif_max: readDecimal(params, "balance__balance_cif_max", warnings),
  };

  return {
    state: {
      filters,
      page: readPage(params, warnings),
      pageSize: readPageSize(params, warnings),
    },
    warnings,
  };
}

// ---------------------------------------------------------------------------
// Serialise (state -> URL) — deterministic
// ---------------------------------------------------------------------------

function encodeQueryValue(value: string): string {
  // Keep commas literal so CSV values read as `purchase_status=1,2,4`.
  return encodeURIComponent(value).replace(/%2C/g, ",");
}

/**
 * Canonical URL query string. Fixed key order; CSVs sorted and de-duplicated;
 * `is_expired` and `flags__is_null` always present; `is_planned` only when not
 * "all"; empty values omitted; `page` and `page_size` always present.
 */
export function serializeLicenseListSearch(state: LicenseListState): string {
  const f = state.filters;
  const parts: string[] = [];
  const push = (key: string, value: string) => {
    if (value !== "") parts.push(`${key}=${encodeQueryValue(value)}`);
  };

  push("search", normaliseSearch(f.search));
  push("exporter", sortedUniqueIds(f.exporter).join(","));
  push("exclude_exporter", sortedUniqueIds(f.exclude_exporter).join(","));
  push("port", sortedUniqueIds(f.port).join(","));
  push("exclude_port", sortedUniqueIds(f.exclude_port).join(","));
  push("purchase_status", sortedUniqueIds(f.purchase_status).join(","));
  push("export_license__norm_class", sortedUniqueIds(f.export_license__norm_class).join(","));
  push("scheme_code", sortedUniqueCodes(f.scheme_code).join(","));
  push("notification_number", sortedUniqueCodes(f.notification_number).join(","));
  parts.push(`is_expired=${f.is_expired}`);
  parts.push(`flags__is_null=${f.flags__is_null}`);
  if (f.is_planned !== "all") parts.push(`is_planned=${f.is_planned}`);
  push("license_date__gte", f.license_date__gte);
  push("license_date__lte", f.license_date__lte);
  push("license_expiry_date__gte", f.license_expiry_date__gte);
  push("license_expiry_date__lte", f.license_expiry_date__lte);
  push("balance__balance_cif_min", normaliseDecimal(f.balance__balance_cif_min) ?? "");
  push("balance__balance_cif_max", normaliseDecimal(f.balance__balance_cif_max) ?? "");
  parts.push(`page=${normalisePage(state.page)}`);
  parts.push(`page_size=${normalisePageSize(state.pageSize)}`);

  return parts.join("&");
}

// ---------------------------------------------------------------------------
// API params (state -> backend names). The only place these names are produced.
// ---------------------------------------------------------------------------

/** Filter params only (no paging). Used by the export endpoints. */
export function toFilterApiParams(state: LicenseListState): LicenseApiParams {
  const f = state.filters;
  const params: LicenseApiParams = {};
  const setIf = (key: string, value: string) => {
    if (value !== "") params[key] = value;
  };

  const search = normaliseSearch(f.search);
  if (LICENSE_NUMBER_PATTERN.test(search)) params.license_number = search;
  else setIf("search", search);

  setIf("exporter", sortedUniqueIds(f.exporter).join(","));
  setIf("exclude_exporter", sortedUniqueIds(f.exclude_exporter).join(","));
  setIf("port", sortedUniqueIds(f.port).join(","));
  setIf("exclude_port", sortedUniqueIds(f.exclude_port).join(","));
  setIf("purchase_status", sortedUniqueIds(f.purchase_status).join(","));
  setIf("export_license__norm_class", sortedUniqueIds(f.export_license__norm_class).join(","));
  setIf("scheme_code", sortedUniqueCodes(f.scheme_code).join(","));
  setIf("notification_number", sortedUniqueCodes(f.notification_number).join(","));
  params.is_expired = f.is_expired;
  params.flags__is_null = f.flags__is_null;
  if (f.is_planned !== "all") params.is_planned = f.is_planned;
  setIf("license_date__gte", f.license_date__gte);
  setIf("license_date__lte", f.license_date__lte);
  setIf("license_expiry_date__gte", f.license_expiry_date__gte);
  setIf("license_expiry_date__lte", f.license_expiry_date__lte);
  setIf("balance__balance_cif_min", normaliseDecimal(f.balance__balance_cif_min) ?? "");
  setIf("balance__balance_cif_max", normaliseDecimal(f.balance__balance_cif_max) ?? "");
  return params;
}

/** Filter params plus `page` and `page_size`. Used by the list query. */
export function toApiParams(state: LicenseListState): LicenseApiParams {
  return {
    ...toFilterApiParams(state),
    page: normalisePage(state.page),
    page_size: normalisePageSize(state.pageSize),
  };
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

export function validateLicenseListFilters(filters: LicenseListFilters): LicenseFieldErrors {
  const errors: LicenseFieldErrors = {};

  const dateFields: DateField[] = [
    "license_date__gte",
    "license_date__lte",
    "license_expiry_date__gte",
    "license_expiry_date__lte",
  ];
  for (const field of dateFields) {
    const value = filters[field];
    if (value !== "" && normaliseIsoDate(value) === null) errors[field] = "Enter a valid date.";
  }

  if (filters.license_date__gte && filters.license_date__lte && filters.license_date__gte > filters.license_date__lte) {
    errors.license_date = "From must be on or before To.";
  }
  if (
    filters.license_expiry_date__gte &&
    filters.license_expiry_date__lte &&
    filters.license_expiry_date__gte > filters.license_expiry_date__lte
  ) {
    errors.license_expiry_date = "From must be on or before To.";
  }

  const decimalFields: DecimalField[] = ["balance__balance_cif_min", "balance__balance_cif_max"];
  for (const field of decimalFields) {
    const value = filters[field];
    if (value !== "" && normaliseDecimal(value) === null) {
      errors[field] = "Enter an amount with at most 2 decimal places.";
    }
  }

  const min = normaliseDecimal(filters.balance__balance_cif_min);
  const max = normaliseDecimal(filters.balance__balance_cif_max);
  if (min !== null && max !== null && Number(min) > Number(max)) {
    errors.balance__balance_cif = "Minimum must be less than or equal to maximum.";
  }

  const contradicts = (include: number[], exclude: number[]) => include.some((id) => exclude.includes(id));
  if (contradicts(filters.exporter, filters.exclude_exporter)) {
    errors.exporter = "The same exporter cannot be both included and excluded.";
  }
  if (contradicts(filters.port, filters.exclude_port)) {
    errors.port = "The same port cannot be both included and excluded.";
  }

  return errors;
}

export function hasLicenseFieldErrors(errors: LicenseFieldErrors): boolean {
  return Object.keys(errors).length > 0;
}

// ---------------------------------------------------------------------------
// Chips and counts
// ---------------------------------------------------------------------------

/** Returns a new state with the given filter patch applied. Filter changes always reset page to 1. */
export function withFilters(state: LicenseListState, patch: Partial<LicenseListFilters>): LicenseListState {
  return { ...state, page: 1, filters: { ...state.filters, ...patch } };
}

const MULTI_FIELD_PREFIX: Record<MultiField, string> = {
  exporter: "Exporter",
  exclude_exporter: "Exclude exporter",
  port: "Port",
  exclude_port: "Exclude port",
  purchase_status: "Purchase status",
  export_license__norm_class: "Norm class",
  scheme_code: "Scheme code",
  notification_number: "Notification number",
};

const DATE_CHIP_PREFIX: Record<DateField, string> = {
  license_date__gte: "Licence date from",
  license_date__lte: "Licence date to",
  license_expiry_date__gte: "Expiry date from",
  license_expiry_date__lte: "Expiry date to",
};

function removeMultiValue(state: LicenseListState, field: MultiField, value: string): LicenseListState {
  // The filter arrays are either number[] (id fields) or string[] (code fields).
  const current = state.filters[field] as readonly (number | string)[];
  const next = current.filter((item) => String(item) !== value);
  return withFilters(state, { [field]: next } as Partial<LicenseListFilters>);
}

/** Formats an ISO date for display: 2026-04-01 -> 01-04-2026. */
export function formatChipDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  return `${day}-${month}-${year}`;
}

/**
 * One chip per active value. Baseline values (is_expired=False,
 * flags__is_null=False, is_planned=all, everything empty) produce no chip.
 */
export function activeFilterChips(state: LicenseListState, labelFor: FilterLabelLookup): LicenseFilterChip[] {
  const f = state.filters;
  const chips: LicenseFilterChip[] = [];

  if (f.search !== "") {
    chips.push({
      key: "search",
      label: `Search: ${f.search}`,
      remove: (s) => withFilters(s, { search: "" }),
    });
  }

  const idFields: IdMultiField[] = [
    "exporter",
    "exclude_exporter",
    "port",
    "exclude_port",
    "purchase_status",
    "export_license__norm_class",
  ];
  for (const field of idFields) {
    for (const id of sortedUniqueIds(f[field])) {
      const value = String(id);
      chips.push({
        key: `${field}:${value}`,
        label: `${MULTI_FIELD_PREFIX[field]}: ${labelFor(field, value)}`,
        remove: (s) => removeMultiValue(s, field, value),
      });
    }
  }

  const codeFields: CodeMultiField[] = ["scheme_code", "notification_number"];
  for (const field of codeFields) {
    for (const code of sortedUniqueCodes(f[field])) {
      chips.push({
        key: `${field}:${code}`,
        label: `${MULTI_FIELD_PREFIX[field]}: ${labelFor(field, code)}`,
        remove: (s) => removeMultiValue(s, field, code),
      });
    }
  }

  if (f.is_expired !== BASELINE_IS_EXPIRED) {
    chips.push({
      key: "is_expired",
      label: f.is_expired === "True" ? "Licence status: Expired" : "Licence status: All",
      remove: (s) => withFilters(s, { is_expired: BASELINE_IS_EXPIRED }),
    });
  }

  if (f.flags__is_null !== BASELINE_FLAGS_IS_NULL) {
    chips.push({
      key: "flags__is_null",
      label: f.flags__is_null === "True" ? "Flags is null: Yes" : "Flags is null: All",
      remove: (s) => withFilters(s, { flags__is_null: BASELINE_FLAGS_IS_NULL }),
    });
  }

  if (f.is_planned !== "all") {
    chips.push({
      key: "is_planned",
      label: f.is_planned === "True" ? "Is planned: Yes" : "Is planned: No",
      remove: (s) => withFilters(s, { is_planned: "all" }),
    });
  }

  const dateFields: DateField[] = [
    "license_date__gte",
    "license_date__lte",
    "license_expiry_date__gte",
    "license_expiry_date__lte",
  ];
  for (const field of dateFields) {
    const value = f[field];
    if (value === "") continue;
    chips.push({
      key: field,
      label: `${DATE_CHIP_PREFIX[field]} ${formatChipDate(value)}`,
      remove: (s) => withFilters(s, { [field]: "" } as Partial<LicenseListFilters>),
    });
  }

  const minBalance = normaliseDecimal(f.balance__balance_cif_min);
  if (minBalance !== null) {
    chips.push({
      key: "balance__balance_cif_min",
      label: `Balance ≥ ₹${minBalance}`,
      remove: (s) => withFilters(s, { balance__balance_cif_min: "" }),
    });
  }
  const maxBalance = normaliseDecimal(f.balance__balance_cif_max);
  if (maxBalance !== null) {
    chips.push({
      key: "balance__balance_cif_max",
      label: `Balance ≤ ₹${maxBalance}`,
      remove: (s) => withFilters(s, { balance__balance_cif_max: "" }),
    });
  }

  return chips;
}

/**
 * Number of non-baseline filter values (one per chip). The baseline is not
 * counted, so the default view reports 0 and Clear all is hidden.
 */
export function countNonBaselineFilters(state: LicenseListState): number {
  return activeFilterChips(state, () => "").length;
}
