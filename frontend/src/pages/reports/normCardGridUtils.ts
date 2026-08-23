export type NormalizedNormCard = { normClass: string; description: string; isConversionNorm: boolean };
export const CONVERSION_NORMS = new Set(["E1", "E5", "E126", "E132"]);
export function normalizeNormCards(availableNorms: unknown): NormalizedNormCard[] {
    if (!Array.isArray(availableNorms)) return [];
    const seen = new Set<string>();
    return availableNorms.flatMap((value: any) => {
        const normClass = String(value && typeof value === "object" ? value.norm_class ?? "" : value ?? "").trim();
        if (!normClass || seen.has(normClass)) return [];
        seen.add(normClass);
        return [{ normClass, description: String(value && typeof value === "object" ? value.description ?? "" : "").trim(), isConversionNorm: CONVERSION_NORMS.has(normClass) }];
    });
}
