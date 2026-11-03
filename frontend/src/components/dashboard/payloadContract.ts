/**
 * Boundary validation for the dashboard payload (contract v3).
 *
 * The dashboard reads arrays and scalars straight from the response. This
 * module checks every field the UI depends on before the payload is stored.
 *
 * - A required part (`meta`, `attention`, `not_monitored`) that does not match
 *   rejects the whole payload. The page keeps its last good data.
 * - An optional section that does not match is replaced with a SectionError.
 *   Other sections still render.
 * - Every mismatch is recorded as a violation and logged. Nothing is turned
 *   into an empty list or a zero to make the page look valid.
 *
 * Absent sections (the caller's role does not grant them) are left absent.
 * Unknown extra keys are ignored, so the backend can add fields without
 * breaking the page.
 */
import type { DashboardResponse, SectionError } from "@/pages/dashboardContract";

export type ContractViolation = { section: string; problem: string };

export type ParsedDashboardPayload =
    | { ok: true; payload: DashboardResponse; violations: ContractViolation[] }
    | { ok: false; violations: ContractViolation[] };

export const CONTRACT_ERROR_MESSAGE =
    "This section could not be read because the server response did not match the expected format.";

/** Returns the list of problems. An empty list means the value matches. */
type Check = (value: unknown, path: string) => string[];

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null && !Array.isArray(value);

const expect = (condition: boolean, path: string, what: string): string[] =>
    condition ? [] : [`${path} should be ${what}`];

const number: Check = (v, p) => expect(typeof v === "number" && Number.isFinite(v), p, "a finite number");
const string: Check = (v, p) => expect(typeof v === "string", p, "a string");
const nullableString: Check = (v, p) => expect(v === null || typeof v === "string", p, "a string or null");
const nullableNumber: Check = (v, p) => expect(v === null || (typeof v === "number" && Number.isFinite(v)), p, "a number or null");
const boolean: Check = (v, p) => expect(typeof v === "boolean", p, "a boolean");
/** Money is a decimal string with exactly 2 dp. The frontend never sees a float here. */
const money: Check = (v, p) => expect(typeof v === "string" && /^-?\d+\.\d{2}$/.test(v), p, "a 2-decimal money string");
const literal =
    (...values: readonly string[]): Check =>
    (v, p) =>
        expect(typeof v === "string" && values.includes(v), p, `one of ${values.join(", ")}`);
const arrayOf =
    (item: Check): Check =>
    (v, p) =>
        Array.isArray(v) ? v.flatMap((entry, index) => item(entry, `${p}[${index}]`)) : [`${p} should be an array`];
const shape =
    (fields: Record<string, Check>): Check =>
    (v, p) =>
        isRecord(v) ? Object.entries(fields).flatMap(([key, check]) => check(v[key], `${p}.${key}`)) : [`${p} should be an object`];
const optional =
    (check: Check): Check =>
    (v, p) =>
        v === undefined ? [] : check(v, p);

const BAND_KEYS = ["expired", "d0_7", "d8_15", "d16_30", "d31_60", "over_60", "inactive", "no_expiry"] as const;
const ALLOTMENT_STATUSES = ["open", "partly_consumed", "consumed", "boe_linked"] as const;
const INVOICE_STATUSES = ["paid", "partially_paid", "unpaid"] as const;
const SEVERITIES = ["high", "medium", "low"] as const;

const boeRow = shape({
    id: number,
    bill_of_entry_number: string,
    bill_of_entry_date: nullableString,
    company_name: nullableString,
    invoice_no: nullableString,
    modified_on: string,
    allotment_links: number,
    licence_items: number,
    mapping_status: literal("mapped", "pending_licence_mapping"),
});

const licenceRef = shape({ id: number, license_number: string });

