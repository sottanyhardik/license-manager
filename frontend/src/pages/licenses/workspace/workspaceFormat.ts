import { NOT_COMPUTED, formatIsoDate } from "@/pages/licence-balances/format";

/** ISO dates from the transaction feed are shown as `31 Dec 2026`. Anything else is shown as received. */
export function displayDate(value: string | null | undefined): string {
  if (!value) return NOT_COMPUTED;
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? formatIsoDate(value) : value;
}
