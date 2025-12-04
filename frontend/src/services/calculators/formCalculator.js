/**
 * Form field calculation utilities.
 *
 * Handles auto-calculation logic for form fields based on other field values.
 */

/**
 * Auto-calculate registration number from license number
 */
export const calculateRegistrationNumber = (licenseNumber) => {
    if (!licenseNumber) return '';

    // Extract registration number from license number
    // Format: XXXXXXXX/YYYY -> XXXXXXXX
    const parts = licenseNumber.split('/');
    return parts[0] || '';
};

/**
 * Auto-calculate dates based on license date
 */
export const calculateRelatedDates = (licenseDate, expiryMonths = 12) => {
    if (!licenseDate) return {};

    const date = new Date(licenseDate);

    // Calculate expiry date (default 12 months from license date)
    const expiryDate = new Date(date);
    expiryDate.setMonth(expiryDate.getMonth() + expiryMonths);

    // Registration date same as license date
    const registrationDate = new Date(date);

    return {
        license_expiry_date: expiryDate.toISOString().split('T')[0],
        registration_date: registrationDate.toISOString().split('T')[0]
    };
};

/**
 * Calculate CIF value from quantity and unit price
 */
export const calculateCIF = (quantity, unitPrice) => {
    const qty = parseFloat(quantity) || 0;
    const price = parseFloat(unitPrice) || 0;
    return (qty * price).toFixed(2);
};

/**
 * Calculate unit price from CIF and quantity
 */
export const calculateUnitPriceFromCIF = (cif, quantity) => {
    const cifValue = parseFloat(cif) || 0;
    const qty = parseFloat(quantity) || 0;

    if (qty === 0) return '0.00';

    return (cifValue / qty).toFixed(4);
};

/**
 * Calculate balanced quantity for allotment
 */
export const calculateBalancedQuantity = (requiredValue, unitPrice) => {
    const value = parseFloat(requiredValue) || 0;
    const price = parseFloat(unitPrice) || 0;

    if (price === 0) return 0;

    return Math.floor(value / price);
};

/**
 * Calculate required value with buffer
 */
export const calculateRequiredValueWithBuffer = (requiredValue, bufferAmount = 20) => {
    const value = parseFloat(requiredValue) || 0;
    const buffer = parseFloat(bufferAmount) || 0;
    return (value + buffer).toFixed(2);
};

/**
 * Auto-fill fields based on field change
 */
export const autoCalculateFields = (formData, changedField, changedValue) => {
    const updates = {};

    // License form calculations
    if (changedField === 'license_number') {
        const regNumber = calculateRegistrationNumber(changedValue);
        if (regNumber) {
            updates.registration_number = regNumber;
        }
    }

    if (changedField === 'license_date') {
        const dates = calculateRelatedDates(changedValue);
        Object.assign(updates, dates);
    }

    // Import/Export item calculations
    if (changedField === 'quantity' || changedField === 'unit_price') {
        const qty = changedField === 'quantity' ? changedValue : formData.quantity;
        const price = changedField === 'unit_price' ? changedValue : formData.unit_price;
        updates.cif_fc = calculateCIF(qty, price);
    }

    if (changedField === 'cif_fc' && formData.quantity) {
        updates.unit_price = calculateUnitPriceFromCIF(changedValue, formData.quantity);
    }

    // Allotment calculations
    if (changedField === 'required_value' || changedField === 'unit_value_per_unit') {
        const value = changedField === 'required_value' ? changedValue : formData.required_value;
        const price = changedField === 'unit_value_per_unit' ? changedValue : formData.unit_value_per_unit;

        if (value && price) {
            updates.balanced_quantity = calculateBalancedQuantity(value, price);
        }
    }

    if (changedField === 'required_value') {
        updates.required_value_with_buffer = calculateRequiredValueWithBuffer(changedValue);
    }

    return updates;
};

/**
 * Validate numeric field value
 */
export const validateNumericField = (value, min = null, max = null, decimals = 2) => {
    const num = parseFloat(value);

    if (isNaN(num)) {
        return {isValid: false, error: 'Must be a valid number'};
    }

    if (min !== null && num < min) {
        return {isValid: false, error: `Must be at least ${min}`};
    }

    if (max !== null && num > max) {
        return {isValid: false, error: `Must be at most ${max}`};
    }

    return {isValid: true, value: num.toFixed(decimals)};
};

/**
 * Validate date field
 */
export const validateDateField = (date, minDate = null, maxDate = null) => {
    const dateObj = new Date(date);

    if (isNaN(dateObj.getTime())) {
        return {isValid: false, error: 'Invalid date'};
    }

    if (minDate && dateObj < new Date(minDate)) {
        return {isValid: false, error: `Date must be after ${minDate}`};
    }

    if (maxDate && dateObj > new Date(maxDate)) {
        return {isValid: false, error: `Date must be before ${maxDate}`};
    }

    return {isValid: true};
};

/**
 * Validate date range
 */
export const validateDateRange = (startDate, endDate) => {
    const start = new Date(startDate);
    const end = new Date(endDate);

    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
        return {isValid: false, error: 'Invalid date range'};
    }

    if (start > end) {
        return {isValid: false, error: 'Start date must be before end date'};
    }

    return {isValid: true};
};

/**
 * Format number with thousand separators
 */
export const formatNumber = (value, decimals = 2) => {
    const num = parseFloat(value);
    if (isNaN(num)) return '0.00';

    return num.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
};

/**
 * Parse formatted number (remove thousand separators)
 */
export const parseFormattedNumber = (formattedValue) => {
    if (typeof formattedValue !== 'string') return formattedValue;

    const cleaned = formattedValue.replace(/,/g, '');
    const num = parseFloat(cleaned);
    return isNaN(num) ? 0 : num;
};

export default {
    calculateRegistrationNumber,
    calculateRelatedDates,
    calculateCIF,
    calculateUnitPriceFromCIF,
    calculateBalancedQuantity,
    calculateRequiredValueWithBuffer,
    autoCalculateFields,
    validateNumericField,
    validateDateField,
    validateDateRange,
    formatNumber,
    parseFormattedNumber,
};
