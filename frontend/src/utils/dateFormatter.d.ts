export type DateInput = string | Date | null | undefined;
export function parseDate(dateString: DateInput): Date | null;
export function formatDate(date: DateInput): string;
export function formatDateForInput(date: DateInput): string;
export function formatDateTime(datetime: DateInput): string;
