import type { SionPlanningRule, RuleAllocationStrategy } from "@/services/api/planningRuleApi";

export interface RuleFormErrors extends Record<string, any> {
    name?: string;
    max_unit_price?: string;
    unit?: string;
    import_item?: string;
    unit_value_rows?: string;
    percentage_rows?: string;
    split?: string;
    split_buckets?: Record<number, Record<string, string>>;
    residual_policy?: string;
}

const decimalPattern = /^\d+(?:\.\d+)?$/;

/** Compare two non-negative decimal strings without IEEE-754 conversion. */
function compareDecimalStrings(left: string, right: string): number | null {
    if (!decimalPattern.test(left) || !decimalPattern.test(right)) return null;
    const [leftWholeRaw, leftFractionRaw = ""] = left.split(".");
    const [rightWholeRaw, rightFractionRaw = ""] = right.split(".");
    const leftWhole = leftWholeRaw.replace(/^0+(?=\d)/, "");
    const rightWhole = rightWholeRaw.replace(/^0+(?=\d)/, "");
    if (leftWhole.length !== rightWhole.length) return leftWhole.length > rightWhole.length ? 1 : -1;
    if (leftWhole !== rightWhole) return leftWhole > rightWhole ? 1 : -1;
    const width = Math.max(leftFractionRaw.length, rightFractionRaw.length);
    const leftFraction = leftFractionRaw.padEnd(width, "0");
    const rightFraction = rightFractionRaw.padEnd(width, "0");
    return leftFraction === rightFraction ? 0 : leftFraction > rightFraction ? 1 : -1;
}

/**
 * Validates planning rule form before submission.
 * Returns an object with field-level error messages.
 */
