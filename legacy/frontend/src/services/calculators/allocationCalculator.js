/**
 * Allocation calculation utilities for allotments.
 *
 * Centralizes business logic for calculating allocation amounts,
 * validating constraints, and determining maximum allocations.
 */

/**
 * Calculate maximum allocation considering all constraints
 */
export const calculateMaxAllocation = (item, allotment) => {
    if (!allotment?.unit_value_per_unit) {
        return {qty: 0, value: 0};
    }

    const unitPrice = parseFloat(allotment.unit_value_per_unit) || 0;
    const balancedQty = parseInt(allotment.balanced_quantity || 0);
    const requiredValue = parseFloat(allotment.required_value || 0);
    const requiredValueWithBuffer = parseFloat(
        allotment.required_value_with_buffer || (requiredValue + 20)
    );
    const allottedValue = parseFloat(allotment.allotted_value || 0);
    const balancedValueWithBuffer = requiredValueWithBuffer - allottedValue;
    const availableQty = parseInt(item.available_quantity || 0);
    const availableCifFc = parseFloat(item.balance_cif_fc || 0);

    // Start with minimum of balanced quantity and available quantity
    let maxQty = Math.min(balancedQty, availableQty);
    let maxValue = maxQty * unitPrice;

    // Check if value exceeds available CIF FC
    if (maxValue > availableCifFc) {
        maxQty = Math.floor(availableCifFc / unitPrice);
        maxValue = maxQty * unitPrice;
    }

    // Check if value exceeds balanced value with buffer
    if (maxValue > balancedValueWithBuffer) {
        maxQty = Math.floor(balancedValueWithBuffer / unitPrice);
        maxValue = maxQty * unitPrice;
    }

    return {
        qty: Math.max(0, maxQty),
        value: Math.max(0, maxValue)
    };
};

/**
 * Calculate allocation value from quantity
 */
export const calculateAllocationValue = (qty, unitPrice) => {
    const quantity = parseFloat(qty) || 0;
    const price = parseFloat(unitPrice) || 0;
    return quantity * price;
};

/**
 * Calculate unit price from value and quantity
 */
export const calculateUnitPrice = (value, qty) => {
    const val = parseFloat(value) || 0;
    const quantity = parseFloat(qty) || 0;

    if (quantity === 0) return 0;

    return val / quantity;
};

/**
 * Validate allocation against constraints
 */
export const validateAllocation = (qty, value, item, allotment) => {
    const errors = [];

    const quantity = parseFloat(qty) || 0;
    const allocationValue = parseFloat(value) || 0;

    if (quantity <= 0) {
        errors.push('Quantity must be greater than zero');
    }

    if (allocationValue <= 0) {
        errors.push('Value must be greater than zero');
    }

    // Calculate maximum allowed
    const max = calculateMaxAllocation(item, allotment);

    if (quantity > max.qty) {
        errors.push(`Quantity exceeds maximum allowed: ${max.qty}`);
    }

    if (allocationValue > max.value) {
        errors.push(`Value exceeds maximum allowed: ${max.value.toFixed(2)}`);
    }

    // Validate unit price matches
    const expectedUnitPrice = parseFloat(allotment.unit_value_per_unit) || 0;
    const calculatedUnitPrice = calculateUnitPrice(allocationValue, quantity);
    const priceDifference = Math.abs(calculatedUnitPrice - expectedUnitPrice);

    if (priceDifference > 0.01) {
        errors.push(
            `Unit price mismatch. Expected: ${expectedUnitPrice.toFixed(2)}, ` +
            `Calculated: ${calculatedUnitPrice.toFixed(2)}`
        );
    }

    return {
        isValid: errors.length === 0,
        errors
    };
};

/**
 * Calculate remaining allocation capacity for allotment
 */
export const calculateRemainingCapacity = (allotment) => {
    const requiredValue = parseFloat(allotment.required_value || 0);
    const requiredValueWithBuffer = parseFloat(
        allotment.required_value_with_buffer || (requiredValue + 20)
    );
    const allottedValue = parseFloat(allotment.allotted_value || 0);
    const balancedQty = parseInt(allotment.balanced_quantity || 0);
    const allottedQty = parseInt(allotment.allotted_quantity || 0);

    return {
        remainingValue: Math.max(0, requiredValueWithBuffer - allottedValue),
        remainingQty: Math.max(0, balancedQty - allottedQty),
        currentValue: allottedValue,
        currentQty: allottedQty,
        requiredValue: requiredValue,
        requiredValueWithBuffer: requiredValueWithBuffer
    };
};

/**
 * Check if allotment is fully allocated
 */
export const isFullyAllocated = (allotment) => {
    const requiredValue = parseFloat(allotment.required_value || 0);
    const allottedValue = parseFloat(allotment.allotted_value || 0);

    // Consider fully allocated if within 99% of required value
    return allottedValue >= (requiredValue * 0.99);
};

/**
 * Calculate allocation percentage
 */
export const calculateAllocationPercentage = (allotment) => {
    const requiredValue = parseFloat(allotment.required_value || 0);
    const allottedValue = parseFloat(allotment.allotted_value || 0);

    if (requiredValue === 0) return 0;

    return Math.min(100, (allottedValue / requiredValue) * 100);
};

/**
 * Format allocation summary
 */
export const formatAllocationSummary = (allotment) => {
    const percentage = calculateAllocationPercentage(allotment);
    const remaining = calculateRemainingCapacity(allotment);
    const isComplete = isFullyAllocated(allotment);

    return {
        percentage: percentage.toFixed(1),
        isComplete,
        remaining: remaining.remainingValue.toFixed(2),
        current: remaining.currentValue.toFixed(2),
        required: remaining.requiredValue.toFixed(2),
        status: isComplete ? 'Complete' :
            percentage > 90 ? 'Almost Complete' :
                percentage > 50 ? 'In Progress' : 'Started'
    };
};

export default {
    calculateMaxAllocation,
    calculateAllocationValue,
    calculateUnitPrice,
    validateAllocation,
    calculateRemainingCapacity,
    isFullyAllocated,
    calculateAllocationPercentage,
    formatAllocationSummary,
};
