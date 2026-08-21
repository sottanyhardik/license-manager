import {useCallback, useMemo, useState, useEffect} from "react";
import AsyncSelect from "react-select/async";
import api from "../api/axios";
import { _fkDetailCache, _fkInFlight } from "./fkDetailCache";
import { useDebouncedCallback } from "../hooks/useDebounce";

// Recent-selections are cached per endpoint so re-opening the same field
// (e.g. "Item Name" on another row) surfaces what you just picked instead of
// an empty menu. Session-scoped only — never sent anywhere.
const RECENTS_STORAGE_PREFIX = "asyncSelectField.recents:";
const RECENTS_LIMIT = 5;

// Escape regex-special characters so an inputValue like "1+1" or "a.b"
// can't blow up the highlight regex.
const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// Wrap the substring of `label` that case-insensitively matches `query` in a
// subtle highlight span. Returns `label` unchanged (any type) when there's
// nothing to highlight, so non-string labels and empty queries are no-ops.
const highlightMatch = (label, query) => {
    if (!query || typeof label !== "string") return label;
    const escaped = escapeRegExp(query);
    if (!escaped) return label;

    let parts;
    try {
        parts = label.split(new RegExp(`(${escaped})`, "gi"));
    } catch {
        return label;
    }
    if (parts.length <= 1) return label;

    // `String.split` with one capturing group alternates
    // [unmatched, matched, unmatched, matched, ...] — odd indices are matches.
    return parts.map((part, i) =>
        i % 2 === 1 ? (
            <span key={i} className="rounded-sm bg-primary/20 px-0.5 text-inherit">
                {part}
            </span>
        ) : (
            part
        )
    );
};

/**
 * AsyncSelectField Component - Select2-like with API support
 *
 * Props:
 * - endpoint: API endpoint to fetch options (required)
 * - labelField: field name to use as label (default: 'name')
 * - valueField: field name to use as value (default: 'id')
 * - value: current selected value(s)
 * - onChange: callback function(value)
 * - isMulti: enable multi-select (default: false)
 * - placeholder: placeholder text
 * - isClearable: allow clearing selection (default: true)
 * - isDisabled: disable the select
 * - formatLabel: custom function to format option label
 * - debounceDelay: ms to debounce the search API call while typing (default: 300)
 * - getOptionSubtitle: optional (item) => string | null — renders a second,
 *   muted line under each dropdown option's label. Omit for today's exact
 *   single-line rows.
 * - ariaLabel: optional aria-label passed through to the underlying select
 * - onMenuOpen / onMenuClose: optional pass-through to the underlying
 *   react-select, for callers that need to know the dropdown's open state
 *   (e.g. to disambiguate an Enter keypress that closes the menu from one
 *   that should submit a surrounding form)
 */
