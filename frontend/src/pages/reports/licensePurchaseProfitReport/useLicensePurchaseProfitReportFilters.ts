import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useDebouncedFilters } from "@/hooks/useDebounce";
import {
    hasLicensePurchaseProfitReportParams,
    parseLicensePurchaseProfitReportParams,
} from "./buildLicensePurchaseProfitReportPath";

/** `norm` query-param options the backend accepts (see backend service's
 * `CONVERSION_NORMS` + `Others` catch-all / `All` no-op). */
export const LICENSE_PURCHASE_PROFIT_NORM_OPTIONS = ["All", "E1", "E5", "E126", "E132", "Others"] as const;

export type LicensePurchaseProfitNorm = (typeof LICENSE_PURCHASE_PROFIT_NORM_OPTIONS)[number];

const SESSION_STORAGE_KEY = "license-purchase-profit-filters";
const DEBOUNCE_MS = 400;

type PersistedFilters = {
    fromDate: string;
    toDate: string;
    norm: string;
    licenseNumber: string;
    excludeLicenseNumber: string[];
    exporter: unknown;
};

const DEFAULT_FILTERS: PersistedFilters = {
    fromDate: "",
    toDate: "",
    norm: "All",
    licenseNumber: "",
    excludeLicenseNumber: [],
    exporter: null,
};

function readSessionStorageFilters(): PersistedFilters | null {
    try {
        const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") return null;
        return {
            fromDate: String(parsed.fromDate ?? ""),
            toDate: String(parsed.toDate ?? ""),
            norm: String(parsed.norm ?? "All"),
            licenseNumber: String(parsed.licenseNumber ?? ""),
            excludeLicenseNumber: Array.isArray(parsed.excludeLicenseNumber)
                ? parsed.excludeLicenseNumber.map((v: unknown) => String(v ?? "")).filter(Boolean)
                : [],
            exporter: parsed.exporter ?? null,
        };
    } catch {
        // sessionStorage unavailable (private mode) or malformed JSON —
        // degrade to defaults rather than throwing on mount.
        return null;
    }
}

/** Mount-time-only hydration: URL params win when present; otherwise fall
 * back to the last session's filters; otherwise defaults. Only ever read
 * once (via `useState`'s lazy initializer in the hook below) — this report
 * doesn't react to subsequent external URL edits. */
function readInitialFilters(searchParams: URLSearchParams): PersistedFilters {
    if (hasLicensePurchaseProfitReportParams(searchParams)) {
        return parseLicensePurchaseProfitReportParams(searchParams);
    }
    return readSessionStorageFilters() ?? DEFAULT_FILTERS;
}

/**
 * Owns every filter on the License Purchase & Profit Report: From/To date
 * (required by the backend to load anything), Norm, License Number,
 * Exclude License Number and Exporter — plus "clear filters" and an
 * active-filters flag. Mirrors the shape of `useItemReportFilters` (state +
 * handlers + `hasActiveFilters`) but scoped to this report's much smaller
 * filter set.
 *
 * Adds URL query-string sync (so the report is deep-linkable and survives a
 * refresh) and a sessionStorage fallback (so navigating away and back via a
 * link, not Back/refresh, still restores the last filter set). License
 * Number / Exclude License Number are debounced 400ms — bundled together,
 * same pattern as `useItemReportFilters` — and the debounced values are
 * what drive the URL, sessionStorage, and (via `debouncedFilters`) the data
 * hook's fetch; From Date, To Date, Norm and Exporter apply immediately.
 */
export function useLicensePurchaseProfitReportFilters() {
    const [, setSearchParams] = useSearchParams();
    const [initial] = useState(() => readInitialFilters(new URLSearchParams(window.location.search)));

    const [fromDate, setFromDate] = useState(initial.fromDate);
    const [toDate, setToDate] = useState(initial.toDate);
    const [norm, setNorm] = useState<string>(initial.norm);
    const [licenseNumber, setLicenseNumber] = useState(initial.licenseNumber);
    const [excludeLicenseNumber, setExcludeLicenseNumber] = useState<string[]>(initial.excludeLicenseNumber);
    const [exporter, setExporter] = useState<unknown>(initial.exporter);

    const handleExporterChange = (value: unknown) => {
        setExporter(value ?? null);
    };

    const handleClearFilters = () => {
        setFromDate("");
        setToDate("");
        setNorm("All");
        setLicenseNumber("");
        setExcludeLicenseNumber([]);
        setExporter(null);
    };

    const hasActiveFilters = Boolean(fromDate) || Boolean(toDate) || norm !== "All" || Boolean(licenseNumber) || excludeLicenseNumber.length > 0 || Boolean(exporter);

    // License Number / Exclude License Number debounce together at 400ms so
    // typing doesn't fire a request (or a URL/sessionStorage write) per
    // keystroke — same `useDebouncedFilters` convention `useItemReportFilters`
    // uses, just a smaller bundle.
    const debouncedTextFilters = useMemo(
        () => ({ licenseNumber, excludeLicenseNumber }),
        [licenseNumber, excludeLicenseNumber],
    );
    const { debouncedFilters: debouncedText } = useDebouncedFilters(debouncedTextFilters, DEBOUNCE_MS);

    // The single merged filter set that actually drives the report: dates/
    // norm/exporter apply immediately, License Number/Exclude License
    // Number are the debounced values. This is what's handed to the data
    // hook, the URL, and sessionStorage — never the raw per-keystroke value.
    const debouncedFilters = useMemo(
        () => ({
            fromDate,
            toDate,
            norm,
            licenseNumber: debouncedText.licenseNumber,
            excludeLicenseNumber: debouncedText.excludeLicenseNumber,
            exporter,
        }),
        [fromDate, toDate, norm, debouncedText, exporter],
    );

    useEffect(() => {
        const params = new URLSearchParams();
        if (debouncedFilters.fromDate) params.set("from_date", debouncedFilters.fromDate);
        if (debouncedFilters.toDate) params.set("to_date", debouncedFilters.toDate);
        if (debouncedFilters.norm && debouncedFilters.norm !== "All") params.set("norm", debouncedFilters.norm);
        if (debouncedFilters.licenseNumber) params.set("license_number", debouncedFilters.licenseNumber);
        if (debouncedFilters.excludeLicenseNumber.length > 0) {
            params.set("exclude_license_number", debouncedFilters.excludeLicenseNumber.join(","));
        }
        const exporterId = debouncedFilters.exporter;
        if (exporterId !== null && exporterId !== undefined && exporterId !== "") {
            params.set("exporter_id", String(exporterId));
        }

        // `replace: true` — typing/selecting a filter shouldn't flood browser
        // history; Back from this page still leaves it normally.
        setSearchParams(params, { replace: true });

        try {
            sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(debouncedFilters));
        } catch {
            // Degrade silently — sessionStorage is a nice-to-have restore
            // path, never load-bearing (URL sync still works without it).
        }
        // `setSearchParams` is stable across renders (react-router-dom v7);
        // omitted to avoid re-running this effect on every render.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [debouncedFilters]);

    return {
        fromDate,
        setFromDate,
        toDate,
        setToDate,
        norm,
        setNorm,
        licenseNumber,
        setLicenseNumber,
        excludeLicenseNumber,
        setExcludeLicenseNumber,
        exporter,
        handleExporterChange,

        hasActiveFilters,
        handleClearFilters,

        // Debounced/merged filter set — pass straight into
        // `useLicensePurchaseProfitReportData`.
        debouncedFilters,
    };
}
