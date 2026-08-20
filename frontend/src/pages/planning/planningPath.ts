export function planningPath(licenseId?: string | number | null, origin?: string): string {
    const params = new URLSearchParams();
    if (licenseId) params.set("license_id", String(licenseId));
    if (origin) params.set("origin", origin);
    return `/planning${params.size ? `?${params}` : ""}`;
}
