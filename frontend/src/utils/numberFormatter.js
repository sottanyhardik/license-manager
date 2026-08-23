/**
 * Format number to Indian number format (12,34,567.89)
 *
 * @param {number|string} value - The number to format
 * @param {number} decimals - Number of decimal places (default: 2)
 * @returns {string} Formatted number string
 */
export const formatIndianNumber = (value, decimals = 2) => {
    try {
        const num = parseFloat(value);

        if (isNaN(num)) {
            return value?.toString() || '';
        }

        // Split into integer and decimal parts
        const fixed = num.toFixed(decimals);
        const parts = fixed.split('.');
        let integerPart = parts[0];
        const decimalPart = parts[1];

        // Handle negative numbers
        const isNegative = integerPart.startsWith('-');
        if (isNegative) {
            integerPart = integerPart.substring(1);
        }

        // Apply Indian number format: last 3 digits, then groups of 2
        let formattedInt = '';
        if (integerPart.length <= 3) {
            formattedInt = integerPart;
        } else {
            // Get last 3 digits
            const lastThree = integerPart.slice(-3);
            let remaining = integerPart.slice(0, -3);

            // Group remaining digits in pairs from right to left
            const groups = [];
            while (remaining.length > 0) {
                if (remaining.length <= 2) {
                    groups.unshift(remaining);
                    break;
                }
                groups.unshift(remaining.slice(-2));
                remaining = remaining.slice(0, -2);
            }

            formattedInt = groups.join(',') + ',' + lastThree;
        }

        // Add negative sign back if needed
        if (isNegative) {
            formattedInt = '-' + formattedInt;
        }

        // Return with decimal part
        return decimals > 0 ? `${formattedInt}.${decimalPart}` : formattedInt;

    } catch (error) {
        return value?.toString() || '';
    }
};

/**
 * Format CIF FC value (2 decimals)
 */
export const formatCifFC = (value) => formatIndianNumber(value, 2);

/**
 * Format CIF INR value (2 decimals)
 */
export const formatCifINR = (value) => formatIndianNumber(value, 2);

/**
 * Format Quantity (2 decimals)
 */
export const formatQuantity = (value) => formatIndianNumber(value, 2);

/**
 * Format FOB value (2 decimals)
 */
export const formatFOB = (value) => formatIndianNumber(value, 2);

/**
 * Abbreviate a number to Indian Lakh/Crore notation (e.g. 12690443 ->
 * "1.27 Cr", 479500 -> "4.80 L"). Small values fall back to the existing
 * `formatIndianNumber(value, 2)` — no abbreviation needed. No currency
 * symbol, matching `formatIndianNumber`'s own convention.
 */
export const formatIndianCompact = (value) => {
    try {
        const num = parseFloat(value);

        if (isNaN(num)) {
            return value?.toString() || '';
        }

        // Handle negative numbers the same way formatIndianNumber does:
        // strip the sign, format the magnitude, then re-prepend it.
        const isNegative = num < 0;
        const abs = Math.abs(num);

        let formatted;
        if (abs >= 10000000) {
            formatted = `${(abs / 10000000).toFixed(2)} Cr`;
        } else if (abs >= 100000) {
            const lakhs = (abs / 100000).toFixed(2);
            // Rounding can push a value just under 1 crore (e.g.
            // 99,99,999.99) to "100.00 L" — re-express as Cr instead.
            formatted = parseFloat(lakhs) >= 100
                ? `${(abs / 10000000).toFixed(2)} Cr`
                : `${lakhs} L`;
        } else {
            return formatIndianNumber(value, 2);
        }

        return isNegative ? `-${formatted}` : formatted;

    } catch (error) {
        return value?.toString() || '';
    }
};
