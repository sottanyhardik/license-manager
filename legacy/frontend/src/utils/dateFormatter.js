/**
 * Date formatting utilities for consistent date display across the application
 */

/**
 * Parse date/datetime string to Date object, handling DD-MM-YYYY format
 * @param {string} dateString - Date string in DD-MM-YYYY, DD-MM-YYYY HH:mm, or YYYY-MM-DD format
 * @returns {Date|null} Date object or null if invalid
 */
export const parseDate = (dateString) => {
    if (!dateString) return null;

    // If it's already a Date object, return it
    if (dateString instanceof Date) {
        return isNaN(dateString.getTime()) ? null : dateString;
    }

    // Parse string date
    if (typeof dateString === 'string') {
        // Check if it contains time component (space followed by time)
        const hasTime = dateString.includes(' ');
        let datePart = dateString;
        let timePart = '';

        if (hasTime) {
            const parts = dateString.split(' ');
            datePart = parts[0];
            timePart = parts[1] || '';
        }

        // Split the date part to avoid timezone issues
        const parts = datePart.split(/[-/]/);
        if (parts.length === 3) {
            let year, month, day;

            // Check if it's YYYY-MM-DD format (year is 4 digits at start)
            if (parts[0].length === 4) {
                year = parseInt(parts[0], 10);
                month = parseInt(parts[1], 10) - 1; // Month is 0-indexed
                day = parseInt(parts[2], 10);
            }
            // Check if it's DD-MM-YYYY format (year is 4 digits at end)
            else if (parts[2].length === 4) {
                day = parseInt(parts[0], 10);
                month = parseInt(parts[1], 10) - 1; // Month is 0-indexed
                year = parseInt(parts[2], 10);
            } else {
                // Fallback to default Date parsing
                const date = new Date(dateString);
                return isNaN(date.getTime()) ? null : date;
            }

            // Parse time component if present
            let hours = 12, minutes = 0, seconds = 0;
            if (timePart) {
                const timeComponents = timePart.split(':');
                hours = parseInt(timeComponents[0], 10) || 12;
                minutes = parseInt(timeComponents[1], 10) || 0;
                seconds = parseInt(timeComponents[2], 10) || 0;
            }

            const date = new Date(year, month, day, hours, minutes, seconds);
            return isNaN(date.getTime()) ? null : date;
        }

        // If not a recognized format, try default Date parsing
        const date = new Date(dateString);
        return isNaN(date.getTime()) ? null : date;
    }

    return null;
};

/**
 * Format date to dd-MM-yyyy format
 * @param {string|Date} date - Date string or Date object
 * @returns {string} Formatted date string in dd-MM-yyyy format, or empty string if invalid
 */
export const formatDate = (date) => {
    if (!date) return '';

    try {
        const dateObj = typeof date === 'string' ? parseDate(date) : date;

        // Check if date is valid
        if (!dateObj || isNaN(dateObj.getTime())) return '';

        const day = String(dateObj.getDate()).padStart(2, '0');
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const year = dateObj.getFullYear();

        return `${day}-${month}-${year}`;
    } catch (error) {
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
        const dateObj = typeof date === 'string' ? parseDate(date) : date;

        // Check if date is valid
        if (!dateObj || isNaN(dateObj.getTime())) return '';

        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');

        return `${year}-${month}-${day}`;
    } catch (error) {
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
        // Parse datetime string properly to handle both ISO and DD-MM-YYYY formats
        let dateObj;
        if (typeof datetime === 'string') {
            // Check if it looks like DD-MM-YYYY format (has dashes and possibly time)
            if (datetime.match(/^\d{2}[-/]\d{2}[-/]\d{4}/)) {
                dateObj = parseDate(datetime);
            } else {
                // Use Date constructor for ISO strings and other formats
                dateObj = new Date(datetime);
            }
        } else {
            dateObj = datetime;
        }

        // Check if date is valid
        if (!dateObj || isNaN(dateObj.getTime())) return '';

        const day = String(dateObj.getDate()).padStart(2, '0');
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const year = dateObj.getFullYear();
        const hours = String(dateObj.getHours()).padStart(2, '0');
        const minutes = String(dateObj.getMinutes()).padStart(2, '0');

        return `${day}-${month}-${year} ${hours}:${minutes}`;
    } catch (error) {
        return '';
    }
};
