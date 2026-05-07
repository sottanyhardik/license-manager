/**
 * Logger Utility
 *
 * Provides development-only logging to keep production builds clean.
 * All console statements should use this utility instead of direct console calls.
 */

import { IS_DEVELOPMENT } from '../constants';

/**
 * Log a message to the console (development only)
 * @param {...any} args - Arguments to log
 */
export const log = (...args) => {
    if (IS_DEVELOPMENT) {
        console.log(...args);
    }
};

/**
 * Log an error to the console (development only)
 * @param {...any} args - Arguments to log
 */
export const error = (...args) => {
    if (IS_DEVELOPMENT) {
        console.error(...args);
    }
};

/**
 * Log a warning to the console (development only)
 * @param {...any} args - Arguments to log
 */
export const warn = (...args) => {
    if (IS_DEVELOPMENT) {
        console.warn(...args);
    }
};

/**
 * Log an info message to the console (development only)
 * @param {...any} args - Arguments to log
 */
export const info = (...args) => {
    if (IS_DEVELOPMENT) {
        console.info(...args);
    }
};

/**
 * Log a debug message to the console (development only)
 * @param {...any} args - Arguments to log
 */
export const debug = (...args) => {
    if (IS_DEVELOPMENT) {
        console.debug(...args);
    }
};

/**
 * Log a table to the console (development only)
 * @param {any} data - Data to display as table
 */
export const table = (data) => {
    if (IS_DEVELOPMENT) {
        console.table(data);
    }
};

/**
 * Start a console timer (development only)
 * @param {string} label - Timer label
 */
export const time = (label) => {
    if (IS_DEVELOPMENT) {
        console.time(label);
    }
};

/**
 * End a console timer (development only)
 * @param {string} label - Timer label
 */
export const timeEnd = (label) => {
    if (IS_DEVELOPMENT) {
        console.timeEnd(label);
    }
};

/**
 * Group console logs (development only)
 * @param {string} label - Group label
 */
export const group = (label) => {
    if (IS_DEVELOPMENT) {
        console.group(label);
    }
};

/**
 * Group console logs collapsed (development only)
 * @param {string} label - Group label
 */
export const groupCollapsed = (label) => {
    if (IS_DEVELOPMENT) {
        console.groupCollapsed(label);
    }
};

/**
 * End a console group (development only)
 */
export const groupEnd = () => {
    if (IS_DEVELOPMENT) {
        console.groupEnd();
    }
};

/**
 * Clear the console (development only)
 */
export const clear = () => {
    if (IS_DEVELOPMENT) {
        console.clear();
    }
};

// Default export with all methods
const logger = {
    log,
    error,
    warn,
    info,
    debug,
    table,
    time,
    timeEnd,
    group,
    groupCollapsed,
    groupEnd,
    clear
};

export default logger;