const CHECKS = {
    meta: shape({
        generated_at: string,
        as_of: string,
        as_of_timezone: string,
        cached: boolean,
        scope: shape({
            company_id: nullableNumber,
            company_name: nullableString,
            date_from: nullableString,
            date_to: nullableString,
        }),
        units: shape({ cif: literal("FC"), invoice: literal("INR") }),
    }),
    attention: arrayOf(
        shape({ key: string, count: number, severity: literal(...SEVERITIES), section: string }),
    ),
    not_monitored: arrayOf(shape({ key: string, reason: string })),
    licence_portfolio: shape({
        total: number,
        active: number,
        expired: number,
        missing_dgft: number,
        expiring_usable_30d: number,
        stale_expiry_flags: number,
        bands: arrayOf(shape({ key: literal(...BAND_KEYS), count: number })),
        within: shape({ "7": number, "15": number, "30": number, "60": number }),
    }),
    financial: shape({
        engine: literal("financial_available_balance"),
        authorized_cif: money,
        utilized_cif: money,
        reserved_cif: money,
        available_cif: money,
        expired_available_cif: money,
        committed_pct: nullableNumber,
        licences_in_scope: number,
        over_utilised_licences: number,
        bridge: shape({
            authorized: money,
            previous_owner_utilisation: money,
            purchased_cif: money,
            sale_utilisation: money,
            boe_utilisation: money,
            reserved: money,
            rounding: money,
            raw_available: money,
            over_utilisation_floor: money,
            available: money,
        }),
    }),
    expiring_licences: arrayOf(
        shape({
            id: number,
            license_number: string,
            license_expiry_date: string,
            days_to_expiry: number,
            balance_cif: money,
            sion_norms: arrayOf(string),
        }),
    ),
    licence_exceptions: shape({
        over_utilised: arrayOf(licenceRef),
        expired_with_balance: arrayOf(licenceRef),
        stale_expiry_flags: arrayOf(licenceRef),
    }),
    c969_link_review: shape({
        count: number,
        rows: arrayOf(
            shape({
                import_item_id: number,
                licence_id: number,
                licence_number: string,
                description: nullableString,
                saved_items: arrayOf(string),
                expected_item: string,
            }),
        ),
        error: optional(string),
    }),
    allotment_activity: shape({
        total: number,
        counts: shape({
            open: number,
            partly_consumed: number,
            consumed: number,
            boe_linked: number,
        }),
        totals: shape({
            allotted_cif: money,
            consumed_cif: money,
            reserved_cif: money,
            not_reserved_cif: money,
        }),
        recent: arrayOf(
            shape({
                id: number,
                reference: string,
                item_name: string,
                company_name: nullableString,
                created_on: string,
                licences: arrayOf(licenceRef),
                licence_count: number,
                original_quantity: money,
                allocated_quantity: money,
                unplaced_quantity: money,
                allotted_cif: money,
                consumed_cif: money,
                reserved_cif: money,
                not_reserved_cif: money,
                remaining_quantity: money,
                boe_count: number,
                status: literal(...ALLOTMENT_STATUSES),
            }),
        ),
    }),
    boe_activity: shape({
        total: number,
        linked_to_allotment: number,
        direct: number,
        pending_licence_mapping: number,
        without_invoice_no: number,
        recent: arrayOf(boeRow),
        pending_mapping: arrayOf(boeRow),
        recently_modified: arrayOf(boeRow),
        monthly_trend: arrayOf(shape({ month: string, count: number })),
    }),
    invoice_activity: shape({
        total: number,
        paid: number,
        partially_paid: number,
        unpaid: number,
        open: number,
        total_amount_inr: money,
        paid_inr: money,
        outstanding_inr: money,
        by_direction: shape({
            sale: shape({ total: number, outstanding_inr: money }),
            purchase: shape({ total: number, outstanding_inr: money }),
        }),
        not_tracked: arrayOf(literal("draft", "pending", "confirmed", "posted")),
        recent: arrayOf(
            shape({
                id: number,
                invoice_number: string,
                invoice_date: nullableString,
                direction: literal("sale", "purchase"),
                party_name: nullableString,
                total_amount_inr: money,
                outstanding_inr: money,
                status: literal(...INVOICE_STATUSES),
            }),
        ),
    }),
} satisfies Record<string, Check>;

