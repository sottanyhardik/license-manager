/**
 * Application-wide Constants
 *
 * This file contains all magic numbers and constant values used across the application.
 * Centralizing constants makes the codebase easier to maintain and update.
 */

// Pagination
export const DEFAULT_PAGE_SIZE = 25;
export const ITEMS_PER_PAGE = 25;
export const MAX_PAGE_SIZE = 100;

// Thresholds
export const MIN_CIF_THRESHOLD = 500;
export const MIN_BALANCE_THRESHOLD = 100;
export const EXPIRY_WARNING_DAYS = 30;

// Timeouts (in milliseconds)
export const API_TIMEOUT = 30000; // 30 seconds
export const DEBOUNCE_DELAY = 300; // 300ms for search/filter debouncing
export const TOAST_AUTO_CLOSE = 3000; // 3 seconds

// Buffer Values
export const ALLOTMENT_VALUE_BUFFER = 20; // $20 buffer for allotments

// File Upload
export const MAX_FILE_SIZE_MB = 10;
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
export const ACCEPTED_FILE_TYPES = {
    DOCUMENTS: ['.pdf', '.jpg', '.jpeg', '.png'],
    IMAGES: ['.jpg', '.jpeg', '.png'],
    EXCEL: ['.xlsx', '.xls'],
    PDF: ['.pdf']
};

// HSN Codes
export const DEFAULT_HSN_CODE = '49070000';

// Date Formats
export const DATE_FORMAT = 'YYYY-MM-DD';
export const DISPLAY_DATE_FORMAT = 'DD-MM-YYYY';
export const DATETIME_FORMAT = 'YYYY-MM-DD HH:mm:ss';

// API Response Codes
export const HTTP_STATUS = {
    OK: 200,
    CREATED: 201,
    BAD_REQUEST: 400,
    UNAUTHORIZED: 401,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    INTERNAL_SERVER_ERROR: 500
};

// License Types
export const LICENSE_TYPES = {
    DFIA: 'DFIA',
    RODTEP: 'RODTEP',
    ROSTL: 'ROSTL',
    MEIS: 'MEIS',
    INCENTIVE: 'INCENTIVE'
};

// Trade Directions
export const TRADE_DIRECTIONS = {
    PURCHASE: 'PURCHASE',
    SALE: 'SALE',
    COMMISSION_PURCHASE: 'COMMISSION_PURCHASE',
    COMMISSION_SALE: 'COMMISSION_SALE'
};

// Billing Modes
export const BILLING_MODES = {
    QTY: 'QTY',
    CIF_INR: 'CIF_INR',
    FOB_INR: 'FOB_INR'
};

// Default Percentage Rates
export const DEFAULT_CIF_PERCENTAGE = 7.9;
export const DEFAULT_FOB_PERCENTAGE = 7.9;

// Transaction Types
export const TRANSACTION_TYPES = {
    OPENING: 'OPENING',
    PURCHASE: 'PURCHASE',
    SALE: 'SALE',
    ADJUSTMENT: 'ADJUSTMENT'
};

// Sold Status
export const SOLD_STATUS = {
    NO: 'NO',
    PARTIAL: 'PARTIAL',
    YES: 'YES'
};

// Purchase Status
export const PURCHASE_STATUS = {
    GE: 'GE', // GE Purchase
    GO: 'GO', // GE Operating
    SM: 'SM', // SM Purchase
    MI: 'MI', // Conversion
    IP: 'IP', // IP
    CO: 'CO'  // CO
};

// Environment
export const IS_DEVELOPMENT = process.env.NODE_ENV === 'development';
export const IS_PRODUCTION = process.env.NODE_ENV === 'production';

// Validation Rules
export const VALIDATION = {
    MIN_PASSWORD_LENGTH: 8,
    MAX_PASSWORD_LENGTH: 128,
    MIN_USERNAME_LENGTH: 3,
    MAX_USERNAME_LENGTH: 50,
    PAN_LENGTH: 10,
    GST_LENGTH: 15
};

// Table Settings
export const TABLE_SETTINGS = {
    MIN_COLUMN_WIDTH: 100,
    MAX_ROWS_PER_PAGE: 100,
    STICKY_HEADER_OFFSET: 0
};

// Animation Durations (in milliseconds)
export const ANIMATION_DURATION = {
    FAST: 150,
    NORMAL: 300,
    SLOW: 500
};

// Colors (for consistency)
export const COLORS = {
    PRIMARY: 'var(--primary-color)',
    SECONDARY: 'var(--primary-dark)',
    SUCCESS: 'var(--success-color)',
    DANGER: 'var(--danger-color)',
    WARNING: 'var(--warning-color)',
    INFO: 'var(--info-color)',
    LIGHT: 'var(--bs-gray-50)',
    DARK: 'var(--bs-gray-700)'
};

// Export Format Options
export const EXPORT_FORMATS = {
    PDF: 'pdf',
    EXCEL: 'xlsx',
    CSV: 'csv'
};

// Scroll Behavior
export const SCROLL_BEHAVIOR = {
    SMOOTH: 'smooth',
    AUTO: 'auto',
    INSTANT: 'instant'
};

// Form States
export const FORM_STATES = {
    IDLE: 'idle',
    SUBMITTING: 'submitting',
    SUCCESS: 'success',
    ERROR: 'error'
};
