/**
 * Date formatting utilities for consistent date display across the application
 */

/**
 * Format date to dd-MM-yyyy format
 * @param {string|Date} date - Date string or Date object
 * @returns {string} Formatted date string in dd-MM-yyyy format, or empty string if invalid
 */
export const formatDate = (date) => {
    if (!date) return '';

    try {
        const dateObj = typeof date === 'string' ? new Date(date) : date;

        // Check if date is valid
        if (isNaN(dateObj.getTime())) return '';

        const day = String(dateObj.getDate()).padStart(2, '0');
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const year = dateObj.getFullYear();

        return `${day}-${month}-${year}`;
    } catch (error) {
        console.error('Error formatting date:', error);
        return '';
    }
};

/**
 * Format date to yyyy-MM-dd format (for input fields)
 * @param {string|Date} date - Date string or Date object
 * @returns {string} Formatted date string in yyyy-MM-dd format, or empty string if invalid
 */
export const formatDateForInput = (date) => {
    if (!date) return '';

    try {
        const dateObj = typeof date === 'string' ? new Date(date) : date;

        // Check if date is valid
        if (isNaN(dateObj.getTime())) return '';

        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');

        return `${year}-${month}-${day}`;
    } catch (error) {
        console.error('Error formatting date for input:', error);
        return '';
    }
};

/**
 * Format datetime to dd-MM-yyyy HH:mm format
 * @param {string|Date} datetime - Datetime string or Date object
 * @returns {string} Formatted datetime string, or empty string if invalid
 */
export const formatDateTime = (datetime) => {
    if (!datetime) return '';

    try {
        const dateObj = typeof datetime === 'string' ? new Date(datetime) : datetime;

        // Check if date is valid
        if (isNaN(dateObj.getTime())) return '';

        const day = String(dateObj.getDate()).padStart(2, '0');
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const year = dateObj.getFullYear();
        const hours = String(dateObj.getHours()).padStart(2, '0');
        const minutes = String(dateObj.getMinutes()).padStart(2, '0');

        return `${day}-${month}-${year} ${hours}:${minutes}`;
    } catch (error) {
        console.error('Error formatting datetime:', error);
        return '';
    }
};
