export function normalizeMinBalance(value: unknown, fallback = 200): number {
    const parsed = Number.parseInt(String(value), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
}
