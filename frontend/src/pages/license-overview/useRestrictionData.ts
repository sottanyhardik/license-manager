import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";

/**
 * Restriction data returned from the API.
 * Maps backend restriction keys (tenRestriction, twoRestriction, etc.)
 * to frontend-friendly names and values.
 */
export interface RestrictionBudget {
  /** Restriction percentage (e.g., 2, 3, 5, 10) */
  percentage: number;
  /** Available budget limit for this restriction */
  limit: number;
  /** Amount already used against this restriction */
  used: number;
  /** Amount available (limit - used) */
  available: number;
}

export interface RestrictionData {
  total_value: number;
  restrictions: RestrictionBudget[];
  [key: string]: any;
}

/**
 * Maps backend restriction keys to human-readable percentages.
 * Backend returns keys like: tenRestriction, twoRestriction, threeRestriction, fiveRestriction
 */
const RESTRICTION_KEY_MAP: Record<string, number> = {
  tenRestriction: 10,
  fiveRestriction: 5,
  threeRestriction: 3,
  twoRestriction: 2,
};

/**
 * Fetches restriction budget data for a license.
 * Uses GET /licenses/{id}/ endpoint which includes get_per_cif() data.
 */
export function useRestrictionData(licenseId: string | number | undefined) {
  return useQuery<RestrictionData | null>({
    queryKey: ["license-restrictions", String(licenseId ?? "")],
    queryFn: async () => {
      if (!licenseId) return null;

      try {
        const { data } = await api.get(`licenses/${licenseId}/`);

        // Extract per_cif data which contains restriction budgets
        const perCif = data.get_per_cif || {};
        const totalValue = data.balance_cif ? parseFloat(String(data.balance_cif)) : 0;

        // Transform backend format to frontend format
        const restrictions: RestrictionBudget[] = [];
        for (const [key, limit] of Object.entries(perCif)) {
          const percentage = RESTRICTION_KEY_MAP[key];
          if (percentage) {
            restrictions.push({
              percentage,
              limit: parseFloat(String(limit)) || 0,
              // For now, used is 0 until we have ledger data
              // This will be enhanced later with actual ledger queries
              used: 0,
              available: parseFloat(String(limit)) || 0,
            });
          }
        }

        return {
          total_value: totalValue,
          restrictions: restrictions.sort((a, b) => b.percentage - a.percentage),
        };
      } catch (error) {
        console.warn("Failed to fetch restriction data:", error);
        return null;
      }
    },
    enabled: Boolean(licenseId),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Query key factory for restriction-related queries.
 */
export const restrictionKeys = {
  all: () => ["restrictions"] as const,
  license: (licenseId: string | number) => ["restrictions", String(licenseId)] as const,
};
