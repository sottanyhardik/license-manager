const DEFAULT_DAYS = 365;
export const MIN_DAYS = 1;
export const MAX_DAYS = 3650;
export function normalizeDownloadDays(value: unknown, fallback = DEFAULT_DAYS): number { const fallbackDays = Number.isFinite(fallback) ? Math.min(MAX_DAYS, Math.max(MIN_DAYS, Math.trunc(fallback))) : DEFAULT_DAYS; const parsed = Number.parseInt(String(value), 10); return Number.isFinite(parsed) ? Math.min(MAX_DAYS, Math.max(MIN_DAYS, parsed)) : fallbackDays; }
export function parseLicenseNumbers(value: string): string[] { const seen = new Set<string>(); const numbers: string[] = []; for (const rawValue of value.split(/[\s,]+/)) { const licenseNumber = rawValue.trim(); if (licenseNumber && !seen.has(licenseNumber)) { seen.add(licenseNumber); numbers.push(licenseNumber); } } return numbers; }
