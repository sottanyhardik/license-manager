import DOMPurify from 'dompurify';

/**
 * Sanitizes HTML content to prevent XSS attacks
 *
 * Usage: When displaying user-generated HTML content using dangerouslySetInnerHTML
 *
 * Example:
 * <div dangerouslySetInnerHTML={{ __html: sanitizeHtml(userContent) }} />
 *
 * Note: React automatically escapes content in JSX expressions like {variable},
 * so sanitization is only needed when using dangerouslySetInnerHTML or innerHTML
 */
export const sanitizeHtml = (html) => {
    return DOMPurify.sanitize(html, {
        ALLOWED_TAGS: ['b', 'i', 'em', 'strong'],
        ALLOWED_ATTR: []
    });
};

/**
 * Sanitizes plain text by stripping all HTML tags
 *
 * Usage: When you need to ensure no HTML at all
 */
export const sanitizeText = (text) => {
    return DOMPurify.sanitize(text, {
        ALLOWED_TAGS: [],
        ALLOWED_ATTR: []
    });
};