export default function AsyncSelectField({
    endpoint,
    labelField = "name",
    valueField = "id",
    value,
    onChange,
    isMulti = false,
    placeholder = "Select...",
    isClearable = true,
    isDisabled = false,
    formatLabel = null,
    className = "",
    loadOnMount = false,  // NEW: Control whether to load options on mount
    debounceDelay = 300,
    getOptionSubtitle = undefined,
    ariaLabel = undefined,
    inputId = undefined,
    name = undefined,
    onMenuOpen = undefined,
    onMenuClose = undefined,
}) {
    // Strip /api/ prefix if it exists to avoid double /api/api/
    let cleanEndpoint = endpoint?.startsWith('/api/') ? endpoint.substring(5) : endpoint;

    // Parse endpoint to separate base URL and existing query params
    const [baseEndpoint, queryString] = cleanEndpoint?.split('?') || [cleanEndpoint, ''];
    const existingParams = useMemo(() => new URLSearchParams(queryString), [queryString]);

    const [selectedOption, setSelectedOption] = useState(null);
    const [isSearching, setIsSearching] = useState(false);

    const recentsKey = `${RECENTS_STORAGE_PREFIX}${baseEndpoint || endpoint || ""}`;
    const [recents, setRecents] = useState(() => {
        try {
            const raw = sessionStorage.getItem(recentsKey);
            const parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed) ? parsed.slice(0, RECENTS_LIMIT) : [];
        } catch {
            // sessionStorage unavailable (private mode, disabled, etc.) — no recents.
            return [];
        }
    });

    const writeRecents = useCallback((list) => {
        try {
            sessionStorage.setItem(recentsKey, JSON.stringify(list));
        } catch {
            // Degrade silently — recents are a nice-to-have, never load-bearing.
        }
    }, [recentsKey]);

    const pushRecent = useCallback((option) => {
        if (!option || option.value === null || option.value === undefined) return;
        setRecents(prev => {
            const deduped = prev.filter(r => r.value !== option.value);
            const updated = [{ value: option.value, label: option.label }, ...deduped].slice(0, RECENTS_LIMIT);
            writeRecents(updated);
            return updated;
        });
    }, [writeRecents]);

    // Recent options as react-select option objects. Only {value, label} is
    // persisted, so `data` is empty here — getOptionSubtitle simply won't
    // find anything to show for a recent row, which is an acceptable trade-off.
    const recentOptions = useMemo(
        () => recents.map(r => ({ value: r.value, label: r.label, data: {} })),
        [recents]
    );

    const formatOption = useCallback((item) => {
        let label;

        if (formatLabel) {
            label = formatLabel(item);
        } else {
            label = item[labelField] || item[valueField] || String(item.id);
        }

        return {
            value: item[valueField],
            label: label,
            data: item
        };
    }, [formatLabel, labelField, valueField]);

    const fetchOptionById = async (id) => {
        try {
            // Resolve the lookup string. Some FKs use integer PKs (port,
            // company), others use slug/code values ("26", "025/2023" — when
            // the API exposes the field via SlugRelatedField). Don't parseInt
            // unconditionally — that turns "025/2023" into 25 and we'd fetch
            // the wrong row.
            const idStr = typeof id === 'number' ? String(id) : String(id);
            const isNumericId = /^\d+$/.test(idStr);

            // Any non-numeric value can't safely ride a raw detail-URL
            // lookup: slugs containing "/" get mangled by URL decoding
            // before Django's `[^/]+` lookup regex ever sees them, and a
            // short code/slug (e.g. "E5", "LG" — a `value_field` other than
            // the default numeric `id`) simply isn't the model's PK, so the
            // naive `{baseEndpoint}{idStr}/` GET 404s. Either way, fall
            // back to the list endpoint with a search filter and pick the
            // exact match by valueField (never labelField — the two only
            // happen to coincide for the handful of existing `value_field:
            // "code"` configs, e.g. notification_number/scheme_code; for
            // anything where they differ, matching by labelField would
            // silently return the wrong row).
            if (!isNumericId) {
                const params = new URLSearchParams(existingParams);
                params.set('search', idStr);
                params.set('page_size', '10');
                const listUrl = `${baseEndpoint}?${params.toString()}`;
                if (_fkDetailCache.has(listUrl)) {
                    return formatOption(_fkDetailCache.get(listUrl));
                }
                const {data} = await api.get(listUrl);
                const results = data.results || data || [];
                const exact = results.find(r => String(r[valueField] ?? '') === idStr);
                const match = exact || results[0];
                if (!match) return null;
                _fkDetailCache.set(listUrl, match);
                return formatOption(match);
            }

            // URL-safe detail lookup. encodeURIComponent so weird (but
            // path-legal) chars in slugs survive.
            const url = `${baseEndpoint}${encodeURIComponent(idStr)}/`;

            // Cached response — no network call.
            if (_fkDetailCache.has(url)) {
                return formatOption(_fkDetailCache.get(url));
            }
            // Coalesce concurrent calls for the same URL: each row's
            // AsyncSelectField fires its own useEffect on mount, so without
            // this several rows requesting the same FK ID would each issue
            // an HTTP GET.
            let pending = _fkInFlight.get(url);
            if (!pending) {
                pending = api.get(url).then(
                    ({data}) => {
                        _fkDetailCache.set(url, data);
                        _fkInFlight.delete(url);
                        return data;
                    },
                    (err) => {
                        _fkInFlight.delete(url);
                        throw err;
                    },
                );
                _fkInFlight.set(url, pending);
            }
            const data = await pending;
            return formatOption(data);
        } catch (err) {
            return null;
        }
    };

    const loadSelectedOption = async (val) => {
        if (!val) {
            setSelectedOption(null);
            return;
        }

        // If val is already a react-select {value, label} option, use it directly
        if (typeof val === 'object' && !Array.isArray(val) && 'value' in val && 'label' in val) {
            setSelectedOption(val);
            return;
        }

        // If val is already a full object with valueField, format it directly
        if (typeof val === 'object' && !Array.isArray(val) && val[valueField]) {
            setSelectedOption(formatOption(val));
            return;
        }

        if (isMulti) {
            // For multi-select, val should be an array of IDs or objects
            let items = Array.isArray(val) ? val : [val];

            // Handle comma-separated string values for backward compatibility
            if (items.length === 1 && typeof items[0] === 'string' && items[0].includes(',')) {
                items = items[0].split(',').map(id => id.trim()).filter(id => id);
            }

            // Filter out empty/null values
            items = items.filter(item => item !== null && item !== undefined && item !== '');

            const options = [];

            for (const item of items) {
                // If item is an object, format it directly
                if (typeof item === 'object' && item[valueField]) {
                    options.push(formatOption(item));
                } else {
                    // Otherwise fetch by ID
                    const opt = await fetchOptionById(item);
                    if (opt) options.push(opt);
                }
            }

            setSelectedOption(options);
        } else {
            // For single select
            const opt = await fetchOptionById(val);
            setSelectedOption(opt);
        }
    };

    // Sync internal state with external value
    useEffect(() => {
        if (value) {
            loadSelectedOption(value);
        } else {
            setSelectedOption(null);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [value]);

    // The actual search request. Debounced below so fast typing doesn't
    // spam the backend on every keystroke.
    const fetchOptionsFromAPI = useCallback(async (inputValue) => {
        try {
            // Merge existing params with new params
            const params = new URLSearchParams(existingParams);
            params.set('search', inputValue);
            params.set('page_size', '50');

            const {data} = await api.get(`${baseEndpoint}?${params.toString()}`);

            const results = data.results || data || [];
            return results.map(item => formatOption(item));
        } catch (err) {
            return [];
        } finally {
            setIsSearching(false);
        }
    }, [baseEndpoint, existingParams, formatOption]);

    const debouncedFetch = useDebouncedCallback(fetchOptionsFromAPI, debounceDelay);

    const loadOptions = (inputValue, callback) => {
        setIsSearching(true);
        debouncedFetch(inputValue)
            .then(options => { if (callback) callback(options); })
            .catch(() => { if (callback) callback([]); });
    };

    const handleChange = (selected) => {
        const previous = selectedOption;
        setSelectedOption(selected);

        if (isMulti) {
            const arr = Array.isArray(selected) ? selected : [];
            const prevArr = Array.isArray(previous) ? previous : [];
            const prevValues = new Set(prevArr.map(opt => opt.value));
            arr.filter(opt => !prevValues.has(opt.value)).forEach(pushRecent);

            // Return array of values for API compatibility
            const values = arr.map(opt => opt.value);
            onChange(values);
        } else {
            if (selected) pushRecent(selected);
            // Return single value
            onChange(selected ? selected.value : null);
        }
    };

    // Menu rows get optional match-highlighting + an optional subtitle line.
    // The closed control's value display (context "value") always stays a
    // plain single line, matching today's look exactly.
    const formatOptionLabel = (option, { context, inputValue: currentInput }) => {
        const highlighted = highlightMatch(option.label, currentInput);

        if (context === "menu" && getOptionSubtitle) {
            const subtitle = getOptionSubtitle((option.data || {}));
            if (subtitle) {
                return (
                    <div className="flex flex-col leading-tight">
                        <span>{highlighted}</span>
                        <span className="text-xs text-muted-foreground">{subtitle}</span>
                    </div>
                );
            }
        }

        return highlighted;
    };

    const noOptionsMessage = ({ inputValue }) =>
        inputValue ? `No matches for "${inputValue}"` : "Type to search…";

    const loadingMessage = () => "Searching…";

    // If loadOnMount is set, keep the exact original behavior (react-select
    // fetches the full first page once, on mount). Otherwise, fall back to
    // showing recent selections (if any) instead of an empty menu when the
    // field is opened with no query yet — still an empty menu when there's
    // nothing recent, exactly like today.
    const effectiveDefaultOptions = loadOnMount ? true : (recentOptions.length > 0 ? recentOptions : false);

    return (
        <div className="relative">
            <AsyncSelect
                cacheOptions
                defaultOptions={effectiveDefaultOptions}
                loadOptions={loadOptions}
                value={selectedOption}
                onChange={handleChange}
                isMulti={isMulti}
                isClearable={isClearable}
                isDisabled={isDisabled}
                placeholder={placeholder}
                className={className}
                classNamePrefix="react-select"
                formatOptionLabel={formatOptionLabel}
                noOptionsMessage={noOptionsMessage}
                loadingMessage={loadingMessage}
                menuPortalTarget={typeof document !== 'undefined' ? document.body : undefined}
                onMenuOpen={onMenuOpen}
                onMenuClose={onMenuClose}
                aria-label={ariaLabel}
                inputId={inputId}
                name={name}
                styles={{
                    control: (base) => ({
                        ...base,
                        minHeight: "38px",
                        borderColor: "var(--tb-border)"
                    }),
                    menu: (base) => ({
                        ...base,
                        zIndex: 9999
                    }),
                    menuPortal: (base) => ({
                        ...base,
                        zIndex: 9999
                    })
                }}
            />

            {/* Debounce-pending indicator — separate from react-select's own
                isLoading (which covers the in-flight HTTP request itself). */}
            {isSearching && (
                <div
                    className="pointer-events-none absolute right-8 top-1/2 -translate-y-1/2"
                    style={{ zIndex: 10000 }}
                >
                    <span
                        className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent text-primary"
                        aria-hidden="true"
                    />
                </div>
            )}
        </div>
    );
}
