import { parseDate } from "../../utils/dateFormatter";

const INDIAN_LOCALE = "en-IN";

type NumericValue = number | string | null | undefined;

export function formatTruthyIndianNumber(
  value: NumericValue,
  options: Intl.NumberFormatOptions,
  emptyValue = "—",
) {
  return value
    ? Number(value).toLocaleString(INDIAN_LOCALE, options)
    : emptyValue;
}

export function formatTruthyInr(
  value: NumericValue,
  emptyValue = "—",
  options: Intl.NumberFormatOptions = { maximumFractionDigits: 0 },
) {
  return value
    ? `₹${Number(value).toLocaleString(INDIAN_LOCALE, options)}`
    : emptyValue;
}

export function formatInr(
  value: NumericValue,
  options: Intl.NumberFormatOptions = { minimumFractionDigits: 2 },
) {
  return `₹${Number(value || 0).toLocaleString(INDIAN_LOCALE, options)}`;
}

export function parseMasterDisplayDate(value: string | null | undefined) {
  return parseDate(value);
}
