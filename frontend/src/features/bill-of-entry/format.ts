import { formatTruthyIndianNumber, formatTruthyInr } from "@/pages/masters/masterDisplayFormatters";

type Formattable = number | string | null | undefined;

/**
 * Card formatters (display-only). Output is identical to the original inline
 * `toLocaleString('en-IN', …)` calls: falsy values (0, '', null) render '—'.
 */
export const fmtInr = (val: unknown): string => formatTruthyInr(val as Formattable);
/** INR to paise for record-detail views (the card keeps whole rupees). */
export const fmtInrExact = (val: unknown): string => formatTruthyInr(val as Formattable, "—", { maximumFractionDigits: 2 });
export const fmtQty = (val: unknown): string => formatTruthyIndianNumber(val as Formattable, { maximumFractionDigits: 3 });
/** Foreign-currency / unit-price amounts, up to 2 decimal places. */
export const fmtFc2 = (val: unknown): string => formatTruthyIndianNumber(val as Formattable, { maximumFractionDigits: 2 });

