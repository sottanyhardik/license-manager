import { isAxiosError } from "axios";

/** HTTP status of an axios failure, or undefined for anything else. */
export function responseStatus(error: unknown): number | undefined {
  return isAxiosError(error) ? error.response?.status : undefined;
}

/** A plain-language explanation for a failed load. Never exposes raw server text. */
export function describeLoadError(error: unknown): string {
  switch (responseStatus(error)) {
    case 401:
      return "Your session has expired. Sign in again to continue.";
    case 403:
      return "You do not have permission to view licence balances.";
    case 404:
      return "This licence could not be found.";
    default:
      return "Check your connection and try again.";
  }
}
