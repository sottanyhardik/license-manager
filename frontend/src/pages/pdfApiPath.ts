export function normalizePdfApiPath(value: string | null): string | null {
    const trimmed = value?.trim();
    if (!trimmed || Array.from(trimmed).some((char) => { const code = char.charCodeAt(0); return code <= 31 || code === 127; })) return null;
    if (/^[a-z][a-z\d+\-.]*:/i.test(trimmed) || trimmed.startsWith("//") || trimmed.includes("\\")) return null;
    return trimmed;
}
