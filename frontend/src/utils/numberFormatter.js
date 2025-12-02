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
