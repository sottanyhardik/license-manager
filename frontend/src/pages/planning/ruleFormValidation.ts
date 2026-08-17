import type { SionPlanningRule, RuleAllocationStrategy } from "@/services/api/planningRuleApi";

export interface RuleFormErrors extends Record<string, any> {
    name?: string;
    max_unit_price?: string;
    unit?: string;
    expression?: string;
    output_item?: string;
    split?: string;
    split_buckets?: Record<number, Record<string, string>>;
    residual_policy?: string;
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

    // Validate expression (at least one condition)
    if (!rule.expression || !rule.expression.conditions || rule.expression.conditions.length === 0) {
        errors.expression = "At least one match condition is required";
    }

    // Validate output_item (required for most strategies)
    if (!rule.output_item) {
        errors.output_item = "Output item is required";
    }

    // Validate split allocation if applicable
    if (allocation && allocation.strategy === "SPLIT_BY_UNIT_VALUE" && allocation.config) {
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