/** The sections a page may omit, in the order the violations are reported. */
const OPTIONAL_SECTIONS = [
    "licence_portfolio",
    "financial",
    "expiring_licences",
    "licence_exceptions",
    "c969_link_review",
    "allotment_activity",
    "boe_activity",
    "invoice_activity",
] as const;

/** A SectionError is exactly `{ error: string }`. */
function isErrorOnly(value: unknown): value is SectionError {
    return isRecord(value) && Object.keys(value).length === 1 && typeof value.error === "string";
}

/**
 * Validates a raw response. Returns a payload safe to render, or `ok: false`
 * when a required part does not match. Callers log `violations` either way.
 */
export function parseDashboardPayload(raw: unknown): ParsedDashboardPayload {
    if (!isRecord(raw)) {
        return { ok: false, violations: [{ section: "root", problem: "response should be an object" }] };
    }

    const violations: ContractViolation[] = [];
    const requiredProblems = (["meta", "attention", "not_monitored"] as const).flatMap((key) =>
        CHECKS[key](raw[key], key).map((problem) => ({ section: key, problem })),
    );
    if (requiredProblems.length > 0) {
        return { ok: false, violations: requiredProblems };
    }

    const payload: Record<string, unknown> = {
        ...raw,
        meta: raw.meta,
        attention: raw.attention,
        not_monitored: raw.not_monitored,
    };

    for (const key of OPTIONAL_SECTIONS) {
        const value = raw[key];
        if (value === undefined || isErrorOnly(value)) {
            if (value !== undefined) payload[key] = value;
            continue;
        }
        const problems = CHECKS[key](value, key);
        if (problems.length === 0) {
            payload[key] = value;
            continue;
        }
        violations.push(...problems.map((problem) => ({ section: key, problem })));
        payload[key] = { error: CONTRACT_ERROR_MESSAGE } satisfies SectionError;
    }

    return { ok: true, payload: payload as unknown as DashboardResponse, violations };
}

/** Sections the client can refetch on their own (`?section=`). Mirrors `RETRYABLE_SECTIONS` on the backend. */
export type RetryableSection = "allotment_activity" | "boe_activity" | "invoice_activity";

export const RETRYABLE_SECTION_LIST: readonly RetryableSection[] = ["allotment_activity", "boe_activity", "invoice_activity"];

/**
 * Validates a single-section response (`{ meta, <section> }`). The section is
 * returned validated, or as a SectionError with a violation when it does not
 * match. A response without the section is a violation, never an empty section.
 */
export function parseDashboardSection<K extends RetryableSection>(
    name: K,
    raw: unknown,
): { section: NonNullable<DashboardResponse[K]>; violations: ContractViolation[] } {
    const violations: ContractViolation[] = [];
    if (!isRecord(raw)) {
        violations.push({ section: "root", problem: "response should be an object" });
    } else {
        const metaProblems = CHECKS.meta(raw.meta, "meta");
        violations.push(...metaProblems.map((problem) => ({ section: "meta", problem })));
    }

    const value = isRecord(raw) ? raw[name] : undefined;
    if (value === undefined) {
        violations.push({ section: name, problem: `${name} is missing from the response` });
        return { section: { error: CONTRACT_ERROR_MESSAGE } as NonNullable<DashboardResponse[K]>, violations };
    }
    if (isErrorOnly(value)) {
        return { section: value as NonNullable<DashboardResponse[K]>, violations };
    }
    const problems = CHECKS[name](value, name);
    if (problems.length > 0) {
        violations.push(...problems.map((problem) => ({ section: name, problem })));
        return { section: { error: CONTRACT_ERROR_MESSAGE } as NonNullable<DashboardResponse[K]>, violations };
    }
    return { section: value as NonNullable<DashboardResponse[K]>, violations };
}

/** One structured log line per response, so a contract drift is visible in the console. */
export function reportContractViolations(violations: ContractViolation[]): void {
    if (violations.length === 0) return;
    console.error("[dashboard] response did not match contract v3", violations);
}