export function validatePlanningRule(
    rule: SionPlanningRule,
    allocation: RuleAllocationStrategy | null
): RuleFormErrors {
    const errors: RuleFormErrors = {};

    // Validate name
    if (!rule.name || !rule.name.trim()) {
        errors.name = "Rule name is required";
    }

    // Validate max_unit_price
    if (!rule.max_unit_price || rule.max_unit_price.trim() === "") {
        errors.max_unit_price = "Maximum unit price is required";
    } else if (!/^\d+(\.\d{1,2})?$/.test(rule.max_unit_price)) {
        errors.max_unit_price = "Price must be a valid decimal";
    } else if (parseFloat(rule.max_unit_price) < 0) {
        errors.max_unit_price = "Price must be non-negative";
    }

    // Validate unit
    if (!rule.unit || !rule.unit.trim()) {
        errors.unit = "Unit is required";
    }

    const strategy = allocation?.strategy ?? rule.strategy ?? "STANDARD";
    if (strategy === "STANDARD" && !allocation?.import_item) {
        errors.import_item = "Import item is required";
    }
    if (strategy === "SPLIT_BY_UNIT_VALUE" && !allocation?.unit_value_rows?.length) {
        errors.unit_value_rows = "Add at least one import item";
    } else if (strategy === "SPLIT_BY_UNIT_VALUE") {
        const rows = allocation?.unit_value_rows ?? [];
        const parsedRows: Array<{ index: number; min: string; max: string }> = [];
        for (const [index, row] of rows.entries()) {
            const rowLabel = `Row ${index + 1}`;
            if (!row.import_item) {
                errors.unit_value_rows = `${rowLabel}: Import item is required`;
                break;
            }
            // A Unit Value strategy intentionally permits one import item in
            // multiple non-overlapping price bands (for example RUTILE below
            // and above a calculated average threshold).
            if (!decimalPattern.test(row.min_unit_price) || !decimalPattern.test(row.max_unit_price)) {
                errors.unit_value_rows = `${rowLabel}: Min and Max Unit Price must be valid decimals`;
                break;
            }
            if (row.preferred_unit_price !== "" && !decimalPattern.test(row.preferred_unit_price)) {
                errors.unit_value_rows = `${rowLabel}: Preferred Unit Price must be a valid decimal`;
                break;
            }
            if (compareDecimalStrings(row.max_unit_price, row.min_unit_price)! <= 0) {
                errors.unit_value_rows = `${rowLabel}: Max Unit Price must be greater than Min Unit Price`;
                break;
            }
            parsedRows.push({ index, min: row.min_unit_price, max: row.max_unit_price });
        }
        if (!errors.unit_value_rows) {
            const ordered = [...parsedRows].sort((left, right) => compareDecimalStrings(left.min, right.min)!);
            for (let index = 1; index < ordered.length; index += 1) {
                if (compareDecimalStrings(ordered[index].min, ordered[index - 1].max)! < 0) {
                    errors.unit_value_rows = "Price ranges overlap";
                    break;
                }
            }
        }
    }
    if (strategy === "SPLIT_BY_PERCENT") {
        const rows = allocation?.percentage_rows ?? [];
        if (!rows.length) errors.percentage_rows = "Add at least one import item";
        else if (Math.abs(rows.reduce((sum, row) => sum + Number(row.percentage || 0), 0) - 100) > 0.001) {
            errors.percentage_rows = "Percentages must total 100%";
        }
        const ids = rows.map((row) => row.import_item).filter(Boolean);
        if (new Set(ids).size !== ids.length) errors.percentage_rows = "Each import item may only be selected once";
    }

    // Validate split allocation if applicable
    if (allocation && allocation.strategy === "SPLIT_BY_UNIT_VALUE" && allocation.config && "buckets" in allocation.config) {
        const { buckets } = allocation.config;

        if (!Array.isArray(buckets) || buckets.length < 2) {
            errors.split = "At least two output buckets are required";
        } else {
            const bucketErrors: Record<number, Record<string, string>> = {};

            buckets.forEach((bucket, index) => {
                const bucketError: Record<string, string> = {};

                // Validate code
                if (!bucket.code || !bucket.code.trim()) {
                    bucketError.code = "Bucket code required";
                }

                // Validate prices
                const minPrice = parseFloat(bucket.min_price);
                const maxPrice = parseFloat(bucket.max_price);
                const refPrice = parseFloat(bucket.reference_price);

                if (isNaN(minPrice) || isNaN(maxPrice) || isNaN(refPrice)) {
                    bucketError.price = "All prices must be valid decimals";
                } else {
                    if (minPrice < 0 || maxPrice < 0 || refPrice < 0) {
                        bucketError.price = "Prices must be non-negative";
                    } else if (maxPrice <= minPrice) {
                        bucketError.price = "Max price must be greater than min price";
                    } else if (refPrice < minPrice || refPrice > maxPrice) {
                        bucketError.price = "Reference price must be between min and max";
                    }
                }

                if (Object.keys(bucketError).length > 0) {
                    bucketErrors[index] = bucketError;
                }
            });

            // Validate adjacency and ordering
            for (let i = 0; i < buckets.length - 1; i++) {
                const current = buckets[i];
                const next = buckets[i + 1];
                const currentMax = parseFloat(current.max_price);
                const nextMin = parseFloat(next.min_price);
                const currentRef = parseFloat(current.reference_price);
                const nextRef = parseFloat(next.reference_price);

                if (nextMin !== currentMax) {
                    if (!bucketErrors[i]) bucketErrors[i] = {};
                    bucketErrors[i].max_price = `Max price must equal next bucket's min price (${nextMin})`;
                }

                if (nextRef <= currentRef) {
                    if (!bucketErrors[i + 1]) bucketErrors[i + 1] = {};
                    bucketErrors[i + 1].reference_price = "Reference prices must increase across buckets";
                }
            }

            if (Object.keys(bucketErrors).length > 0) {
                errors.split_buckets = bucketErrors;
            }
        }
    }

    return errors;
}

/**
 * Check if form has any validation errors
 */
export function hasValidationErrors(errors: RuleFormErrors): boolean {
    return Object.values(errors).some(err => err && (typeof err === "string" || Object.keys(err).length > 0));
}
