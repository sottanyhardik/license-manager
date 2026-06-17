// Per-item licence condition badge. Shown next to a LicenseImportItemsModel
// serial number wherever it appears (License form, BOE rows, Allotment items,
// Trade lines, reports). Driven by the `condition_type` field on the row.
//
// Values come from the DFIA parser's condition-sheet extraction:
//   "AU"  — Actual User (item is non-transferable for this licence)
//   "2%"  / "3%" / "5%" / "10%" — CIF capped at N% of total licence CIF
//
// Anything else passes through as a generic grey badge with the raw value.

import { CONDITION_BADGE_PALETTE as CONDITION_BADGE_STYLES } from "../theme/tokens";

export default function ConditionBadge({ type, size = "sm" }) {
    if (!type) return null;
    const style = CONDITION_BADGE_STYLES[type] || {
        bg: "#E5E7EB", color: "#374151", label: type,
    };
    const sized = size === "xs"
        ? { fontSize: "0.6rem", padding: "1px 4px" }
        : { fontSize: "0.65rem", padding: "2px 6px" };
    return (
        <span
            title={type === "AU"
                ? "Actual-user condition (non-transferable for this item)"
                : `Restricted: CIF shall not exceed ${type} of total licence CIF`}
            style={{
                display: "inline-flex",
                alignItems: "center",
                background: style.bg,
                color: style.color,
                fontWeight: 700,
                borderRadius: 4,
                marginLeft: 6,
                lineHeight: 1.2,
                whiteSpace: "nowrap",
                ...sized,
            }}
        >{style.label}</span>
    );
}
