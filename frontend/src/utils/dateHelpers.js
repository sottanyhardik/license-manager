/**
 * Date Helper Utilities
 *
 * Centralized date handling functions to ensure consistency across the application.
 * Uses the existing dateFormatter module and adds additional helper functions.
 */

import { formatDate as formatDateUtil, parseDate as parseDateUtil, formatDateForInput as formatDateForInputUtil } from './dateFormatter';
import { DATE_FORMAT, DISPLAY_DATE_FORMAT } from '../constants';

/**
 * Format a date for display (DD-MM-YYYY format)
 * @param {Date|string} date - Date to format
 * @returns {string} Formatted date string
 */
export const formatDateForDisplay = (date) => {
    if (!date) return '';
    return formatDateUtil(date) || '';
};

/**
 * Format a date for API submission (YYYY-MM-DD format)
 * @param {Date|string} date - Date to format
 * @returns {string|null} Formatted date string or null
 */
export const formatDateForAPI = (date) => {
    if (!date) return null;
    if (!(date instanceof Date)) return date;
    return formatDateForInputUtil(date);
};

/**
 * Parse a date string to a Date object
 * @param {string} dateString - Date string to parse
 * @returns {Date|null} Parsed Date object or null
 */
export const parseDate = (dateString) => {
    if (!dateString) return null;
    return parseDateUtil(dateString);
};

/**
 * Check if a date is valid
 * @param {Date|string} date - Date to validate
 * @returns {boolean} True if valid date
 */
export const isValidDate = (date) => {
    if (!date) return false;
    const parsedDate = date instanceof Date ? date : new Date(date);
    return parsedDate instanceof Date && !isNaN(parsedDate);
};

/**
 * Check if a date is in the past
 * @param {Date|string} date - Date to check
 * @returns {boolean} True if date is in the past
 */
export const isPastDate = (date) => {
    if (!isValidDate(date)) return false;
    const parsedDate = date instanceof Date ? date : new Date(date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return parsedDate < today;
};

/**
 * Check if a date is in the future
 * @param {Date|string} date - Date to check
 * @returns {boolean} True if date is in the future
 */
export const isFutureDate = (date) => {
    if (!isValidDate(date)) return false;
    const parsedDate = date instanceof Date ? date : new Date(date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return parsedDate > today;
};

/**
 * Check if a date is today
 * @param {Date|string} date - Date to check
 * @returns {boolean} True if date is today
 */
export const isToday = (date) => {
    if (!isValidDate(date)) return false;
    const parsedDate = date instanceof Date ? date : new Date(date);
    const today = new Date();
    return (
        parsedDate.getDate() === today.getDate() &&
        parsedDate.getMonth() === today.getMonth() &&
        parsedDate.getFullYear() === today.getFullYear()
    );
};

/**
 * Get the number of days between two dates
 * @param {Date|string} date1 - First date
 * @param {Date|string} date2 - Second date
 * @returns {number} Number of days between dates
 */
export const daysBetween = (date1, date2) => {
    if (!isValidDate(date1) || !isValidDate(date2)) return 0;
    const d1 = date1 instanceof Date ? date1 : new Date(date1);
    const d2 = date2 instanceof Date ? date2 : new Date(date2);
    const diffTime = Math.abs(d2 - d1);
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};

/**
 * Get the number of days until a date
 * @param {Date|string} date - Target date
 * @returns {number} Number of days until date (negative if in past)
 */
export const daysUntil = (date) => {
    if (!isValidDate(date)) return 0;
    const targetDate = date instanceof Date ? date : new Date(date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const diffTime = targetDate - today;
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};

/**
 * Add days to a date
 * @param {Date|string} date - Starting date
 * @param {number} days - Number of days to add
 * @returns {Date} New date with days added
 */
export const addDays = (date, days) => {
    const result = date instanceof Date ? new Date(date) : new Date(date);
    result.setDate(result.getDate() + days);
    return result;
};

/**
 * Add months to a date
 * @param {Date|string} date - Starting date
 * @param {number} months - Number of months to add
 * @returns {Date} New date with months added
 */
export const addMonths = (date, months) => {
    const result = date instanceof Date ? new Date(date) : new Date(date);
    result.setMonth(result.getMonth() + months);
    return result;
};

/**
 * Get the start of the day for a date
 * @param {Date|string} date - Date to process
 * @returns {Date} Date set to start of day (00:00:00)
 */
export const startOfDay = (date) => {
    const result = date instanceof Date ? new Date(date) : new Date(date);
    result.setHours(0, 0, 0, 0);
    return result;
};

/**
 * Get the end of the day for a date
 * @param {Date|string} date - Date to process
 * @returns {Date} Date set to end of day (23:59:59.999)
 */
export const endOfDay = (date) => {
    const result = date instanceof Date ? new Date(date) : new Date(date);
    result.setHours(23, 59, 59, 999);
    return result;
};

/**
 * Format a date range for display
 * @param {Date|string} startDate - Start date
 * @param {Date|string} endDate - End date
 * @returns {string} Formatted date range string
 */
export const formatDateRange = (startDate, endDate) => {
    const start = formatDateForDisplay(startDate);
    const end = formatDateForDisplay(endDate);
    if (!start && !end) return '';
    if (!start) return `Until ${end}`;
    if (!end) return `From ${start}`;
    return `${start} - ${end}`;
};

/**
 * Get today's date as a Date object
 * @returns {Date} Today's date with time set to 00:00:00
 */
export const getToday = () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return today;
};

/**
 * Get the current date and time
 * @returns {Date} Current date and time
 */
export const getNow = () => {
    return new Date();
};

/**
 * Compare two dates (ignoring time)
 * @param {Date|string} date1 - First date
 * @param {Date|string} date2 - Second date
 * @returns {number} -1 if date1 < date2, 0 if equal, 1 if date1 > date2
 */
export const compareDates = (date1, date2) => {
    if (!isValidDate(date1) || !isValidDate(date2)) return 0;
    const d1 = startOfDay(date1);
    const d2 = startOfDay(date2);
    if (d1 < d2) return -1;
    if (d1 > d2) return 1;
    return 0;
};

/**
 * Check if a date is within a range
 * @param {Date|string} date - Date to check
 * @param {Date|string} startDate - Range start date
 * @param {Date|string} endDate - Range end date
 * @returns {boolean} True if date is within range (inclusive)
 */
export const isDateInRange = (date, startDate, endDate) => {
    if (!isValidDate(date)) return false;
    if (!isValidDate(startDate) && !isValidDate(endDate)) return true;

    const d = startOfDay(date);

    if (isValidDate(startDate) && !isValidDate(endDate)) {
        return d >= startOfDay(startDate);
    }

    if (!isValidDate(startDate) && isValidDate(endDate)) {
        return d <= startOfDay(endDate);
    }

    return d >= startOfDay(startDate) && d <= startOfDay(endDate);
};
