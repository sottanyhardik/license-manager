/**
 * Plain-language labels for backend status, flag and movement codes.
 * Unknown codes are passed through so nothing is silently relabelled.
 */

export type StatusTone = "good" | "warn" | "bad" | "info" | "neutral";
export type StatusIconName = "check" | "warning" | "down" | "help" | "stop" | "ruler" | "neutral";

export interface StatusDisplay {
  label: string;
  tone: StatusTone;
  icon: StatusIconName;
}

const STATUS_DISPLAY: Record<string, StatusDisplay> = {
  RECONCILED: { label: "Reconciled", tone: "good", icon: "check" },
  "REVIEW REQUIRED": { label: "Review required", tone: "warn", icon: "warning" },
  "OVER-UTILISED": { label: "Over-utilised", tone: "bad", icon: "down" },
  "UNMAPPED ITEM": { label: "Unmapped item", tone: "neutral", icon: "help" },
  "OVER-ALLOCATED": { label: "Over-allocated", tone: "bad", icon: "stop" },
  UNIT_UNVERIFIED: { label: "Unit unverified", tone: "info", icon: "ruler" },
  // Item CIF under licence-level control: attribution of the licence's pooled CIF, not an item limit.
  "LICENCE-LEVEL CONTROL": { label: "Licence-level CIF control", tone: "neutral", icon: "neutral" },
};

export function statusDisplay(status: string | null | undefined): StatusDisplay {
  const key = (status ?? "").trim().toUpperCase();
  const known = STATUS_DISPLAY[key];
  if (known) return known;
  const raw = (status ?? "").trim();
  return { label: raw || "No status", tone: "neutral", icon: "neutral" };
}

const FLAG_EXPLANATIONS: Record<string, string> = {
  ALLOT_AND_SALE_OVERLAP_UNVERIFIED:
    "An allotment and a sale on the same item may be the same entitlement — review",
  ALLOTMENT_LINKED_BOE_NOT_ON_ITEM: "An allotment is linked to a BOE on another licence or item",
  CROSS_ITEM: "A BOE on this item is linked to a sale of another item",
  OVER_LINKED: "BOEs linked to a sale exceed its amount; the excess is counted",
  UNIT_UNVERIFIED: "Quantity unit is not verified",
  OVER_LINKED_MIXED_OWNERSHIP:
    "Over-linked excess whose sale has both previous-owner and current-owner BOEs; the excess owner is not determined — review",
  OVER_UTILISED: "Available is negative",
  LEGACY_BALANCE_DIFFERS: "Legacy balance engine disagrees with the reconciled figure — review",
  LICENCE_CIF_DEPENDS_ON_UNVERIFIED_SALE:
    "The licence CIF result depends on whether an unverified sale is external or internal — review",
};

export interface FlagDisplay {
  code: string;
  text: string;
  /** False for codes without a plain-language explanation; `text` is then the raw code. */
  known: boolean;
}

export function describeFlag(code: string): FlagDisplay {
  const text = FLAG_EXPLANATIONS[code];
  return text ? { code, text, known: true } : { code, text: code, known: false };
}

const MOVEMENT_LABELS: Record<string, string> = {
  ORIGINAL: "Original authorisation",
  SALE: "Sale (invoiced)",
  SALE_COVERED_BOE: "Sale-covered BOE",
  BOE_DEBIT: "Bill of entry (used)",
  OVER_LINKED_EXCESS: "Over-linked excess",
  ALLOTMENT: "Reserved for customer",
};

export function movementLabel(kind: string): string {
  return MOVEMENT_LABELS[kind] ?? kind;
}
